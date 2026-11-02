# Deploy: dual RTX 3090 (24 GB × 2)

The dev machine (single 12 GB GPU) delivers the diffusion-free story (E0/E2) and a
working ComfyUI adapter. The deploy machine runs the full conditional generation
with FLUX.1-dev and the formal E1. **Machine-specific values live in `.env`.** The one
possible exception is the Krea 2 model file name in `configs/gen_deploy_3090.yaml` (see
step 6 below).

## GPU layout

| GPU | process | how |
|---|---|---|
| 0 | ComfyUI (FLUX.1-dev + control) | start Comfy with `CUDA_VISIBLE_DEVICES=0` |
| 1 | YOLO training / pseudo-labeler | `TRAIN_DEVICES=1` in `.env` |

synthguard never exports `CUDA_VISIBLE_DEVICES` into its own process; it passes
`TRAIN_DEVICES` to ultralytics as the device index. Do **not** set
`CUDA_VISIBLE_DEVICES=0` in the shell that runs `synthguard`, or GPU 1 becomes invisible.

Starting Comfy on GPU 0 (Linux example; Windows: `set CUDA_VISIBLE_DEVICES=0`):

```bash
CUDA_VISIBLE_DEVICES=0 python main.py --listen 127.0.0.1 --port 8188
```

## `.env` on the deploy machine

```env
COMFY_URL=http://127.0.0.1:8188
COMFY_ROOT=<comfy root on the 3090 machine>
SKIP_DIFFUSION=0
CUDA_VISIBLE_DEVICES=0
TRAIN_DEVICES=1
SYNTHGUARD_DATA_ROOT=<large data disk>/synthguard-data
GEN_PROFILE=deploy_3090
```

`configs/gen_deploy_3090.yaml`: 1024 px, 28 steps, depth control at 0.65, no low-VRAM
mode, `fallback_sdxl: false` (the proxy is a dev-only stand-in and must not produce E1).

## Weights (place under `<COMFY_ROOT>/ComfyUI/models/`)

| file (as in `gen_deploy_3090.yaml`) | folder | source |
|---|---|---|
| `flux1-dev.safetensors` | `diffusion_models/` | https://huggingface.co/black-forest-labs/FLUX.1-dev (gated; accept the license) |
| `ae.safetensors` | `vae/` | same repo |
| `clip_l.safetensors`, `t5xxl_fp16.safetensors` | `text_encoders/` | https://huggingface.co/comfyanonymous/flux_text_encoders |
| `flux1-depth-dev-lora.safetensors` | `loras/` | https://huggingface.co/black-forest-labs/FLUX.1-Depth-dev-lora (gated) |

The shipped workflow template is Canny (`comfy/workflows/flux_canny_lora_api.json`).
For depth control, export the official Comfy depth example in API format into
`comfy/workflows/`, add it to `gen_client.WORKFLOWS`, and keep the same placeholders.
Record every file's SHA-256 in `REPRO.md`.

**License:** FLUX.1-dev and its control LoRAs are under the FLUX.1 [dev] Non-Commercial
License. Images generated with them may not be packaged or sold as a commercial
dataset. SynthGuard's own code is Apache-2.0; that does not change the weights' terms.

## Migration checklist (dev → deploy)

### What moves, what does not

| item | move? | how |
|---|---|---|
| repository (`src/ configs/ comfy/ tests/ docs/ scripts/ runs/*.md`, lock file) | yes | `git` (internal remote) or a folder copy without the excluded items |
| `.venv/` (4.8 GB) | **no** | rebuild from `requirements.lock.txt`; venvs are not relocatable |
| `.env` | **no** | write a new one from `.env.example` |
| `data/public`, `data/pools`, `data/yolo`, `data/weights` | no | re-created by `download` / the pipeline (checksummed) |
| `data/scenes/<batch>/` (generated scenes, unlabeled) | yes, if labeling continues there | copy the folder as is |
| internal substation validation images | never via the repo | internal machines only, outside the repository |
| Comfy weights (`.safetensors`) | yes | copy or re-download into the 3090's Comfy `models/` |

Folder copy on Windows (excludes environment, data and machine config):

```powershell
robocopy <src>\synthguard <dst>\synthguard /E /XD .venv data node_modules .pytest_cache __pycache__ /XF .env
robocopy <src>\synthguard\data\scenes <dst>\synthguard-data\scenes /E   # optional
```

### Steps

The web UI (`synthguard ui`, tab **环境**) shows the same steps with live checks, and can
export `.env` on the old machine and import it on the new one (paths still need editing).

1. Copy the repository as above. Python 3.12 and `uv` on the 3090 machine.
2. Create the environment exactly as in `REPRO.md` (same lock file). The cu128 torch
   wheel also supports Ampere (sm_86); check with
   `python -c "import torch; print(torch.cuda.device_count(), torch.cuda.get_device_name(1))"`
   → `2`, `NVIDIA GeForce RTX 3090`.
3. `cp .env.example .env` and set the variables above (`GEN_PROFILE=deploy_3090`,
   `TRAIN_DEVICES=1`, `SYNTHGUARD_DATA_ROOT` on the data disk).
4. `pytest -q` — must pass (includes the "no absolute paths in src" check).
5. ComfyUI on GPU 0, a version with Krea 2 support (`CLIPLoader` type `krea2`; the dev
   machine reports ComfyUI 0.33.1). Copy the three Krea 2 files listed under
   `weights.krea2` in `gen_deploy_3090.yaml`:
   `diffusion_models/krea2_turbo_nvfp4.safetensors`, `clip/qwen3vl_4b_fp8_scaled.safetensors`,
   `vae/qwen_image_vae.safetensors`. Compare each copy with the SHA-256 in `REPRO.md` §6
   (`certutil -hashfile <file> SHA256` on Windows, `sha256sum <file>` on Linux).
   `synthguard probe-comfy` must answer.
6. Scenes first (the current deliverable):
   `synthguard scenes --spec substation --n 20 --batch deploy_check`. Open the contact
   sheet; if nvfp4 fails or is very slow on the 3090, switch `weights.krea2.unet` to an
   fp8/bf16 Krea 2 Turbo checkpoint and rerun. Record the per-image time in `REPRO.md`.
7. Detection pipeline check: `synthguard download --profile smoke` (spot check `ok`),
   then `synthguard smoke --profile smoke` with `SKIP_DIFFUSION=1`; E0/E2 should land
   within seed noise of `runs/smoke/compare.md`.
8. Formal E1 (only once FLUX.1-dev weights are in place): `probe-comfy` must report
   `flux1-dev`; `synthguard gen --profile mvp --n 16`, eyeball 30 images per class
   (design §5.2), calibrate `qa_global_edge_f1_min` on that sample, then full generation
   within the cap (diffusion ≤ 50% of the increment, enforced in export),
   `synthguard train E1 --profile mvp`, `synthguard compare --profile mvp`.
   If E1 drops > 2.0 mAP50 vs E0: stop adding diffusion, keep E2 as the recommended
   configuration, and say so in the README.

### Sharing the web UI with colleagues

`synthguard ui` binds to 127.0.0.1 by default. On the deploy machine:

```bash
.venv\Scripts\python -m synthguard ui --host 0.0.0.0      # Linux: .venv/bin/python
```

- Colleagues open `http://<machine name or IP>:8765/`. Requests that use a DNS name other
  than the machine's own name are refused (DNS-rebinding protection). Add an alias with
  `--allow-host gpu3090.example.local`; IP addresses always work.
- Open TCP 8765 for the internal network only, e.g. Windows (admin):
  `netsh advfirewall firewall add rule name="SynthGuard UI" dir=in action=allow protocol=TCP localport=8765 remoteip=localsubnet`
- Anyone who can reach the page can start and stop jobs and mark images; only a browser
  on the machine itself can change `.env`. There is no login, so never expose the port
  outside the office network.
- The UI stops when its window closes. To survive logoff or reboot, run it from Task
  Scheduler (Windows) or a systemd service (Linux); ComfyUI needs the same.

### Two Comfy instances for scene batches (optional)

`scenes` only needs Comfy, so both GPUs can generate when no training runs. Start a
second Comfy with `CUDA_VISIBLE_DEVICES=1 ... --port 8189` and point a second
`synthguard` process at it; environment variables override `.env`:

```powershell
synthguard scenes --spec substation --n 500 --batch batch02a --seed 2
$env:COMFY_URL="http://127.0.0.1:8189"; synthguard scenes --spec substation --n 500 --batch batch02b --seed 3
```

Use a different `--seed` per process; generation seeds are `seed × 1000003 + k`, so
batches never repeat. Stop the second instance before training on GPU 1.

## Optional Phase 2 (Gate D)

Flux LoRA + mask inpainting for localized edits — only after E2 is stable and E1 has
been measured. Not part of the MVP.
