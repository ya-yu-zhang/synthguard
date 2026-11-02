"""Public-label -> SynthGuard class mapping. Unknown labels fail loudly (no silent drops)."""
from __future__ import annotations

from .records import load_yaml

MVP_CLASSES = ("person", "helmet")


class UnmappedLabelError(KeyError):
    pass


def load_class_map(path: str) -> dict:
    cmap = load_yaml(path)
    validate_class_map(cmap)
    return cmap


def validate_class_map(cmap: dict) -> None:
    train = cmap["train_classes"]
    targets = set(cmap["map"].values())
    missing = [c for c in MVP_CLASSES if c not in targets]
    if missing:
        raise ValueError(f"class map does not produce MVP classes: {missing}")
    stray = targets - set(train)
    if stray:
        raise ValueError(f"class map targets not in train_classes: {sorted(stray)}")
    if not set(cmap["eval_classes"]) <= set(train):
        raise ValueError("eval_classes must be a subset of train_classes")
    overlap = set(cmap["map"]) & set(cmap.get("ignore") or [])
    if overlap:
        raise ValueError(f"labels both mapped and ignored: {sorted(overlap)}")


def map_label(label: str, cmap: dict) -> str | None:
    """Return the SynthGuard class, None for explicitly ignored labels, raise otherwise."""
    key = label.strip().lower()
    if key in cmap["map"]:
        return cmap["map"][key]
    if key in (cmap.get("ignore") or []):
        return None
    raise UnmappedLabelError(f"label '{label}' is neither mapped nor ignored in class map")


def class_ids(cmap: dict) -> dict[str, int]:
    return {c: i for i, c in enumerate(cmap["train_classes"])}
