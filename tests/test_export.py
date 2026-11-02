import pytest

from synthguard.class_map import class_ids, load_class_map
from synthguard.records import load_yaml
from synthguard.export_yolo import ValLeakError, check_no_val_leak, yolo_lines


def test_yolo_lines_normalized():
    rec = {"w": 400, "h": 200, "boxes": [{"cls": "helmet", "xyxy": [100, 50, 200, 150]}]}
    (line,) = yolo_lines(rec, class_ids(load_class_map("class_map_csafety.yaml")))
    cid, cx, cy, w, h = line.split()
    assert cid == "1"
    assert float(cx) == pytest.approx(0.375) and float(cy) == pytest.approx(0.5)
    assert float(w) == pytest.approx(0.25) and float(h) == pytest.approx(0.5)


def _r(i, source="real", **kw):
    return {"id": i, "source": source, **kw}


def test_val_must_be_real():
    with pytest.raises(ValLeakError):
        check_no_val_leak([], [_r("a", "augment")])


def test_train_cannot_contain_val_or_derivatives():
    val = [_r("v1")]
    with pytest.raises(ValLeakError):
        check_no_val_leak([_r("v1")], val)
    with pytest.raises(ValLeakError):
        check_no_val_leak([_r("aug_v1", "augment", source_id="v1")], val)
    with pytest.raises(ValLeakError):
        check_no_val_leak([_r("p", "paste", source_id="t1", pastes=[{"instance_from": "v1"}])], val)
    check_no_val_leak([_r("t1"), _r("aug_t1", "augment", source_id="t1")], val)


@pytest.mark.parametrize("ds", ["hardhat", "csafety"])
def test_committed_splits_are_disjoint(ds):
    from synthguard.records import read_list

    cfg = load_yaml(f"datasets/{ds}.yaml")
    val, seed = set(read_list(cfg["val_list"])), set(read_list(cfg["seed_list"]))
    sizes = cfg.get("split_sizes", {"val": 1000, "seed": 1000})
    assert len(val) == sizes["val"] and len(seed) == sizes["seed"] and not val & seed
