# SynthGuard compare · `smoke_hardhat`

Model `yolo11n.pt`, 30 epochs, imgsz 416, identical hyper-parameters and the same fixed real val split for every row. mAP50 = mean AP50 over person, helmet. Values ×100; ± is half the min–max range across seeds (E0: seeds [0, 1], E2: seeds [0, 1]).

| exp | data | mAP50 | AP50 person | AP50 helmet | mAP50-95 | Δ mAP50 vs E0 |
|---|---|---:|---:|---:|---:|---:|
| E0 | real seed only | 44.0 ±0.2 | 0.3 ±0.2 | 87.7 ±0.3 | 27.1 ±0.0 | — |
| E2 | seed + classic aug + copy-paste (no diffusion) | 43.7 ±0.3 | 0.0 ±0.0 | 87.3 ±0.5 | 27.2 ±0.2 | -0.3 |
| E1 | seed + full factory output (incl. diffusion) | skipped | — | — | — | — |

E1 skipped: weights missing: flux (flux1-dev-fp8.safetensors, clip_l+t5, ae.safetensors, flux1-canny-dev-lora.safetensors), sdxl proxy (sd_xl_base_1.0.safetensors, controlnet-canny-sdxl-1.0.safetensors).

**Where it wins.** Nowhere at this scale. Without any generation, E2 changes mAP50 by -0.3 over E0. That is within noise (seed spread, or under 0.5 points with only two seeds), so read it as no change.
**Where it loses.** Classes not improved by E2: person -0.2, helmet -0.3. person stays below 5 AP50 in every row: the source labels this class sparsely (most visible people are unboxed, see docs/dataset.md), so detections of unlabeled people count as false positives and the class mostly measures label coverage, not the factory. Gains on this public domain do not transfer automatically to other cameras; the val split is fixed and contains no synthetic or derived images.
**Next.** E1 is pending: weights missing: flux (flux1-dev-fp8.safetensors, clip_l+t5, ae.safetensors, flux1-canny-dev-lora.safetensors), sdxl proxy (sd_xl_base_1.0.safetensors, controlnet-canny-sdxl-1.0.safetensors). Next: soften the strongest ops (blur/fog) and check paste scale priors before adding volume.

<sub>env: ultralytics 8.4.197, torch 2.11.0+cu128 (CUDA 12.8), NVIDIA GeForce RTX 5070, Python 3.12.13. Generated from `runs/smoke_hardhat/E*_s*/metrics.json` by `synthguard compare`.</sub>
