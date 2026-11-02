"""Instance copy-paste with ground-truth boxes (no pseudo-labels).

Instances are cropped from seed train images with a small margin. A crop is only
banked if every other box it touches lies (almost) entirely inside it or encloses
the instance, so the pasted pixels never carry an unlabeled partial neighbour. Placements that would
cover an existing object are retried.
"""
from __future__ import annotations

import random
from statistics import median

import cv2
import numpy as np
from tqdm import tqdm

from .dataset import real_dir, seed_ids
from .records import box_ioa, box_iou, imread, imwrite, pool_dir, read_records, write_records

MIN_SIDE = 8          # px; smaller instances are not banked
INNER_IOA = 0.9       # a touched box must be >= 90% inside the crop to travel with it
COVER_IOA = 0.25      # max fraction of an existing box a paste may cover
MAX_IOU = 0.3
TRIES = 25


def _crop_rect(box, margin, w, h):
    bw, bh = box[2] - box[0], box[3] - box[1]
    mx, my = bw * margin, bh * margin
    return [max(0.0, box[0] - mx), max(0.0, box[1] - my), min(float(w), box[2] + mx),
            min(float(h), box[3] + my)]


def bank_instances(records: list[dict]) -> dict[str, list[dict]]:
    bank: dict[str, list[dict]] = {}
    for r in records:
        for i, b in enumerate(r["boxes"]):
            x1, y1, x2, y2 = b["xyxy"]
            if x2 - x1 < MIN_SIDE or y2 - y1 < MIN_SIDE:
                continue
            for margin in (0.1, 0.0):
                rect = _crop_rect(b["xyxy"], margin, r["w"], r["h"])
                inner, ok = [], True
                for j, o in enumerate(r["boxes"]):
                    if j == i:
                        continue
                    ioa = box_ioa(o["xyxy"], rect)
                    if ioa >= INNER_IOA:
                        inner.append(o)
                    elif ioa > 0 and box_ioa(b["xyxy"], o["xyxy"]) < INNER_IOA:
                        # a box that merely encloses the instance (person around a helmet)
                        # is context; anything else cut by the crop edge is a conflict
                        ok = False
                        break
                if ok:
                    bank.setdefault(b["cls"], []).append(
                        {"rec": r, "box": b, "rect": rect, "inner": inner})
                    break
    return bank


def feather_mask(h: int, w: int) -> np.ndarray:
    f = max(1, int(round(0.08 * min(h, w))))
    m = np.zeros((h, w), np.float32)
    m[f:h - f, f:w - f] = 1.0 if h > 2 * f and w > 2 * f else 0.0
    if m.max() == 0:
        m[:] = 1.0
        return m[..., None]
    k = 2 * f + 1
    return cv2.GaussianBlur(m, (k, k), 0)[..., None]


SIZE_GROUP = {"helmet": "head_level", "head": "head_level", "person": "person"}
SCALE_RANGE = (0.5, 2.0)   # resizing beyond this looks implausible: skip, never clamp
HEAD_PER_PERSON = 0.15     # fallback: head-level box height ~ 15% of a person box
INSTANCE_TRIES = 10


def _scale_for(inst: dict, bg: dict, rng: random.Random) -> float | None:
    """Scale that matches the background's typical size for the instance's group
    (helmet and head share one). None when the background offers no size reference or
    the instance would need resizing outside SCALE_RANGE, e.g. a close-up helmet for a
    wide shot; clamping instead produced visibly oversized pastes."""
    ih = inst["box"]["xyxy"][3] - inst["box"]["xyxy"][1]
    g = SIZE_GROUP.get(inst["box"]["cls"], inst["box"]["cls"])

    def heights(group):
        return [b["xyxy"][3] - b["xyxy"][1] for b in bg["boxes"]
                if SIZE_GROUP.get(b["cls"], b["cls"]) == group]

    if heights(g):
        ref = median(heights(g))
    elif g == "head_level" and heights("person"):
        ref = median(heights("person")) * HEAD_PER_PERSON
    elif g == "person" and heights("head_level"):
        ref = median(heights("head_level")) / HEAD_PER_PERSON
    else:
        return None
    s = ref / ih * rng.uniform(0.8, 1.2)
    return float(s) if SCALE_RANGE[0] <= s <= SCALE_RANGE[1] else None


def _place(inst, bg, scale, occupied, rng):
    rx1, ry1, rx2, ry2 = inst["rect"]
    cw, ch = int(round((rx2 - rx1) * scale)), int(round((ry2 - ry1) * scale))
    if cw < MIN_SIDE or ch < MIN_SIDE or cw >= bg["w"] or ch >= bg["h"]:
        return None
    heads = [b["xyxy"] for b in bg["boxes"] if b["cls"] in ("helmet", "head")]
    for _ in range(TRIES):
        x = rng.randint(0, bg["w"] - cw)
        if inst["box"]["cls"] in ("helmet", "head") and heads:
            # prior: hats appear at the height band where heads already are
            ref = rng.choice(heads)
            y = int(ref[1] + rng.uniform(-1.0, 1.0) * (ref[3] - ref[1]))
        else:
            y = rng.randint(0, bg["h"] - ch)
        y = min(max(0, y), bg["h"] - ch)
        rect = [x, y, x + cw, y + ch]
        # neither covering an existing object nor landing inside one
        if all(box_ioa(o, rect) <= COVER_IOA and box_ioa(rect, o) <= COVER_IOA
               and box_iou(o, rect) <= MAX_IOU for o in occupied):
            return rect
    return None


def _map_box(xyxy, inst, rect, scale):
    rx1, ry1 = inst["rect"][0], inst["rect"][1]
    return [round(rect[0] + (xyxy[0] - rx1) * scale, 2), round(rect[1] + (xyxy[1] - ry1) * scale, 2),
            round(rect[0] + (xyxy[2] - rx1) * scale, 2), round(rect[1] + (xyxy[3] - ry1) * scale, 2)]


def paste(profile: dict, base_seed: int = 0) -> dict:
    real = real_dir(profile)
    recs = {r["id"]: r for r in read_records(real)}
    seeds = [recs[i] for i in seed_ids(profile)]
    bank = bank_instances(seeds)
    pcfg = profile["paste"]
    weights = {c: pcfg["class_weights"].get(c, 1.0) for c in bank}
    n_out = round(profile["seed_take"] * profile["increment"]["paste_frac"])

    rng = random.Random(base_seed + 7919)
    bgs = seeds[:]
    rng.shuffle(bgs)
    cache: dict[str, np.ndarray] = {}

    def load(r):
        if r["id"] not in cache:
            cache[r["id"]] = imread(real / r["file"])
        return cache[r["id"]]

    out_pool = pool_dir("paste", profile["name"])
    out, skipped, scale_rejects = [], 0, 0
    classes = sorted(bank)
    for k in tqdm(range(n_out), desc="copy-paste", unit="img"):
        bg = bgs[k % len(bgs)]
        canvas = load(bg).copy()
        boxes = [dict(b) for b in bg["boxes"]]
        occupied = [b["xyxy"] for b in boxes]
        pastes = []
        for _ in range(rng.randint(1, pcfg["max_instances_per_image"])):
            cls = rng.choices(classes, weights=[weights[c] for c in classes])[0]
            pool = [i for i in bank[cls] if i["rec"]["id"] != bg["id"]]
            if not pool:
                continue
            rect = None
            for _ in range(INSTANCE_TRIES):  # find an instance whose size fits this scene
                inst = rng.choice(pool)
                scale = _scale_for(inst, bg, rng)
                if scale is None:
                    scale_rejects += 1
                    continue
                rect = _place(inst, bg, scale, occupied, rng)
                if rect is not None:
                    break
                skipped += 1
            if rect is None:
                continue
            src = load(inst["rec"])
            rx1, ry1, rx2, ry2 = (int(round(v)) for v in inst["rect"])
            crop = cv2.resize(src[ry1:ry2, rx1:rx2], (rect[2] - rect[0], rect[3] - rect[1]),
                              interpolation=cv2.INTER_LINEAR)
            a = feather_mask(*crop.shape[:2])
            roi = canvas[rect[1]:rect[3], rect[0]:rect[2]].astype(np.float32)
            canvas[rect[1]:rect[3], rect[0]:rect[2]] = (a * crop + (1 - a) * roi).astype(np.uint8)
            for b in [inst["box"]] + inst["inner"]:
                nb = {"cls": b["cls"], "xyxy": _map_box(b["xyxy"], inst, rect, scale)}
                boxes.append(nb)
                occupied.append(nb["xyxy"])
            occupied.append(rect)
            pastes.append({"cls": cls, "instance_from": inst["rec"]["id"], "scale": round(scale, 3),
                           "rect": rect, "n_boxes": 1 + len(inst["inner"])})
        if not pastes:
            continue
        rid = f"paste_{bg['id']}_{k:04d}"
        imwrite(out_pool / "images" / f"{rid}.png", canvas)
        out.append({"id": rid, "file": f"images/{rid}.png", "w": bg["w"], "h": bg["h"],
                    "source": "paste", "boxes": boxes, "source_id": bg["id"],
                    "seed": base_seed, "pastes": pastes})
    write_records(out_pool, out)
    return {"images": len(out), "pasted_instances": sum(len(r["pastes"]) for r in out),
            "placement_failures": skipped, "scale_rejects": scale_rejects,
            "bank": {c: len(v) for c, v in bank.items()},
            "pool": str(out_pool)}
