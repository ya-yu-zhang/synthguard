"""The one internal annotation format: a JSONL "pool" of image records.

A pool is a directory with `images/` and `records.jsonl`. Each record:

    {"id": str, "file": "images/<name>", "w": int, "h": int,
     "source": "real" | "augment" | "paste" | "diffusion",
     "boxes": [{"cls": str, "xyxy": [x1, y1, x2, y2]}],   # absolute pixels
     ...manifest fields (source_id, aug_id, seed, ops, ...)}
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
import yaml

from .settings import get_settings


def load_yaml(name_or_path: str | Path) -> dict:
    p = Path(name_or_path)
    if not p.suffix:
        p = get_settings().configs_dir / f"{p}.yaml"
    elif not p.is_absolute() and not p.exists():
        p = get_settings().configs_dir / p
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_list(name: str) -> list[str]:
    p = get_settings().configs_dir / name
    return [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


# cv2.imread/imwrite cannot open non-ASCII paths on Windows; go through numpy buffers.
def imread(path: str | Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise IOError(f"cannot decode image: {path}")
    return img


def imwrite(path: str | Path, img: np.ndarray) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(path.suffix or ".png", img)
    if not ok:
        raise IOError(f"cannot encode image: {path}")
    buf.tofile(str(path))


def read_records(pool: Path) -> list[dict]:
    f = pool / "records.jsonl"
    if not f.exists():
        return []
    with open(f, encoding="utf-8") as fh:
        return [json.loads(ln) for ln in fh if ln.strip()]


def write_records(pool: Path, records: Iterable[dict]) -> int:
    pool.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(pool / "records.jsonl", "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n


def pool_dir(name: str, profile: str) -> Path:
    """Factory pools (augment / paste / diffusion) live per profile.
    The downloaded public set is `dataset.real_dir(profile)`."""
    return get_settings().data_root / "pools" / profile / name


def by_id(records: Iterable[dict]) -> dict[str, dict]:
    return {r["id"]: r for r in records}


def box_iou(a, b) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def box_ioa(a, region) -> float:
    """Fraction of box `a` covered by `region`."""
    ix1, iy1 = max(a[0], region[0]), max(a[1], region[1])
    ix2, iy2 = min(a[2], region[2]), min(a[3], region[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area = (a[2] - a[0]) * (a[3] - a[1])
    return inter / area if area > 0 else 0.0
