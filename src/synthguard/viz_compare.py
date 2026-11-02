"""Triptychs for the README: factory side (original / augment / paste) and model side
(val ground truth / E0 prediction / E2 prediction). Writes to assets/examples/ (≤ 20 files)."""
from __future__ import annotations

import random

import cv2
import numpy as np

from .dataset import real_dir, val_ids
from .records import by_id, imread, imwrite, pool_dir, read_records
from .settings import get_settings, repo_root

COLORS = {"person": (60, 180, 75), "helmet": (0, 200, 255), "head": (200, 80, 200)}
MAX_FILES = 20


def draw(img: np.ndarray, boxes, title: str, conf: bool = False) -> np.ndarray:
    out = img.copy()
    for b in boxes:
        cls, xyxy = b["cls"], b["xyxy"]
        c = COLORS.get(cls, (255, 255, 255))
        x1, y1, x2, y2 = (int(round(v)) for v in xyxy)
        cv2.rectangle(out, (x1, y1), (x2, y2), c, 2)
        label = f"{cls} {b['conf']:.2f}" if conf and "conf" in b else cls
        cv2.putText(out, label, (x1, max(10, y1 - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.38, c, 1,
                    cv2.LINE_AA)
    bar = np.full((26, out.shape[1], 3), 245, np.uint8)
    cv2.putText(bar, title, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (30, 30, 30), 1, cv2.LINE_AA)
    return np.vstack([bar, out])


def _row(panels: list[np.ndarray]) -> np.ndarray:
    h = max(p.shape[0] for p in panels)
    pad = [cv2.copyMakeBorder(p, 0, h - p.shape[0], 0, 4, cv2.BORDER_CONSTANT, value=(255, 255, 255))
           for p in panels]
    return np.hstack(pad)


def _predict(weights, img, imgsz):
    from ultralytics import YOLO

    res = YOLO(str(weights)).predict(img, conf=0.25, imgsz=imgsz, verbose=False,
                                     device=get_settings().train_devices)[0]
    return [{"cls": res.names[int(c)], "conf": float(p), "xyxy": xy.tolist()}
            for c, p, xy in zip(res.boxes.cls, res.boxes.conf, res.boxes.xyxy)]


def run(profile: dict, n_factory: int = 4, n_pred: int = 4, seed: int = 0) -> list[str]:
    rdir = real_dir(profile)
    real = by_id(read_records(rdir))
    aug_dir, paste_dir = pool_dir("augment", profile["name"]), pool_dir("paste", profile["name"])
    aug = {r["source_id"]: r for r in read_records(aug_dir)}
    pas = {r["source_id"]: r for r in read_records(paste_dir)}
    out_dir = repo_root() / "assets" / "examples"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.jpg"):
        old.unlink()
    written = []
    rng = random.Random(seed)

    both = sorted(set(aug) & set(pas))
    rng.shuffle(both)
    for sid in both[:n_factory]:
        src = real[sid]
        a, p = aug[sid], pas[sid]
        row = _row([draw(imread(rdir / src["file"]), src["boxes"], "original (GT)"),
                    draw(imread(aug_dir / a["file"]), a["boxes"], "classic aug: " + ",".join(a["ops"][:3])),
                    draw(imread(paste_dir / p["file"]), p["boxes"],
                         f"copy-paste +{sum(x['n_boxes'] for x in p['pastes'])} boxes")])
        f = out_dir / f"factory_{sid}.jpg"
        imwrite(f, row)
        written.append(f.name)

    work = get_settings().runs_root / profile["name"] / "train"
    w0, w2 = work / "E0_s0" / "weights" / "best.pt", work / "E2_s0" / "weights" / "best.pt"
    if w0.exists() and w2.exists():
        val = [real[i] for i in val_ids(profile)]
        val = [r for r in val if len(r["boxes"]) >= 2]
        rng.shuffle(val)
        imgsz = profile["train"]["imgsz"]
        for r in val[:n_pred]:
            img = imread(rdir / r["file"])
            row = _row([draw(img, r["boxes"], "val ground truth"),
                        draw(img, _predict(w0, img, imgsz), "E0 prediction", conf=True),
                        draw(img, _predict(w2, img, imgsz), "E2 prediction", conf=True)])
            f = out_dir / f"pred_{r['id']}.jpg"
            imwrite(f, row)
            written.append(f.name)
    assert len(written) <= MAX_FILES
    return written
