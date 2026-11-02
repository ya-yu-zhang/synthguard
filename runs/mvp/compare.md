# SynthGuard compare · `mvp`

Model `yolo11n.pt`, 60 epochs, imgsz 640, identical hyper-parameters and the same fixed real val split for every row. mAP50 = mean AP50 over person, helmet. Values ×100; ± is half the min–max range across seeds (E0: seeds [0, 1], E1: seeds [0, 1], E2: seeds [0, 1]).

| exp | data | mAP50 | AP50 person | AP50 helmet | mAP50-95 | Δ mAP50 vs E0 |
|---|---|---:|---:|---:|---:|---:|
| E0 | real seed only | 95.5 ±0.1 | 95.9 ±0.6 | 95.0 ±0.4 | 59.7 ±0.4 | — |
| E2 | seed + classic aug + copy-paste (no diffusion) | 95.1 ±0.2 | 95.7 ±0.6 | 94.5 ±0.2 | 58.9 ±0.1 | -0.3 |
| E1 | seed + full factory output (incl. diffusion) | 94.8 ±0.5 | 95.2 ±0.6 | 94.4 ±0.4 | 58.9 ±0.6 | -0.7 |

E1 diffusion: `krea2_img2img_dev_proxy`, 362 of 520 generated images passed QA. This is a dev-machine stand-in, not the target FLUX.1-dev stack.

**Where it wins.** Nowhere at this scale. Without any generation, E2 changes mAP50 by -0.3 over E0. That is within noise (seed spread, or under 0.5 points with only two seeds), so read it as no change.
**Where it loses.** Classes not improved by E2: person -0.1, helmet -0.5. Box tightness drops: mAP50-95 -0.8 vs E0. Gains on this public domain do not transfer automatically to other cameras; the val split is fixed and contains no synthetic or derived images.
**Next.** E1 is -0.7 vs E0; keep diffusion within the ≤50% increment cap. Next: soften the strongest ops (blur/fog) and check paste scale priors before adding volume.

<sub>env: ultralytics 8.4.197, torch 2.11.0+cu128 (CUDA 12.8), NVIDIA GeForce RTX 5070, Python 3.12.13. Generated from `runs/mvp/E*_s*/metrics.json` by `synthguard compare`.</sub>
