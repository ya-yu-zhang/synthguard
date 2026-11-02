"""Assemble experiment datasets (E0 / E2 / E1) and write them in YOLO format.

The val split is always the same real list; anything synthetic or derived from a
val image is refused.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import yaml

from .class_map import class_ids
from .dataset import class_map, real_dir, seed_ids, val_ids
from .qa_filter import filter_records
from .records import by_id, pool_dir, read_records
from .settings import get_settings

EXPERIMENTS = {
    "E0": ("real",),
    "E2": ("real", "augment", "paste"),
    "E1": ("real", "augment", "paste", "diffusion"),
}


class ValLeakError(RuntimeError):
    pass


def yolo_lines(rec: dict, ids: dict[str, int]) -> list[str]:
    lines = []
    w, h = rec["w"], rec["h"]
    for b in rec["boxes"]:
        x1, y1, x2, y2 = b["xyxy"]
        cx, cy = (x1 + x2) / 2 / w, (y1 + y2) / 2 / h
        bw, bh = (x2 - x1) / w, (y2 - y1) / h
        lines.append(f"{ids[b['cls']]} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
    return lines


def check_no_val_leak(train: list[dict], val: list[dict]) -> None:
    val_ids = {r["id"] for r in val}
    bad = [r["id"] for r in val if r["source"] != "real"]
    if bad:
        raise ValLeakError(f"non-real records in val: {bad[:5]}")
    for r in train:
        if r["id"] in val_ids or r.get("source_id") in val_ids:
            raise ValLeakError(f"train record {r['id']} is (derived from) a val image")
        for p in r.get("pastes", []):
            if p.get("instance_from") in val_ids:
                raise ValLeakError(f"train record {r['id']} pastes an instance from val")


def collect(profile: dict, exp: str) -> tuple[list[tuple[Path, dict]], list[tuple[Path, dict]], dict]:
    rdir = real_dir(profile)
    real = by_id(read_records(rdir))
    seed = [real[i] for i in seed_ids(profile)]
    val = [real[i] for i in val_ids(profile)]
    train = [(rdir, r) for r in seed]
    qa: dict = {}
    for name in EXPERIMENTS[exp][1:]:
        d = pool_dir(name, profile["name"])
        recs = read_records(d)
        if name == "diffusion":
            recs = [r for r in recs if r.get("qa", {}).get("accepted")]
        if not recs:
            raise FileNotFoundError(f"pool '{name}' is empty for profile {profile['name']}; "
                                    f"run the matching factory step first")
        recs, qa[name] = filter_records(recs)
        if name == "diffusion":
            # design §4.1: diffusion is at most 50% of the increment
            classic = sum(1 for _, r in train if r["source"] != "real")
            recs = recs[:classic]
        train += [(d, r) for r in recs]
    check_no_val_leak([r for _, r in train], val)
    return train, [(rdir, r) for r in val], qa


def _place_file(src: Path, dst: Path) -> None:
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def export(profile: dict, exp: str) -> Path:
    ids = class_ids(class_map(profile))
    train, val, qa = collect(profile, exp)
    root = get_settings().data_root / "yolo" / profile["name"] / exp
    if root.exists():
        shutil.rmtree(root)
    for split, items in (("train", train), ("val", val)):
        (root / "images" / split).mkdir(parents=True)
        (root / "labels" / split).mkdir(parents=True)
        for pool, r in items:
            src = pool / r["file"]
            name = f"{r['id']}{src.suffix}"
            _place_file(src, root / "images" / split / name)
            (root / "labels" / split / f"{r['id']}.txt").write_text(
                "\n".join(yolo_lines(r, ids)) + ("\n" if r["boxes"] else ""), encoding="utf-8")
    data = {"path": str(root), "train": "images/train", "val": "images/val",
            "names": {i: c for c, i in ids.items()}}
    (root / "data.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    meta = {"experiment": exp, "train_images": len(train), "val_images": len(val),
            "train_sources": {}, "qa": qa}
    for _, r in train:
        meta["train_sources"][r["source"]] = meta["train_sources"].get(r["source"], 0) + 1
    (root / "export_meta.yaml").write_text(yaml.safe_dump(meta, sort_keys=False), encoding="utf-8")
    return root / "data.yaml"
