# SynthGuard compare · `mvp`

Model `yolo11n.pt`, 60 epochs, imgsz 640, identical hyper-parameters and the same fixed real val split for every row. mAP50 = mean AP50 over person, helmet. Values ×100; ± is half the min–max range across seeds (E0: seeds [0, 1], E2: seeds [0, 1]).

| exp | data | mAP50 | AP50 person | AP50 helmet | mAP50-95 | Δ mAP50 vs E0 |
|---|---|---:|---:|---:|---:|---:|
| E0 | real seed only | 95.5 ±0.1 | 95.9 ±0.6 | 95.0 ±0.4 | 59.7 ±0.4 | — |
| E2 | seed + classic aug + copy-paste (no diffusion) | 94.9 ±0.2 | 95.1 ±0.1 | 94.7 ±0.4 | 58.3 ±0.3 | -0.5 |
| E1 | seed + full factory output (incl. diffusion) | skipped | — | — | — | — |

E1 skipped: SKIP_DIFFUSION=1.

**Where it wins.** Nowhere at this scale. Without any generation, E2 changes mAP50 by -0.5 over E0.
**Where it loses.** Classes not improved by E2: person -0.7, helmet -0.3. Box tightness drops: mAP50-95 -1.4 vs E0. Gains on this public domain do not transfer automatically to other cameras; the val split is fixed and contains no synthetic or derived images.
**Next.** E1 is pending: SKIP_DIFFUSION=1. Next: soften the strongest ops (blur/fog) and check paste scale priors before adding volume.

<sub>env: ultralytics 8.4.197, torch 2.11.0+cu128 (CUDA 12.8), NVIDIA GeForce RTX 5070, Python 3.12.13. Generated from `runs/mvp/E*_s*/metrics.json` by `synthguard compare`.</sub>
