# Datasets

A profile names one dataset (`dataset:` key); `configs/datasets/<name>.yaml` pins the
source, revision, checksums, class map and frozen split lists. Train and val always
come from that single dataset.

| | main: `csafety` | archived: `hardhat` (v0.1) |
|---|---|---|
| Name | construction-safety, Roboflow 100 ("construction safety - v1 release-640") | hard-hat-detection (FiftyOne export of *Hard Hat Workers*) |
| Hub id | [`Francesco/construction-safety-gsnvb`](https://huggingface.co/datasets/Francesco/construction-safety-gsnvb) | [`Voxel51/hard-hat-detection`](https://huggingface.co/datasets/Voxel51/hard-hat-detection) |
| Pinned revision | `cd92c83884cc7c0ba1a3fda584784f550321e16f` | `d11e7d6b69ba1a22422db3230c0415d39a699d7c` |
| License | **CC BY 4.0** (Roboflow 100; the HF card tags it `license:cc`) — attribution required | CC0-1.0 (dataset card) |
| Size | 1206 JPEGs, 640×640 (stretched by Roboflow), no augmentation | 5000 PNGs, ~416×416 |
| Source labels | helmet, no-helmet, person, vest, no-vest (+ empty super-category) | helmet, head, person |
| Box counts | person 2817, helmet 2543, no-helmet 129, vest 1343, no-vest 892 | helmet 18966, head 5785, person 751 |
| Splits | val 300 / seed 906 (all images used) | val 1000 / seed 1000 (3000 unused) |

## Why the main dataset changed

The first dataset labels people sparsely: 751 person boxes over 5000 images, while
most visible people carry no box. Person AP was 0–0.5 in every experiment and Z0 showed
why (the COCO detector found 56.5% of labeled people yet scored 1.4 AP50, because its
other detections hit unboxed people). Person numbers measured label coverage, not the
factory. construction-safety boxes every worker (person ≈ helmet count; only 17 of 1206
images have no person box), so both MVP classes are measurable. It is small, which is
why the MVP profile cannot reach the design's 1000 + 1000 and uses 906 + 300.

The archived runs stay in `runs/smoke_hardhat/` and `runs/mvp_hardhat/`, and can be
reproduced with `--profile smoke_hardhat` / `--profile mvp_hardhat`.

## Download

```bash
synthguard download                    # main dataset, profile `smoke`
synthguard download --profile mvp_hardhat
```

- `csafety`: three parquet shards (train / validation / test as published), each checked
  against a pinned SHA-256 in `configs/datasets/csafety.yaml`. Original JPEG bytes are
  written to `<SYNTHGUARD_DATA_ROOT>/public/csafety/images/<id>.jpg` without re-encoding.
  Ids are the source file stem (`ppe_0062`), unique across all shards. The numeric
  `image_id` column is **not** unique across shards and is not used.
- `hardhat`: `samples.json` (SHA-256 checked) plus only the PNGs the profile needs.

Both are re-entrant. After each download, five image hashes from
`configs/splits/<dataset>/checksums_sample.txt` are compared. Set `HF_ENDPOINT` in
`.env` to use a mirror.

## Class maps

`configs/class_map_csafety.yaml`:

```yaml
train_classes: [person, helmet, head]
eval_classes: [person, helmet]
map: {person: person, helmet: helmet, no-helmet: head}
ignore: [vest, no-vest, construction-safety]
```

`head` (a bare head, from `no-helmet`) is a mapped auxiliary class, not in the main
table (design §2.1). Vests are out of MVP scope and are dropped explicitly. Unknown labels
raise instead of being dropped silently (`tests/test_class_map.py` covers both datasets).

## Splits

`configs/splits/<dataset>/{val_list,train_seed_list}.txt` are frozen and committed.
Ids are ordered by `sha1("synthguard-v1:<id>")`, so any prefix is a uniform random
subset (the csafety smoke profile uses the first 300 seed ids and the full val list).
The published train/validation/test partition is pooled before hashing so val
can reach 300 images (validation + test would give only 209).

- Augmentation, copy-paste and diffusion only ever read seed images.
- `export_yolo.check_no_val_leak` refuses any val record that is not real, and any
  train record that is, or is derived from, or pastes an instance from, a val image.

## Known quirks

- csafety: images were stretched to 640×640 by Roboflow, so aspect ratios are distorted
  the same way in train and val. `no-helmet` is rare (24 boxes on val).
- hardhat: sparse person labels (above); many images padded with mirrored borders.
