"""Fixed, hash-ordered splits. Generated once per dataset by the maintainer and committed.

Ordering by a salted hash makes any prefix (smoke uses the first N ids) a
uniform random subset, while the full lists never change between experiments.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

SALT = "synthguard-v1"


def _key(rid: str) -> str:
    return hashlib.sha1(f"{SALT}:{rid}".encode()).hexdigest()


def make_splits(ids: list[str], val_p: Path, seed_p: Path, val_size: int, seed_size: int,
                force: bool = False) -> dict:
    if (val_p.exists() or seed_p.exists()) and not force:
        raise FileExistsError("splits already exist; val is frozen (use --force only for a new dataset)")
    if len(ids) != len(set(ids)):
        raise ValueError("ids are not unique")
    order = sorted(ids, key=_key)
    val, seed = order[:val_size], order[val_size:val_size + seed_size]
    assert not set(val) & set(seed)
    val_p.parent.mkdir(parents=True, exist_ok=True)
    val_p.write_text("\n".join(val) + "\n", encoding="utf-8", newline="\n")
    seed_p.write_text("\n".join(seed) + "\n", encoding="utf-8", newline="\n")
    return {"val": len(val), "train_seed": len(seed), "unused": len(ids) - len(val) - len(seed)}
