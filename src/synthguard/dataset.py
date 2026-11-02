"""Which public dataset a profile uses: its root, frozen splits and class map.

Each profile names a dataset (`dataset: csafety`); `configs/datasets/<name>.yaml`
pins the source, revision, split lists and class map.
"""
from __future__ import annotations

from pathlib import Path

from .class_map import load_class_map
from .records import load_yaml, read_list
from .settings import get_settings


def dataset_cfg(profile: dict) -> dict:
    return load_yaml(Path("datasets") / f"{profile['dataset']}.yaml")


def real_dir(profile: dict) -> Path:
    return get_settings().data_root / "public" / dataset_cfg(profile)["name"]


def seed_ids(profile: dict) -> list[str]:
    return read_list(dataset_cfg(profile)["seed_list"])[: profile["seed_take"]]


def val_ids(profile: dict) -> list[str]:
    return read_list(dataset_cfg(profile)["val_list"])[: profile["val_take"]]


def class_map(profile: dict) -> dict:
    return load_class_map(dataset_cfg(profile)["class_map"])
