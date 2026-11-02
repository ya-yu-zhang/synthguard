"""Small, dependency-free AP50 for the pseudo-labeler gate (Z0) and diffusion QA.

Detector training/eval numbers (E0/E2/E1) come from ultralytics' own validator;
this module is only used where predictions do not come from a trained YOLO.
"""
from __future__ import annotations

import numpy as np

from .records import box_iou


def ap_from_pr(recall: np.ndarray, precision: np.ndarray) -> float:
    """All-point interpolated AP (area under the monotone precision envelope)."""
    mrec = np.concatenate(([0.0], recall, [1.0]))
    mpre = np.concatenate(([1.0], precision, [0.0]))
    mpre = np.flip(np.maximum.accumulate(np.flip(mpre)))
    idx = np.where(mrec[1:] != mrec[:-1])[0]
    return float(np.sum((mrec[idx + 1] - mrec[idx]) * mpre[idx + 1]))


def ap50_per_class(preds: list[list[tuple]], gts: list[list[tuple]], classes: list[str],
                   iou_thr: float = 0.5) -> dict[str, dict]:
    """preds[i] = [(cls, conf, xyxy)], gts[i] = [(cls, xyxy)] for image i."""
    out = {}
    for c in classes:
        n_gt = sum(1 for g in gts for gc, _ in g if gc == c)
        dets = [(conf, i, box) for i, p in enumerate(preds) for pc, conf, box in p if pc == c]
        dets.sort(key=lambda d: -d[0])
        used = [np.zeros(sum(1 for gc, _ in g if gc == c), bool) for g in gts]
        gt_boxes = [[b for gc, b in g if gc == c] for g in gts]
        tp = np.zeros(len(dets))
        for k, (_, i, box) in enumerate(dets):
            best, bj = 0.0, -1
            for j, gb in enumerate(gt_boxes[i]):
                iou = box_iou(box, gb)
                if iou > best:
                    best, bj = iou, j
            if best >= iou_thr and not used[i][bj]:
                used[i][bj] = True
                tp[k] = 1
        if n_gt == 0:
            out[c] = {"ap50": None, "n_gt": 0, "n_det": len(dets)}
            continue
        ctp = np.cumsum(tp)
        recall = ctp / n_gt
        precision = ctp / np.arange(1, len(dets) + 1) if dets else np.array([])
        ap = ap_from_pr(recall, precision) if dets else 0.0
        out[c] = {"ap50": ap, "n_gt": n_gt, "n_det": len(dets),
                  "max_recall": float(recall[-1]) if dets else 0.0}
    return out


def nms_same_class(dets: list[tuple], iou_thr: float = 0.6) -> list[tuple]:
    """dets = [(cls, conf, xyxy)]; greedy NMS within each class."""
    kept: list[tuple] = []
    for d in sorted(dets, key=lambda d: -d[1]):
        if all(k[0] != d[0] or box_iou(k[2], d[2]) < iou_thr for k in kept):
            kept.append(d)
    return kept
