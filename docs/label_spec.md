# Label spec

| class | id | definition | in main table |
|---|---|---|---|
| person | 0 | a visible human body (any extent) | yes |
| helmet | 1 | a hard hat / safety helmet being worn, box around the helmet (head-level) | yes |
| head | 2 | a head without a hard hat, box around the head | no (auxiliary) |

Boxes are axis-aligned, absolute pixel `xyxy` internally, YOLO-normalized on export.

Factory rules:

- **Classic augmentation** propagates boxes through the same geometric transform;
  boxes with < 40% visibility after cropping are dropped by albumentations.
- **Copy-paste** carries every box that is ≥ 90% inside the crop; an instance is not
  banked if its crop would cut any other box that does not enclose it. A paste may
  cover at most 25% of an existing box.
- **Diffusion** reuses the source image's boxes (layout is fixed by Canny conditioning)
  and must pass QA: edge agreement inside boxes, plus a pseudo-label re-detection
  check for classes allowed by Z0.
- **Automatic QA** (all factory pools): clip to image, drop boxes < 3 px side or
  < 16 px², drop boxes > 95% of the image, remove same-class duplicates (IoU > 0.9).

Manual review notes (design §5.2) record only the error type and the action taken
(threshold, prompt, preset dropped) — never places or names.
