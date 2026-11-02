"""Train/evaluate one experiment with identical settings across E0 / E2 / E1."""
from __future__ import annotations

import json
import platform
import shutil
import time

from .dataset import class_map
from .export_yolo import export
from .settings import get_settings


def _device() -> str:
    d = get_settings().train_devices.strip()
    return d or "0"


def train_one(profile: dict, exp: str, seed: int, data_yaml=None) -> dict:
    import torch
    import ultralytics
    from ultralytics import YOLO

    s = get_settings()
    t = profile["train"]
    data_yaml = data_yaml or export(profile, exp)
    run_dir = s.runs_root / profile["name"] / f"{exp}_s{seed}"
    work = s.runs_root / profile["name"] / "train"
    weights = s.data_root / "weights" / t["model"]
    weights.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    model = YOLO(str(weights))
    model.train(data=str(data_yaml), epochs=t["epochs"], imgsz=t["imgsz"], batch=t["batch"],
                workers=t["workers"], seed=seed, deterministic=True, device=_device(),
                project=str(work), name=f"{exp}_s{seed}", exist_ok=True, verbose=False,
                plots=False)
    train_sec = time.time() - t0
    best = work / f"{exp}_s{seed}" / "weights" / "best.pt"

    m = YOLO(str(best)).val(data=str(data_yaml), imgsz=t["imgsz"], batch=t["batch"],
                            split="val", device=_device(), plots=False, verbose=False,
                            project=str(work), name=f"{exp}_s{seed}_val", exist_ok=True)
    names = m.names
    per_class = {}
    for k, ci in enumerate(m.box.ap_class_index):
        per_class[names[int(ci)]] = {"ap50": float(m.box.ap50[k]), "ap50_95": float(m.box.ap[k]),
                                     "p": float(m.box.p[k]), "r": float(m.box.r[k])}
    import yaml

    meta = yaml.safe_load((data_yaml.parent / "export_meta.yaml").read_text(encoding="utf-8"))
    eval_classes = class_map(profile)["eval_classes"]
    ev = [per_class[c] for c in eval_classes if c in per_class]
    result = {
        "experiment": exp, "seed": seed, "profile": profile["name"],
        "model": t["model"], "epochs": t["epochs"], "imgsz": t["imgsz"], "batch": t["batch"],
        "eval_classes": eval_classes, "train_images": meta["train_images"],
        "val_images": meta["val_images"], "train_sources": meta["train_sources"],
        "map50_eval": sum(c["ap50"] for c in ev) / len(ev) if ev else None,
        "map50_95_eval": sum(c["ap50_95"] for c in ev) / len(ev) if ev else None,
        "map50_all": float(m.box.map50), "map50_95_all": float(m.box.map),
        "per_class": per_class, "train_seconds": round(train_sec, 1),
        "env": {"ultralytics": ultralytics.__version__, "torch": torch.__version__,
                "cuda": torch.version.cuda,
                "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
                "python": platform.python_version()},
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    shutil.copy2(work / f"{exp}_s{seed}" / "results.csv", run_dir / "results.csv")
    shutil.copy2(data_yaml.parent / "export_meta.yaml", run_dir / "export_meta.yaml")
    return result


def train(profile: dict, exp: str, seeds: list[int] | None = None) -> list[dict]:
    data_yaml = export(profile, exp)
    return [train_one(profile, exp, s, data_yaml) for s in (seeds or profile["train"]["seeds"])]
