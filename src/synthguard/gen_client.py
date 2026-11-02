"""Optional diffusion via the ComfyUI HTTP API, with graceful degradation.

Never raises for "diffusion unavailable": it records why in
runs/<profile>/gen_status.json and returns, so the rest of the factory continues.
Generation is conditioned on public seed images (Canny); boxes are propagated
from the source and then verified (edge agreement + Z0-gated pseudo-labeler).
"""
from __future__ import annotations

import json
import random
import time
import uuid
from pathlib import Path

import cv2
import numpy as np
import requests

from .dataset import real_dir, seed_ids
from .records import imread, imwrite, load_yaml, pool_dir, read_records, write_records
from .settings import get_settings, repo_root

WORKFLOWS = {"flux1-dev": "flux_canny_lora_api.json", "sdxl_dev_proxy": "sdxl_canny_img2img_api.json",
             "krea2_img2img_dev_proxy": "krea2_img2img_api.json",
             "krea2_t2i": "krea2_t2i_api.json"}  # scenes for manual labeling (scenes.py)


# ---------------------------------------------------------------- Comfy HTTP
def probe(url: str, timeout: float = 3.0) -> dict | None:
    try:
        r = requests.get(f"{url.rstrip('/')}/system_stats", timeout=timeout)
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError):
        return None


def list_models(url: str, folder: str) -> list[str]:
    try:
        r = requests.get(f"{url.rstrip('/')}/models/{folder}", timeout=10)
        r.raise_for_status()
        return list(r.json())
    except (requests.RequestException, ValueError):
        return []


def free_vram(url: str) -> None:
    """Ask Comfy to unload models so YOLO training can use the GPU (dev: one shared card)."""
    try:
        requests.post(f"{url.rstrip('/')}/free", json={"unload_models": True, "free_memory": True},
                      timeout=30)
    except requests.RequestException:
        pass


def upload_image(url: str, path: Path, name: str) -> str:
    with open(path, "rb") as f:
        r = requests.post(f"{url.rstrip('/')}/upload/image",
                          files={"image": (name, f, "image/png")},
                          data={"overwrite": "true", "subfolder": "synthguard"}, timeout=60)
    r.raise_for_status()
    j = r.json()
    return f"{j['subfolder']}/{j['name']}" if j.get("subfolder") else j["name"]


def submit_and_wait(url: str, workflow: dict, timeout: float = 900.0) -> list[bytes]:
    base = url.rstrip("/")
    r = requests.post(f"{base}/prompt", json={"prompt": workflow, "client_id": uuid.uuid4().hex},
                      timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Comfy rejected workflow: {r.text[:500]}")
    pid = r.json()["prompt_id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        h = requests.get(f"{base}/history/{pid}", timeout=30).json()
        if pid in h:
            entry = h[pid]
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                msgs = [m for m in status.get("messages", []) if m[0] == "execution_error"]
                raise RuntimeError(f"Comfy execution error: {json.dumps(msgs)[:800]}")
            images = []
            for out in entry.get("outputs", {}).values():
                for im in out.get("images", []):
                    v = requests.get(f"{base}/view", params={"filename": im["filename"],
                                     "subfolder": im["subfolder"], "type": im["type"]}, timeout=60)
                    v.raise_for_status()
                    images.append(v.content)
            if images:
                return images
        time.sleep(1.0)
    raise TimeoutError(f"Comfy prompt {pid} did not finish in {timeout:.0f}s")


# ---------------------------------------------------------------- workflow
def fill(template, params: dict):
    """Replace string leaves "{{key}}" by params[key] (keeping the param's type)."""
    if isinstance(template, dict):
        return {k: fill(v, params) for k, v in template.items()}
    if isinstance(template, list):
        return [fill(v, params) for v in template]
    if isinstance(template, str) and template.startswith("{{") and template.endswith("}}"):
        key = template[2:-2]
        if key not in params:
            raise KeyError(f"workflow placeholder '{key}' has no value")
        return params[key]
    return template


def load_workflow(generator: str) -> dict:
    p = repo_root() / "comfy" / "workflows" / WORKFLOWS[generator]
    return json.loads(p.read_text(encoding="utf-8"))


def choose_generator(cfg: dict, url: str) -> tuple[str | None, str]:
    """First generator whose weights Comfy can see: flux1-dev (target), then the dev-only
    stand-ins the profile allows (SDXL + Canny, then Krea 2 img2img without control)."""
    have = {f: set(list_models(url, f)) for f in
            ("diffusion_models", "unet", "text_encoders", "clip", "vae", "loras",
             "checkpoints", "controlnet")}
    unets = have["diffusion_models"] | have["unet"]
    encoders = have["text_encoders"] | have["clip"]
    fw = cfg["weights"]["flux"]
    missing = {"flux": [n for n, ok in (
        (fw["unet"], fw["unet"] in unets), ("clip_l+t5", {fw["clip_l"], fw["t5"]} <= encoders),
        (fw["vae"], fw["vae"] in have["vae"]),
        (fw["control_lora"], fw["control_lora"] in have["loras"])) if not ok]}
    if not missing["flux"]:
        return "flux1-dev", "flux weights present"
    if cfg.get("fallback_sdxl") and "sdxl" in cfg["weights"]:
        sw = cfg["weights"]["sdxl"]
        missing["sdxl proxy"] = [n for n, ok in (
            (sw["ckpt"], sw["ckpt"] in have["checkpoints"]),
            (sw["controlnet"], sw["controlnet"] in have["controlnet"])) if not ok]
        if not missing["sdxl proxy"]:
            return "sdxl_dev_proxy", f"flux weights missing ({', '.join(missing['flux'])}); using SDXL proxy"
    if cfg.get("fallback_krea2") and "krea2" in cfg["weights"]:
        kw = cfg["weights"]["krea2"]
        missing["krea2 proxy"] = [n for n, ok in (
            (kw["unet"], kw["unet"] in unets), (kw["text_encoder"], kw["text_encoder"] in encoders),
            (kw["vae"], kw["vae"] in have["vae"])) if not ok]
        if not missing["krea2 proxy"]:
            return "krea2_img2img_dev_proxy", (f"flux weights missing ({', '.join(missing['flux'])}); "
                                               "using Krea 2 img2img proxy (no control net)")
    return None, "weights missing: " + "; ".join(f"{k} ({', '.join(v)})" for k, v in missing.items())


def gen_size(w: int, h: int, resolution: int) -> tuple[int, int]:
    s = resolution / max(w, h)
    return max(64, int(round(w * s / 64)) * 64), max(64, int(round(h * s / 64)) * 64)


def build_params(cfg: dict, generator: str, image_name: str, w: int, h: int, seed: int) -> dict:
    gw, gh = gen_size(w, h, cfg["resolution"])
    p = {"image": image_name, "width": gw, "height": gh, "seed": seed, "steps": cfg["steps"],
         "prompt": cfg["prompt"], "negative": cfg["negative"], "control_scale": cfg["control_scale"]}
    if generator == "flux1-dev":
        p.update(cfg["weights"]["flux"], guidance=cfg["flux_control_guidance"],
                 weight_dtype=cfg["flux_weight_dtype"])
    elif generator == "krea2_img2img_dev_proxy":
        # turbo model: few steps, cfg 1 (negative prompt has no effect); layout is held
        # only by the img2img strength, so QA must catch drift
        p.update(cfg["weights"]["krea2"], steps=cfg["krea2_steps"], denoise=cfg["krea2_denoise"])
    else:
        p.update(cfg["weights"]["sdxl"], cfg=cfg["sdxl_cfg"], denoise=cfg["img2img_denoise"])
    return p


# ---------------------------------------------------------------- QA
def edge_f1(a: np.ndarray, b: np.ndarray, tol: int = 2) -> float:
    """Edge agreement between two same-size BGR crops (F1 with a small pixel tolerance)."""
    ea = cv2.Canny(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), 80, 160) > 0
    eb = cv2.Canny(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY), 80, 160) > 0
    if ea.sum() == 0 or eb.sum() == 0:
        return 0.0
    k = np.ones((2 * tol + 1, 2 * tol + 1), np.uint8)
    da, db = cv2.dilate(ea.astype(np.uint8), k) > 0, cv2.dilate(eb.astype(np.uint8), k) > 0
    precision = (eb & da).sum() / eb.sum()
    recall = (ea & db).sum() / ea.sum()
    return float(2 * precision * recall / (precision + recall)) if precision + recall else 0.0


def _unmatched(dets, boxes, cls, conf_min, iou_max=0.3) -> int:
    """Confident detections of `cls` that match no ground-truth box of that class."""
    from .records import box_iou

    gt = [b["xyxy"] for b in boxes if b["cls"] == cls]
    return sum(1 for c, conf, xyxy in dets
               if c == cls and conf >= conf_min and all(box_iou(xyxy, g) < iou_max for g in gt))


def qa_generated(src_img, gen_img, boxes, cfg, labeler=None, allowed=()) -> dict:
    """Propagated boxes are only valid if the layout survived generation:
    - edge agreement inside the boxes (objects stayed where they were),
    - edge agreement over the whole image (the scene was not rewritten),
    - for Z0-approved classes: the labeler re-finds the boxes, and finds no extra
      confident instance that the source did not already have (no new unlabeled people)."""
    scores = []
    for b in boxes:
        x1, y1, x2, y2 = (int(round(v)) for v in b["xyxy"])
        if x2 - x1 >= 4 and y2 - y1 >= 4:
            scores.append(edge_f1(src_img[y1:y2, x1:x2], gen_img[y1:y2, x1:x2]))
    edge = float(np.mean(scores)) if scores else 0.0
    glob = edge_f1(src_img, gen_img)
    res = {"edge_f1": round(edge, 3), "edge_ok": edge >= cfg["qa_edge_f1_min"],
           "global_edge_f1": round(glob, 3), "global_ok": glob >= cfg["qa_global_edge_f1_min"]}
    checked = [b for b in boxes if b["cls"] in allowed]
    res["pseudo_match"], res["pseudo_ok"], res["new_instances"] = None, True, None
    if labeler is not None and allowed:
        from .records import box_iou

        src_dets, gen_dets = labeler.predict([src_img, gen_img])
        if checked:
            hit = sum(1 for b in checked if any(d[0] == b["cls"] and box_iou(d[2], b["xyxy"]) >= 0.5
                                                for d in gen_dets))
            res["pseudo_match"] = round(hit / len(checked), 3)
            res["pseudo_ok"] = res["pseudo_match"] >= cfg["qa_pseudo_match_min"]
        conf_min = cfg["qa_new_instance_conf"]
        res["new_instances"] = sum(
            max(0, _unmatched(gen_dets, boxes, c, conf_min) - _unmatched(src_dets, boxes, c, conf_min))
            for c in allowed)
    res["no_new_ok"] = not res["new_instances"]
    res["accepted"] = bool(res["edge_ok"] and res["global_ok"] and res["pseudo_ok"] and res["no_new_ok"])
    return res


# ---------------------------------------------------------------- entry
def comfy_summary(stats: dict) -> dict:
    """Version and VRAM only: system_stats also carries argv / install paths, which must
    not end up in committed run files."""
    sysinfo = stats.get("system", {})
    return {"comfyui_version": sysinfo.get("comfyui_version"),
            "pytorch_version": sysinfo.get("pytorch_version"),
            "devices": [{"name": d.get("name"), "vram_total": d.get("vram_total")}
                        for d in stats.get("devices", [])]}


def _write_status(profile: dict, status: dict) -> dict:
    out = get_settings().runs_root / profile["name"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "gen_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status


def run(profile: dict, n: int | None = None, seed: int = 0) -> dict:
    s = get_settings()
    cfg = load_yaml(f"gen_{s.gen_profile}")
    base = {"profile": profile["name"], "gen_profile": s.gen_profile, "comfy_url": s.comfy_url}
    if s.skip_diffusion:
        print("[gen] SKIP_DIFFUSION=1 -> diffusion skipped")
        return _write_status(profile, {**base, "status": "skipped",
                                       "e1_reason": "SKIP_DIFFUSION=1"})
    stats = probe(s.comfy_url)
    if stats is None:
        print(f"[gen] ComfyUI not reachable at {s.comfy_url} -> diffusion skipped "
              f"(start Comfy or set SKIP_DIFFUSION=1)")
        return _write_status(profile, {**base, "status": "skipped",
                                       "e1_reason": f"ComfyUI offline at {s.comfy_url}"})
    generator, why = choose_generator(cfg, s.comfy_url)
    if generator is None:
        print(f"[gen] {why} -> diffusion skipped")
        return _write_status(profile, {**base, "status": "skipped", "e1_reason": why,
                                       "comfy": comfy_summary(stats)})
    print(f"[gen] generator={generator} ({why})")

    rdir = real_dir(profile)
    recs = {r["id"]: r for r in read_records(rdir)}
    seeds = [recs[i] for i in seed_ids(profile) if recs[i]["boxes"]]
    rng = random.Random(seed + 104729)
    rng.shuffle(seeds)
    n = n or cfg["max_images_smoke"]

    labeler, allowed = None, []
    z0 = s.runs_root / profile["name"] / "z0.json"
    if z0.exists():
        z = json.loads(z0.read_text(encoding="utf-8"))
        allowed = z.get("allowed_classes", [])
        if allowed:
            from .label_pseudo import make_labeler

            labeler = make_labeler(z.get("labeler") or "open_vocab")

    out_pool = pool_dir("diffusion", profile["name"])
    out, errors = [], []
    t0 = time.time()
    for k, src in enumerate(seeds[:n]):
        gseed = seed * 1_000_003 + k
        try:
            name = upload_image(s.comfy_url, rdir / src["file"], f"{src['id']}.png")
            params = build_params(cfg, generator, name, src["w"], src["h"], gseed)
            png = submit_and_wait(s.comfy_url, fill(load_workflow(generator), params))[0]
        except Exception as e:
            errors.append(f"{src['id']}: {type(e).__name__}: {e}")
            print(f"[gen] {errors[-1][:300]}")
            if len(errors) >= 3 and not out:
                break
            continue
        gen = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
        gen = cv2.resize(gen, (src["w"], src["h"]), interpolation=cv2.INTER_AREA)
        qa = qa_generated(imread(rdir / src["file"]), gen, src["boxes"], cfg, labeler, allowed)
        rid = f"gen_{src['id']}_{k:04d}"
        imwrite(out_pool / "images" / f"{rid}.png", gen)
        out.append({"id": rid, "file": f"images/{rid}.png", "w": src["w"], "h": src["h"],
                    "source": "diffusion", "boxes": src["boxes"], "source_id": src["id"],
                    "seed": gseed, "generator": generator, "control": cfg["control"],
                    "control_scale": cfg["control_scale"], "steps": cfg["steps"],
                    "resolution": params["width"], "prompt": cfg["prompt"],
                    "negative": cfg["negative"], "qa": qa})
        print(f"[gen] {k + 1}/{n} {rid} edge_f1={qa['edge_f1']} accepted={qa['accepted']}")
    write_records(out_pool, out)
    free_vram(s.comfy_url)
    accepted = sum(1 for r in out if r["qa"]["accepted"])
    rejected = {k: sum(1 for r in out if not r["qa"][k]) for k in
                ("edge_ok", "global_ok", "pseudo_ok", "no_new_ok")}
    status = {**base, "status": "ok" if out else "failed", "generator": generator, "why": why,
              "generated": len(out), "accepted": accepted, "failed_checks": rejected,
              "settings": {k: cfg[k] for k in cfg if k.startswith(("qa_", "krea2_", "resolution", "steps"))},
              "errors": errors[:10],
              "seconds": round(time.time() - t0, 1), "comfy": comfy_summary(stats),
              "qa_pseudo_classes": allowed,
              "e1_reason": (f"{len(out)} conditional images ({accepted} accepted) with {generator}; "
                            "E1 with the target generator (FLUX.1-dev) is planned on the 3090"
                            if out else f"generation failed: {errors[:1]}")}
    return _write_status(profile, status)
