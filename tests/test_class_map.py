import pytest

from synthguard.class_map import (MVP_CLASSES, UnmappedLabelError, class_ids, load_class_map,
                                  map_label, validate_class_map)
from synthguard.records import load_yaml

# every label present in each pinned source
SOURCE_LABELS = {
    "hardhat": {"person", "helmet", "head"},
    "csafety": {"construction-safety", "helmet", "no-helmet", "no-vest", "person", "vest"},
}


def _cmap(ds):
    return load_class_map(load_yaml(f"datasets/{ds}.yaml")["class_map"])


@pytest.mark.parametrize("ds", sorted(SOURCE_LABELS))
def test_map_is_valid_and_covers_mvp(ds):
    cmap = _cmap(ds)
    assert set(MVP_CLASSES) <= set(cmap["map"].values())
    assert cmap["eval_classes"] == ["person", "helmet"]


@pytest.mark.parametrize("ds", sorted(SOURCE_LABELS))
def test_every_source_label_is_mapped_or_ignored(ds):
    cmap = _cmap(ds)
    for lab in SOURCE_LABELS[ds]:
        map_label(lab, cmap)  # raises if silently unknown


def test_csafety_label_list_matches_test_fixture():
    assert set(load_yaml("datasets/csafety.yaml")["labels"]) == SOURCE_LABELS["csafety"]


def test_csafety_mapping():
    cmap = _cmap("csafety")
    assert map_label("no-helmet", cmap) == "head"
    assert map_label("vest", cmap) is None and map_label("no-vest", cmap) is None


def test_unknown_label_fails_loudly():
    with pytest.raises(UnmappedLabelError):
        map_label("crane", _cmap("csafety"))


@pytest.mark.parametrize("ds", sorted(SOURCE_LABELS))
def test_no_scope_creep(ds):
    assert set(_cmap(ds)["train_classes"]) <= {"person", "helmet", "head"}


def test_validate_rejects_missing_mvp_class():
    bad = {"train_classes": ["person"], "eval_classes": ["person"], "map": {"person": "person"}}
    with pytest.raises(ValueError):
        validate_class_map(bad)


@pytest.mark.parametrize("ds", sorted(SOURCE_LABELS))
def test_class_ids_order(ds):
    assert class_ids(_cmap(ds)) == {"person": 0, "helmet": 1, "head": 2}
