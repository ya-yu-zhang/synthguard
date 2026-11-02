import numpy as np

from synthguard.copy_paste import bank_instances, feather_mask
from synthguard.metrics import ap50_per_class
from synthguard.qa_filter import filter_record


def test_bank_skips_instances_that_cut_other_objects():
    rec = {"id": "x", "w": 100, "h": 100, "boxes": [
        {"cls": "person", "xyxy": [10, 10, 50, 90]},
        {"cls": "helmet", "xyxy": [20, 10, 35, 22]},   # fully inside the person -> travels along
        {"cls": "head", "xyxy": [45, 40, 70, 60]},     # straddles the person crop edge
    ]}
    bank = bank_instances([rec])
    assert "person" not in bank  # cutting the head in half would leave an unlabeled fragment
    assert bank["helmet"][0]["inner"] == []


def test_bank_carries_inner_boxes():
    rec = {"id": "x", "w": 100, "h": 100, "boxes": [
        {"cls": "person", "xyxy": [10, 10, 50, 90]},
        {"cls": "helmet", "xyxy": [20, 12, 35, 24]},
    ]}
    (p,) = bank_instances([rec])["person"]
    assert [b["cls"] for b in p["inner"]] == ["helmet"]


def test_feather_mask_range():
    m = feather_mask(40, 30)
    assert m.shape == (40, 30, 1) and 0 <= m.min() and m.max() <= 1


def test_qa_drops_degenerate_and_duplicates():
    rec = {"w": 100, "h": 100, "boxes": [
        {"cls": "helmet", "xyxy": [10, 10, 30, 30]},
        {"cls": "helmet", "xyxy": [10, 10, 30, 30.5]},
        {"cls": "helmet", "xyxy": [50, 50, 51, 51]},
    ]}
    out, why = filter_record(rec)
    assert len(out["boxes"]) == 1 and why["duplicate"] == 1 and why["too_small"] == 1


def test_ap50_perfect_and_empty():
    gts = [[("helmet", [0, 0, 10, 10])], [("helmet", [5, 5, 20, 20])]]
    perfect = [[("helmet", 0.9, [0, 0, 10, 10])], [("helmet", 0.8, [5, 5, 20, 20])]]
    assert ap50_per_class(perfect, gts, ["helmet"])["helmet"]["ap50"] == 1.0
    assert ap50_per_class([[], []], gts, ["helmet"])["helmet"]["ap50"] == 0.0
    half = [[("helmet", 0.9, [0, 0, 10, 10])], [("helmet", 0.95, [50, 50, 60, 60])]]
    assert 0.0 < ap50_per_class(half, gts, ["helmet"])["helmet"]["ap50"] < 1.0


def test_augment_ops_fire_independently():
    """Regression: equal-p ops must not fire all-or-nothing under per-image seeding."""
    from collections import Counter

    from synthguard.augment_classic import applied_ops, build_pipeline, reseed
    from synthguard.records import load_yaml

    pipe = build_pipeline(load_yaml("augment"))
    img = np.random.RandomState(0).randint(0, 255, (64, 64, 3), np.uint8)
    combos, empty = Counter(), 0
    for s in range(120):
        reseed(pipe, s)
        ops = applied_ops(pipe(image=img, bboxes=[[5, 5, 40, 40]], cls=["helmet"])["replay"])
        combos[("HorizontalFlip" in ops, "Affine" in ops, "RandomBrightnessContrast" in ops)] += 1
        empty += not ops
    assert len(combos) >= 6
    assert empty < 20


def test_paste_scale_skips_instead_of_clamping():
    """Regression: a close-up helmet must not be shrunk-to-the-limit into a wide shot."""
    import random

    from synthguard.copy_paste import SCALE_RANGE, _scale_for

    rng = random.Random(0)
    closeup = {"box": {"cls": "helmet", "xyxy": [0, 0, 300, 300]}}
    wide_bg = {"boxes": [{"cls": "helmet", "xyxy": [10, 10, 40, 40]}]}  # 30 px helmets
    assert all(_scale_for(closeup, wide_bg, rng) is None for _ in range(50))
    no_ref = {"boxes": []}
    assert _scale_for(closeup, no_ref, rng) is None
    fitting = {"box": {"cls": "head", "xyxy": [0, 0, 30, 30]}}  # head shares the helmet group
    s = _scale_for(fitting, wide_bg, rng)
    assert s is not None and SCALE_RANGE[0] <= s <= SCALE_RANGE[1]
