"""Open-vocabulary pseudo-labeler (YOLO-World) and the Z0 gate.

Z0 measures the labeler on the real val split before it is trusted anywhere.
A class whose AP50 is below `min_ap50_for_pseudo` may not be pseudo-labeled.
"""
from __future__ import annotations

import json
import time

from tqdm import tqdm

from .metrics import ap50_per_class, nms_same_class
from .dataset import real_dir, val_ids
from .records import by_id, load_yaml, read_records
from .settings import get_settings


class PseudoLabeler:
    def __init__(self, cfg: dict | None = None, device: str | None = None):
        from ultralytics import YOLOWorld

        self.cfg = cfg or load_yaml("text_prompts")
        self.prompt_cls: list[str] = []
        prompts: list[str] = []
        for cls, plist in self.cfg["prompts"].items():
            for p in plist:
                prompts.append(p)
                self.prompt_cls.append(cls)
        weights = get_settings().data_root / "weights" / self.cfg["model"]
        weights.parent.mkdir(parents=True, exist_ok=True)
        self.model = YOLOWorld(str(weights))
        self.model.set_classes(prompts)
        self.device = device or get_settings().train_devices
        # warm-up so the first real batch does not trip the NMS time limit
        import numpy as np

        self.model.predict(np.zeros((640, 640, 3), np.uint8), device=self.device, verbose=False)

    def predict(self, images, imgsz: int = 640) -> list[list[tuple]]:
        """images: list of BGR arrays. Returns [(cls, conf, xyxy)] per image."""
        out = []
        for res in self.model.predict(images, conf=self.cfg["conf"], imgsz=imgsz,
                                      device=self.device, verbose=False, stream=True):
            dets = []
            b = res.boxes
            for k in range(len(b)):
                dets.append((self.prompt_cls[int(b.cls[k])], float(b.conf[k]),
                             [float(v) for v in b.xyxy[k].tolist()]))
            out.append(nms_same_class(dets))
        return out


def run_z0(profile: dict) -> dict:
    from .records import imread

    cfg = load_yaml("text_prompts")
    rdir = real_dir(profile)
    real = by_id(read_records(rdir))
    val = [real[i] for i in val_ids(profile)]
    classes = list(cfg["prompts"])
    out_dir = get_settings().runs_root / profile["name"]
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        labeler = PseudoLabeler(cfg)
        preds = []
        for k in tqdm(range(0, len(val), 16), desc="z0", unit="batch"):
            chunk = val[k:k + 16]
            preds += labeler.predict([imread(rdir / r["file"]) for r in chunk])
    except Exception as e:  # recorded, not hidden: only the closed-set fallback may verify
        fb = _coco_fallback(cfg, val, rdir)
        thr = cfg["min_ap50_for_pseudo"]
        allowed = [c for c, v in fb.get("per_class", {}).items()
                   if v["ap50"] is not None and v["ap50"] >= thr] if fb.get("status") == "ok" else []
        result = {"status": "failed", "error": f"{type(e).__name__}: {e}", "model": cfg["model"],
                  "threshold": thr, "allowed_classes": allowed,
                  "labeler": "coco_fallback" if allowed else None, "fallback": fb}
        (out_dir / "z0.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        (out_dir / "z0.md").write_text(render_md(result, profile), encoding="utf-8")
        return result
    gts = [[(b["cls"], b["xyxy"]) for b in r["boxes"]] for r in val]
    per = ap50_per_class(preds, gts, classes)
    thr = cfg["min_ap50_for_pseudo"]
    result = {"status": "ok", "model": cfg["model"], "prompts": cfg["prompts"], "conf": cfg["conf"],
              "val_images": len(val), "per_class": per, "threshold": thr,
              "allowed_classes": [c for c, v in per.items() if v["ap50"] is not None and v["ap50"] >= thr],
              "labeler": "open_vocab", "seconds": round(time.time() - t0, 1)}
    (out_dir / "z0.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (out_dir / "z0.md").write_text(render_md(result, profile), encoding="utf-8")
    return result


class CocoLabeler:
    """Closed-set labeler: the COCO-pretrained detector we fine-tune from, restricted to
    the SynthGuard classes COCO actually has (person). Same interface as PseudoLabeler."""

    def __init__(self, cfg: dict | None = None, device: str | None = None):
        from ultralytics import YOLO

        self.cfg = cfg or load_yaml("text_prompts")
        self.ids = self.cfg["fallback_coco_ids"]
        self.inv = {v: k for k, v in self.ids.items()}
        weights = get_settings().data_root / "weights" / self.cfg["fallback_model"]
        weights.parent.mkdir(parents=True, exist_ok=True)
        self.model = YOLO(str(weights))
        self.device = device or get_settings().train_devices
        # warm-up: the first CUDA call is slow enough to trip ultralytics' NMS time limit,
        # which would silently truncate that batch's detections
        import numpy as np

        self.model.predict(np.zeros((640, 640, 3), np.uint8), device=self.device, verbose=False)

    def predict(self, images) -> list[list[tuple]]:
        out = []
        for res in self.model.predict(images, conf=self.cfg["conf"], classes=list(self.ids.values()),
                                      device=self.device, verbose=False):
            b = res.boxes
            out.append([(self.inv[int(b.cls[i])], float(b.conf[i]), b.xyxy[i].tolist())
                        for i in range(len(b))])
        return out


def make_labeler(kind: str | None):
    """The labeler Z0 approved, or None."""
    if kind == "open_vocab":
        return PseudoLabeler()
    if kind == "coco_fallback":
        return CocoLabeler()
    return None


def _coco_fallback(cfg: dict, val: list[dict], rdir) -> dict:
    """Z0 for the closed-set baseline on the real val split."""
    from .records import imread

    try:
        labeler = CocoLabeler(cfg)
        preds = []
        for k in range(0, len(val), 16):
            preds += labeler.predict([imread(rdir / r["file"]) for r in val[k:k + 16]])
        gts = [[(b["cls"], b["xyxy"]) for b in r["boxes"]] for r in val]
        classes = list(labeler.ids)
        return {"status": "ok", "model": cfg["fallback_model"], "classes": classes,
                "per_class": ap50_per_class(preds, gts, classes)}
    except Exception as e:
        return {"status": "failed", "error": f"{type(e).__name__}: {e}"}


def render_md(r: dict, profile: dict) -> str:
    lines = [f"# Z0 · pseudo-labeler gate (profile `{profile['name']}`)", ""]
    if r["status"] != "ok":
        allowed = r.get("allowed_classes") or []
        lines += [f"Open-vocabulary labeler `{r['model']}`: **failed** — `{r['error']}`", "",
                  ("The closed-set fallback below passes the gate for "
                   f"{', '.join(allowed)}: diffusion QA re-detects those boxes with it; other "
                   "classes rely on edge agreement only. No class is ever pseudo-labeled from "
                   "scratch." if allowed else
                   "No labeler passes the gate; diffusion QA relies on edge agreement only."), ""]
        fb = r.get("fallback") or {}
        if fb.get("status") == "ok":
            lines += [f"Fallback baseline: COCO-pretrained `{fb['model']}` (the init of every "
                      "experiment), zero-shot on the real val split. COCO has no hard-hat class, "
                      "so helmet is not measurable this way.", "",
                      "| class | AP50 | GT boxes | max recall |", "|---|---:|---:|---:|"]
            for c, v in fb["per_class"].items():
                ap = "n/a" if v["ap50"] is None else f"{v['ap50'] * 100:.1f}"
                lines.append(f"| {c} | {ap} | {v['n_gt']} | {v.get('max_recall', 0) * 100:.1f} |")
            lines.append("| helmet | n/a (no COCO class) | — | — |")
        elif fb:
            lines.append(f"Fallback baseline also failed: `{fb.get('error')}`")
        return "\n".join(lines) + "\n"
    lines += [f"Model `{r['model']}` (open-vocabulary), conf ≥ {r['conf']}, "
              f"{r['val_images']} real val images, AP50 all-point interpolation.", "",
              "| class | prompts | AP50 | GT boxes | max recall | pseudo-label allowed |",
              "|---|---|---:|---:|---:|---|"]
    for c, v in r["per_class"].items():
        ap = "n/a" if v["ap50"] is None else f"{v['ap50'] * 100:.1f}"
        mr = f"{v.get('max_recall', 0) * 100:.1f}"
        ok = "yes" if c in r["allowed_classes"] else "no"
        lines.append(f"| {c} | {', '.join(r['prompts'][c])} | {ap} | {v['n_gt']} | {mr} | {ok} |")
    lines += ["", f"Gate: AP50 ≥ {r['threshold'] * 100:.0f} to allow pseudo-labels for a class. "
              "Diffusion outputs keep the source image's propagated boxes; the labeler is only "
              "used to verify them for allowed classes (see `gen_client.py`)."]
    return "\n".join(lines) + "\n"
