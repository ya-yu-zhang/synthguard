# SynthGuard compare · `smoke`

Model `yolo11n.pt`, 30 epochs, imgsz 640, identical hyper-parameters and the same fixed real val split for every row. mAP50 = mean AP50 over person, helmet. Values ×100; ± is half the min–max range across seeds (E0: seeds [0, 1], E2: seeds [0, 1]).

| exp | data | mAP50 | AP50 person | AP50 helmet | mAP50-95 | Δ mAP50 vs E0 |
|---|---|---:|---:|---:|---:|---:|
| E0 | real seed only | 94.5 ±0.3 | 95.5 ±0.4 | 93.5 ±0.2 | 57.6 ±0.4 | — |
| E2 | seed + classic aug + copy-paste (no diffusion) | 94.4 ±0.3 | 95.5 ±0.7 | 93.3 ±0.0 | 56.7 ±0.8 | -0.1 |
| E1 | seed + full factory output (incl. diffusion) | skipped | — | — | — | — |

E1 skipped: SKIP_DIFFUSION=1.

**Where it wins.** Nowhere at this scale. Without any generation, E2 changes mAP50 by -0.1 over E0. That is within noise (seed spread, or under 0.5 points with only two seeds), so read it as no change.
**Where it loses.** Classes not improved by E2: person -0.0, helmet -0.1. Box tightness drops: mAP50-95 -0.9 vs E0. Gains on this public domain do not transfer automatically to other cameras; the val split is fixed and contains no synthetic or derived images.
**Next.** E1 is pending: SKIP_DIFFUSION=1. Next: soften the strongest ops (blur/fog) and check paste scale priors before adding volume.

<sub>env: ultralytics 8.4.197, torch 2.11.0+cu128 (CUDA 12.8), NVIDIA GeForce RTX 5070, Python 3.12.13. Generated from `runs/smoke/E*_s*/metrics.json` by `synthguard compare`.</sub>
