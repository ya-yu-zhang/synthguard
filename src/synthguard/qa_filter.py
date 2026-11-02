"""Automatic QA for factory output (never applied to the real val split)."""
from __future__ import annotations

from collections import Counter

from .records import box_iou

MIN_SIDE_PX = 3.0
MIN_AREA_PX = 16.0
MAX_AREA_FRAC = 0.95
DUP_IOU = 0.9


def filter_record(rec: dict) -> tuple[dict, Counter]:
    """Clip, drop degenerate/oversized boxes, de-duplicate same-class near-identical boxes."""
    w, h = rec["w"], rec["h"]
    reasons: Counter = Counter()
    kept: list[dict] = []
    for b in rec["boxes"]:
        x1, y1, x2, y2 = b["xyxy"]
        x1, y1, x2, y2 = max(0.0, x1), max(0.0, y1), min(float(w), x2), min(float(h), y2)
        bw, bh = x2 - x1, y2 - y1
        if bw < MIN_SIDE_PX or bh < MIN_SIDE_PX or bw * bh < MIN_AREA_PX:
            reasons["too_small"] += 1
            continue
        if bw * bh > MAX_AREA_FRAC * w * h:
            reasons["too_large"] += 1
            continue
        nb = {**b, "xyxy": [x1, y1, x2, y2]}
        if any(k["cls"] == nb["cls"] and box_iou(k["xyxy"], nb["xyxy"]) > DUP_IOU for k in kept):
            reasons["duplicate"] += 1
            continue
        kept.append(nb)
    return {**rec, "boxes": kept}, reasons


def filter_records(records: list[dict]) -> tuple[list[dict], dict]:
    total: Counter = Counter()
    out = []
    empty = 0
    for r in records:
        fr, why = filter_record(r)
        total.update(why)
        if not fr["boxes"]:
            empty += 1
        out.append(fr)
    return out, {"dropped_boxes": dict(total), "images_without_boxes": empty, "images": len(out)}
