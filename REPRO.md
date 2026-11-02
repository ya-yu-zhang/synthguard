# REPRO — reproduce the smoke run on a second machine

Everything machine-specific lives in `.env`. Nothing in `src/` or `configs/` contains
an absolute path (enforced by `tests/test_no_abs_paths.py`).

## 1. Reference machine (where the committed `runs/smoke/` came from)

| | |
|---|---|
| OS | Windows 11 Pro 10.0.26100 |
| CPU / RAM | 8-core desktop CPU / 32 GB |
| GPU | NVIDIA GeForce RTX 5070, 12 GB |
| Driver | 616.92 |
| CUDA (torch wheel) | 12.8 (`torch 2.11.0+cu128`) |
| Python | 3.12.13 |
| Key packages | ultralytics 8.4.197, albumentations 2.0.8, opencv 5.0.0.93, numpy 2.5.4 |

RTX 50-series (Blackwell) needs a CUDA ≥ 12.8 torch wheel; older wheels fail with
"no kernel image".

## 2. Environment

```bash
uv venv .venv --python 3.12
uv pip install -p .venv -r requirements.lock.txt --extra-index-url https://download.pytorch.org/whl/cu128 --index-strategy unsafe-best-match
uv pip install -p .venv -e . --no-deps
cp .env.example .env        # then edit paths / devices
```

`requirements.lock.txt` is the full `uv pip freeze` of the reference environment
(SHA-256 `9de7392e8a0af156f937ea0ed2e6f10ce12348c0df54e2676d26307bdbe300f2`).
Regenerate it only when deliberately upgrading.

CPU-only minimum: download, augment, paste, stats, export and compare run without a
GPU (`TRAIN_DEVICES=cpu`). Training works on CPU but is slow; treat it as GPU-only.

## 3. Data

| | |
|---|---|
| Main dataset | `Francesco/construction-safety-gsnvb` @ `cd92c83884cc7c0ba1a3fda584784f550321e16f` (Roboflow 100 construction-safety) |
| License | CC BY 4.0 (attribution in `DATA_LICENSE`) |
| Download | `synthguard download` (re-entrant; all 1206 images, 147 MB on disk) |
| Shard checksums | SHA-256 of all three parquet shards pinned in `configs/datasets/csafety.yaml`, verified on every download |
| Spot check | 5 image hashes in `configs/splits/csafety/checksums_sample.txt`, compared after every download |
| Splits | `configs/splits/csafety/{val_list,train_seed_list}.txt` (300 / 906, committed, frozen) |
| Archived dataset | `Voxel51/hard-hat-detection` @ `d11e7d6b…` (CC0-1.0), `configs/datasets/hardhat.yaml`, profiles `smoke_hardhat` / `mvp_hardhat` |

Pretrained weights fetched by ultralytics into `<SYNTHGUARD_DATA_ROOT>/weights/`:

| file | SHA-256 |
|---|---|
| `yolo11n.pt` | `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1` |
| `yolov8s-worldv2.pt` | `9b2c17ab6124a913e9b3a5c170617920d91b0f01111a8479da69f00e2cf27792` |

`YOLO_AUTOINSTALL` is forced to `false` by the CLI so ultralytics never pip-installs
packages outside the lock. Consequence on the reference machine: the open-vocabulary
labeler needs the `clip` package (`git+https://github.com/ultralytics/CLIP.git`), which
is not in the lock, so Z0 records it as failed and uses the closed-set fallback.
Install CLIP deliberately if you want the open-vocabulary Z0.

## 4. Run

```bash
synthguard smoke
```

(`scripts/run_smoke.ps1` / `scripts/run_smoke.sh` run `pytest` first, then the same
command, and print the wall clock.)

Expected: `runs/smoke/compare.md` with E0 ≈ 94.5 and E2 ≈ 94.4 mAP50, within roughly
±1 of the committed file (GPU kernels are not bit-exact across cards/drivers even with
`deterministic=True`), stats quota `OK`, E1 `skipped` unless ComfyUI is configured.

## 5. Cost (measured on the reference machine)

Measured once each, 2026-11-01, main dataset, `SKIP_DIFFUSION=1`, images and weights
already cached:

| | smoke (`run_smoke.ps1`) | MVP (`run_mvp.ps1`) |
|---|---|---|
| Wall clock (pytest + loop) | **10.5 min** | **30.9 min** |
| Per training run | E0 97–132 s, E2 130–171 s (30 epochs, 640 px) | E0 299–327 s, E2 526–597 s (60 epochs, 640 px) |
| Factory pools on disk | 180 MB | 544 MB |
| Expected numbers | E0 94.5 / E2 94.4 mAP50 | E0 95.5 / E2 95.1 mAP50; quota OK (person 2302 / 500, helmet 2339 / 500) |

Shared: `.venv` 4.7 GB (mostly the CUDA torch wheel); dataset 147 MB plus ~30 MB of
detector weights on first download. The archived hard-hat runs took 8.4 min (smoke)
and 30.4 min (MVP, 1000 + 1000 at 416 px) on the same machine.

## 6. ComfyUI (optional diffusion)

Dev machine status: ComfyUI 0.33.1, launched by the dev machine's Comfy launcher. No
Flux, SDXL or ControlNet weights are installed, so the target FLUX.1-dev stack is not
run here. Krea 2 Turbo is installed and used for two things:

| use | generator | measured on the RTX 5070 |
|---|---|---|
| MVP E1 stand-in (img2img, strength 0.25, 8 steps) | `krea2_img2img_dev_proxy` | 520 generated, 362 passed QA (`runs/mvp/gen_status.json`) |
| scene batches for manual labeling (text-to-image, 8 steps) | `krea2_t2i` | `batch01`: 50 images in 598 s, 12.0 s per image |

Krea 2 weights (folder under Comfy `models/`, file name as in `configs/gen_*.yaml`
`weights.krea2`), so a copy on another machine can be verified:

| folder | file | bytes | SHA-256 |
|---|---|---:|---|
| `diffusion_models/` | `krea2_turbo_nvfp4.safetensors` | 7,673,668,448 | `61527003b2d537055494d01bc8efe51d6e86e64192ba23e3721a5647231fe394` |
| `clip/` | `qwen3vl_4b_fp8_scaled.safetensors` | 5,242,467,968 | `54bd5144df0bbc25dd6ccadfcb826b521445a1b06ae5a42570bdd2974ca87094` |
| `vae/` | `qwen_image_vae.safetensors` | 253,806,246 | `a70580f0213e67967ee9c95f05bb400e8fb08307e017a924bf3441223e023d1f` |

Check a copy with `certutil -hashfile <file> SHA256` (Windows) or `sha256sum <file>` (Linux).
The Krea 2 weights' license terms for company use have not been confirmed; check them
before producing data at scale.

When enabling further generators, record here:

- ComfyUI version (commit) and every custom node used (repo + commit). The shipped
  workflows (`comfy/workflows/*.json`) use **core nodes only** (`Canny`,
  `ControlNetApplyAdvanced`, `InstructPixToPixConditioning`, `FluxGuidance`, …).
- Each weight file name (as in `configs/gen_*.yaml`) and its SHA-256.
- Comfy launch flags (dev: `--lowvram`).

Check with `synthguard probe-comfy`; it prints which generator would be used and why.
