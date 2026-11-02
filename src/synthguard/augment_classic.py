"""Classic augmentation with box propagation (weather / imaging / occlusion / mild geometry)."""
from __future__ import annotations

import random

import albumentations as A
import cv2
import numpy as np
from tqdm import tqdm

from .dataset import real_dir, seed_ids
from .records import imread, imwrite, load_yaml, pool_dir, read_records, write_records


def build_pipeline(cfg: dict) -> A.ReplayCompose:
    w, im, oc, ge = cfg["weather"], cfg["imaging"], cfg["occlusion"], cfg["geometry"]
    return A.ReplayCompose(
        [
            A.HorizontalFlip(p=ge["hflip_p"]),
            A.Affine(scale=(0.85, 1.15), translate_percent=(-0.06, 0.06), rotate=(-5, 5),
                     border_mode=cv2.BORDER_CONSTANT, fill=114, p=ge["affine_p"]),
            A.RandomRain(slant_range=(-8, 8), drop_width=1, blur_value=3,
                         brightness_coefficient=0.85, p=w["rain_p"]),
            A.RandomFog(fog_coef_range=(0.1, 0.3), alpha_coef=0.08, p=w["fog_p"]),
            A.RandomBrightnessContrast(brightness_limit=0.25, contrast_limit=0.25,
                                       p=w["brightness_contrast_p"]),
            A.ISONoise(color_shift=(0.01, 0.04), intensity=(0.1, 0.4), p=w["iso_noise_p"]),
            A.MotionBlur(blur_limit=(3, 7), p=im["motion_blur_p"]),
            A.ImageCompression(quality_range=(35, 85), p=im["jpeg_p"]),
            A.RandomShadow(shadow_roi=(0, 0.3, 1, 1), num_shadows_limit=(1, 2), p=im["shadow_p"]),
            A.CoarseDropout(num_holes_range=(1, 3), hole_height_range=(0.04, 0.12),
                            hole_width_range=(0.04, 0.12), fill="random_uniform",
                            p=oc["blocks_p"]),
        ],
        bbox_params=A.BboxParams(format="pascal_voc", label_fields=["cls"],
                                 min_visibility=cfg["min_visibility"], clip=True),
    )


def draw_occluding_lines(img: np.ndarray, rng: random.Random) -> np.ndarray:
    """1-3 thick straight bars, a stand-in for poles / fence rails crossing the view."""
    h, w = img.shape[:2]
    out = img.copy()
    for _ in range(rng.randint(1, 3)):
        g = rng.randint(40, 200)
        thick = rng.randint(2, max(3, w // 60))
        if rng.random() < 0.5:  # near-vertical pole
            x = rng.randint(0, w - 1)
            p1, p2 = (x, 0), (x + rng.randint(-w // 20, w // 20), h - 1)
        else:  # near-horizontal rail
            y = rng.randint(h // 3, h - 1)
            p1, p2 = (0, y), (w - 1, y + rng.randint(-h // 20, h // 20))
        cv2.line(out, p1, p2, (g, g, g), thick, lineType=cv2.LINE_AA)
    return out


def reseed(pipe: A.BaseCompose, seed: int) -> None:
    """Per-image reproducible seeding. Compose.set_random_seed hands every child the same
    seed (albumentations 2.0.x), which makes ops with equal p fire all-or-nothing; give
    each child its own derived seed instead."""
    pipe.set_random_seed(seed)
    for i, t in enumerate(pipe.transforms):
        t.set_random_seed(seed * 1009 + i * 7919 + 1)


def applied_ops(replay: dict) -> list[str]:
    ops = []
    for t in replay["transforms"]:
        if t.get("applied"):
            ops.append(t["__class_fullname__"].split(".")[-1])
    return ops


def augment(profile: dict, base_seed: int = 0) -> dict:
    cfg = load_yaml("augment")
    real = real_dir(profile)
    recs = {r["id"]: r for r in read_records(real)}
    sources = [recs[i] for i in seed_ids(profile)]
    n_out = round(profile["seed_take"] * profile["increment"]["augment_frac"])

    rng = random.Random(base_seed)
    order = [s for s in sources if s["boxes"]]
    rng.shuffle(order)
    picks = [order[k % len(order)] for k in range(n_out)]

    pipe = build_pipeline(cfg)
    out_pool = pool_dir("augment", profile["name"])
    out = []
    for k, src in enumerate(tqdm(picks, desc="augment", unit="img")):
        seed = base_seed * 1_000_003 + k
        reseed(pipe, seed)
        img = imread(real / src["file"])
        res = pipe(image=img, bboxes=[b["xyxy"] for b in src["boxes"]],
                   cls=[b["cls"] for b in src["boxes"]])
        ops = applied_ops(res["replay"])
        image = res["image"]
        lrng = random.Random(seed)
        if lrng.random() < cfg["occlusion"]["lines_p"]:
            image = draw_occluding_lines(image, lrng)
            ops.append("OccludingLines")
        rid = f"aug_{src['id']}_{k:04d}"
        imwrite(out_pool / "images" / f"{rid}.png", image)
        h, w = image.shape[:2]
        boxes = [{"cls": c, "xyxy": [round(float(v), 2) for v in bb]}
                 for bb, c in zip(res["bboxes"], res["cls"])]
        out.append({"id": rid, "file": f"images/{rid}.png", "w": w, "h": h,
                    "source": "augment", "boxes": boxes, "source_id": src["id"],
                    "aug_id": k, "seed": seed, "ops": ops})
    write_records(out_pool, out)
    return {"images": len(out), "boxes": sum(len(r["boxes"]) for r in out), "pool": str(out_pool)}
