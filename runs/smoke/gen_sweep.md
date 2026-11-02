# Krea 2 img2img denoise sweep (smoke profile, dev machine)

8 seed images (same sources and sampler seed for every strength), Krea 2 Turbo nvfp4, 8 steps, 768 px.
QA thresholds were set *after* this sweep; the `accepted` column below used the provisional
values (in-box edge ≥ 0.25, global edge ≥ 0.45, COCO person re-detection, no extra confident person).

| denoise | mean in-box edge F1 | mean global edge F1 | images with new unlabeled person | person re-found (per image) | accepted (provisional QA) |
|---:|---:|---:|---:|---|---:|
| 0.20 | 0.874 | 0.872 | 1 / 8 | 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0 | 7 / 8 |
| 0.30 | 0.803 | 0.800 | 2 / 8 | 0.5, 1.0, 0.5, 1.0, 1.0, 1.0, 0.25, 0.667 | 6 / 8 |
| 0.35 | 0.762 | 0.760 | 3 / 8 | 0.5, 1.0, 1.0, 0.5, 1.0, 1.0, 0.25, 0.667 | 5 / 8 |
| 0.45 | 0.707 | 0.648 | 5 / 8 | 0.0, 1.0, 0.5, 1.0, 1.0, 1.0, 0.25, 0.0 | 2 / 8 |

Visual review of the same grid: at 0.30 and above the model adds background workers that
carry no box (some too small for the person detector to flag); at 0.45 whole scenes are
re-imagined. Chosen: **denoise 0.25**, in-box edge ≥ 0.60, global edge ≥ 0.75. Without a
control net this generator can only re-render appearance, not vary layout.
