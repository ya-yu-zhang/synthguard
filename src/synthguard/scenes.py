"""Text-to-image scene batches for MANUAL labeling.

Unlike the factory pools (augment / paste / diffusion), these images carry no boxes:
the manifest records which elements each prompt asked for, as a hint for annotators,
not as labels. Output: <data>/scenes/<batch>/{images/, manifest.jsonl, classes.txt,
contact_*.jpg, batch.json}. batch.json carries the run parameters and status
(running / done / failed; the web UI marks interrupted runs as cancelled).
"""
from __future__ import annotations

import json
import math
import random
import re
import time

import cv2
import numpy as np

from . import gen_client as gc
from .records import imwrite, load_yaml
from .settings import get_settings


def build_prompt(spec: dict, rng: random.Random) -> tuple[str, list[str], tuple[int, int]]:
    names = list(spec["elements"])
    weights = [spec["weights"].get(n, 1) for n in names]
    lo, hi = spec["elements_per_image"]
    k = rng.randint(lo, hi)
    picked: list[str] = []
    while len(picked) < k:
        n = rng.choices(names, weights=weights)[0]
        if n not in picked:
            picked.append(n)
    parts = [rng.choice(spec["settings"])] + [spec["elements"][n]["text"] for n in picked] + \
        [rng.choice(spec["viewpoints"]), rng.choice(spec["conditions"]), spec["style"]]
    size = tuple(rng.choice(spec["sizes"]))
    return ", ".join(parts), picked, size


def contact_sheets(rows: list[dict], out_dir, per_sheet: int = 25, thumb: int = 300) -> list[str]:
    from .records import imread

    names = []
    for s in range(0, len(rows), per_sheet):
        tiles = []
        for r in rows[s:s + per_sheet]:
            img = imread(out_dir / r["file"])
            h, w = img.shape[:2]
            sc = thumb / max(h, w)
            img = cv2.resize(img, (int(w * sc), int(h * sc)))
            tile = np.full((thumb + 22, thumb, 3), 255, np.uint8)
            tile[22:22 + img.shape[0], :img.shape[1]] = img
            cv2.putText(tile, r["id"], (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (30, 30, 30), 1,
                        cv2.LINE_AA)
            tiles.append(tile)
        while len(tiles) % 5:
            tiles.append(np.full_like(tiles[0], 255))
        grid = np.vstack([np.hstack(tiles[i:i + 5]) for i in range(0, len(tiles), 5)])
        name = f"contact_{s // per_sheet + 1:02d}.jpg"
        imwrite(out_dir / name, grid)
        names.append(name)
    return names


BATCH_NAME = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


def with_weights(spec: dict, overrides: dict | None) -> dict:
    """Copy of the spec with some element weights replaced (unknown names are an error)."""
    if not overrides:
        return spec
    unknown = set(overrides) - set(spec["elements"])
    if unknown:
        raise ValueError(f"unknown elements: {', '.join(sorted(unknown))}")
    weights = {k: float(v) for k, v in overrides.items()}
    bad = sorted(k for k, v in weights.items() if not (math.isfinite(v) and 0 < v <= 1000))
    if bad:
        raise ValueError(f"element weights must be in (0, 1000]: {', '.join(bad)}")
    return {**spec, "weights": {**spec["weights"], **weights}}


def coverage(spec: dict, rows_elements: list[list[str]]) -> dict[str, int]:
    shows = [{c for p in picked for c in spec["elements"][p]["shows"]} for picked in rows_elements]
    return {c: sum(1 for s in shows if c in s) for c in spec["classes"]}


def preview(spec: dict, n: int, seed: int = 0) -> dict[str, int]:
    """Requested-class counts a batch would get, without generating anything."""
    rng = random.Random(seed)
    return coverage(spec, [build_prompt(spec, rng)[1] for _ in range(n)])


def _write_info(out_dir, info: dict) -> None:
    (out_dir / "batch.json").write_text(json.dumps(info, ensure_ascii=False, indent=2),
                                        encoding="utf-8", newline="\n")


def run(spec_name: str, n: int, batch: str, seed: int = 0, operator: str = "",
        weights_override: dict | None = None) -> dict:
    s = get_settings()
    if not BATCH_NAME.match(batch):
        raise ValueError("batch name: letters, digits, '-' and '_' only (max 40)")
    spec = with_weights(load_yaml(f"scenes_{spec_name}"), weights_override)
    weights = load_yaml(f"gen_{s.gen_profile}")["weights"].get("krea2")
    if not weights:
        raise RuntimeError(f"configs/gen_{s.gen_profile}.yaml has no weights.krea2 block")
    out_dir = s.data_root / "scenes" / batch
    if (out_dir / "manifest.jsonl").exists():
        raise FileExistsError(f"batch '{batch}' already exists; pick another name")
    if gc.probe(s.comfy_url) is None:
        raise RuntimeError(f"ComfyUI offline at {s.comfy_url}")
    (out_dir / "images").mkdir(parents=True, exist_ok=True)
    (out_dir / "classes.txt").write_text("\n".join(spec["classes"]) + "\n", encoding="utf-8",
                                         newline="\n")
    info = {"batch": batch, "spec": spec_name, "n": n, "seed": seed, "operator": operator,
            "weights_override": weights_override or {}, "generator": spec["generator"],
            "model": weights["unet"], "steps": spec["steps"],
            "started": time.strftime("%Y-%m-%d %H:%M:%S"), "status": "running"}
    _write_info(out_dir, info)
    rng = random.Random(seed)
    template = gc.load_workflow("krea2_t2i")
    rows, errors, t0 = [], [], time.time()
    # manifest grows row by row, so an interrupted batch keeps what it already made
    with open(out_dir / "manifest.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for k in range(n):
            prompt, picked, (w, h) = build_prompt(spec, rng)
            gseed = seed * 1_000_003 + k
            rid = f"{spec['name']}_{batch}_{k:04d}"
            try:
                png = gc.submit_and_wait(s.comfy_url, gc.fill(template, {
                    **weights, "width": w, "height": h, "seed": gseed, "steps": spec["steps"],
                    "prompt": prompt}))[0]
            except Exception as e:
                errors.append(f"{rid}: {type(e).__name__}: {e}")
                print(f"[scenes] {errors[-1][:300]}", flush=True)
                if len(errors) >= 3 and not rows:
                    break
                continue
            (out_dir / "images" / f"{rid}.png").write_bytes(png)
            shows = sorted({c for p in picked for c in spec["elements"][p]["shows"]})
            rows.append({"id": rid, "file": f"images/{rid}.png", "w": w, "h": h, "seed": gseed,
                         "generator": spec["generator"], "model": weights["unet"],
                         "steps": spec["steps"], "prompt": prompt, "elements": picked,
                         "requested_classes": shows})
            fh.write(json.dumps(rows[-1], ensure_ascii=False) + "\n")
            fh.flush()
            print(f"[scenes] {k + 1}/{n} {rid} {w}x{h} {','.join(picked)}", flush=True)
    gc.free_vram(s.comfy_url)
    sheets = contact_sheets(rows, out_dir) if rows else []
    cov = coverage(spec, [r["elements"] for r in rows])
    info.update(status="done" if rows else "failed", images=len(rows), errors=len(errors),
                seconds=round(time.time() - t0, 1), finished=time.strftime("%Y-%m-%d %H:%M:%S"),
                first_errors=errors[:3])
    _write_info(out_dir, info)
    return {"batch": batch, "images": len(rows), "errors": errors[:5],
            "seconds": info["seconds"], "requested_class_coverage": cov,
            "contact_sheets": sheets, "dir": str(out_dir)}
