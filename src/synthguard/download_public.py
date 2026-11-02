"""Download a pinned public dataset and convert it to a SynthGuard pool.

Re-entrant: files already on disk are skipped; records are rebuilt each time.
Formats: `fiftyone` (samples.json + per-image files) and `hf_parquet` (images
embedded in parquet shards, COCO-style xywh boxes).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from .class_map import load_class_map, map_label
from .dataset import dataset_cfg, real_dir, seed_ids, val_ids
from .records import read_list, write_records
from .settings import get_settings


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _hf():
    s = get_settings()
    if s.hf_endpoint:
        os.environ["HF_ENDPOINT"] = s.hf_endpoint
    import huggingface_hub  # imported late so HF_ENDPOINT applies

    return huggingface_hub


def _fetch(ds: dict, filename: str, out: Path, sha256: str) -> Path:
    p = Path(_hf().hf_hub_download(ds["hub_id"], filename, repo_type="dataset",
                                   revision=ds["revision"], local_dir=out))
    digest = sha256_file(p)
    if digest != sha256:
        raise RuntimeError(f"{filename} checksum mismatch: {digest} (expected {sha256})")
    return p


def _box(x, y, bw, bh, w, h):
    x1, y1 = max(0.0, x), max(0.0, y)
    x2, y2 = min(float(w), x + bw), min(float(h), y + bh)
    if x2 - x1 < 1 or y2 - y1 < 1:
        return None
    return [round(v, 2) for v in (x1, y1, x2, y2)]


# ---------------------------------------------------------------- fiftyone
def convert_samples(samples_path: Path, cmap: dict) -> list[dict]:
    """FiftyOne samples (normalized [x, y, w, h]) -> pixel xyxy records."""
    samples = json.loads(samples_path.read_text(encoding="utf-8"))["samples"]
    records = []
    for s in samples:
        w, h = s["metadata"]["width"], s["metadata"]["height"]
        boxes = []
        for det in (s.get("ground_truth") or {}).get("detections", []):
            cls = map_label(det["label"], cmap)
            if cls is None:
                continue
            x, y, bw, bh = det["bounding_box"]
            xyxy = _box(x * w, y * h, bw * w, bh * h, w, h)
            if xyxy:
                boxes.append({"cls": cls, "xyxy": xyxy})
        records.append({"id": Path(s["filepath"]).stem, "file": s["filepath"], "w": w, "h": h,
                        "source": "real", "boxes": boxes})
    return records


def _download_fiftyone(ds: dict, ids: list[str] | None, out: Path, cmap: dict) -> dict:
    samples = _fetch(ds, ds["index_file"], out, ds["index_sha256"])
    records = convert_samples(samples, cmap)
    write_records(out, records)
    files = [r["file"] for r in records] if ids is None else [f"data/{i}.png" for i in ids]
    missing = [f for f in files if not (out / f).exists()]
    if missing:
        _hf().snapshot_download(ds["hub_id"], repo_type="dataset", revision=ds["revision"],
                                local_dir=out, allow_patterns=missing, max_workers=8)
    still = [f for f in files if not (out / f).exists()]
    if still:
        raise RuntimeError(f"{len(still)} files failed to download, e.g. {still[:3]}")
    return {"records": len(records), "requested": len(files), "fetched": len(missing)}


# ---------------------------------------------------------------- hf parquet
def source_id(path: str) -> str:
    """'ppe_0062_jpg.rf.<hash>.jpg' -> 'ppe_0062' (unique per source photo)."""
    return re.sub(r"_jpg\.rf\.[0-9a-f]+\.jpg$", "", Path(path).name)


def convert_parquet_rows(rows: list[dict], labels: list[str], cmap: dict) -> list[tuple[dict, bytes]]:
    out = []
    for r in rows:
        w, h = r["width"], r["height"]
        boxes = []
        o = r["objects"]
        for (x, y, bw, bh), cat in zip(o["bbox"], o["category"]):
            cls = map_label(labels[cat], cmap)
            if cls is None:
                continue
            xyxy = _box(x, y, bw, bh, w, h)
            if xyxy:
                boxes.append({"cls": cls, "xyxy": xyxy})
        rid = source_id(r["image"]["path"])
        out.append(({"id": rid, "file": f"images/{rid}.jpg", "w": w, "h": h, "source": "real",
                     "boxes": boxes}, r["image"]["bytes"]))
    return out


def _download_parquet(ds: dict, out: Path, cmap: dict) -> dict:
    import pyarrow.parquet as pq

    records, written = [], 0
    for fname, digest in ds["files"].items():
        p = _fetch(ds, fname, out, digest)
        rows = pq.read_table(p, columns=["width", "height", "objects", "image"]).to_pylist()
        for rec, data in convert_parquet_rows(rows, ds["labels"], cmap):
            dst = out / rec["file"]
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(data)  # original JPEG bytes, no re-encode
                written += 1
            records.append(rec)
    ids = [r["id"] for r in records]
    if len(ids) != len(set(ids)):
        raise RuntimeError("source ids are not unique; split freezing would be unsafe")
    write_records(out, records)
    return {"records": len(records), "requested": len(records), "fetched": written}


# ---------------------------------------------------------------- entry
def needed_ids(profile: dict) -> list[str]:
    return seed_ids(profile) + val_ids(profile)


def download(profile: dict, everything: bool = False) -> dict:
    ds = dataset_cfg(profile)
    cmap = load_class_map(ds["class_map"])
    out = real_dir(profile)
    out.mkdir(parents=True, exist_ok=True)
    if ds["format"] == "fiftyone":
        res = _download_fiftyone(ds, None if everything else needed_ids(profile), out, cmap)
    elif ds["format"] == "hf_parquet":
        res = _download_parquet(ds, out, cmap)  # shards are small; always complete
    else:
        raise ValueError(f"unknown dataset format {ds['format']}")
    return {"dataset": ds["name"], **res, "root": str(out)}


def spot_check(profile: dict, n: int = 5) -> list[tuple[str, str, str]]:
    """Compare a few local images against the dataset's checksum sample."""
    ds = dataset_cfg(profile)
    out = real_dir(profile)
    rows = []
    for ln in read_list(ds["checksums"])[:n]:
        digest, rel = ln.split(maxsplit=1)
        p = out / rel
        rows.append((rel, digest, sha256_file(p) if p.exists() else "missing"))
    return rows
