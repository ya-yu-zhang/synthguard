"""Instance statistics per class and source, with a terminal histogram and quota check."""
from __future__ import annotations

import json
from collections import Counter

from .dataset import class_map, real_dir, seed_ids, val_ids
from .qa_filter import filter_records
from .records import by_id, pool_dir, read_records
from .settings import get_settings

INCREMENT_SOURCES = ("augment", "paste", "diffusion")


def gather(profile: dict) -> dict[str, list[dict]]:
    real = by_id(read_records(real_dir(profile)))
    groups = {
        "val (real)": [real[i] for i in val_ids(profile)],
        "seed (real)": [real[i] for i in seed_ids(profile)],
    }
    for name in INCREMENT_SOURCES:
        recs = read_records(pool_dir(name, profile["name"]))
        if name == "diffusion":
            recs = [r for r in recs if r.get("qa", {}).get("accepted")]
        groups[name], _ = filter_records(recs)
    return groups


def compute(profile: dict) -> dict:
    classes = class_map(profile)["train_classes"]
    groups = gather(profile)
    table, per_image = {}, {}
    for g, recs in groups.items():
        c = Counter(b["cls"] for r in recs for b in r["boxes"])
        table[g] = {"images": len(recs), **{k: c.get(k, 0) for k in classes}}
        per_image[g] = Counter(min(len(r["boxes"]), 20) for r in recs)
    pasted = Counter(p["cls"] for r in groups["paste"] for p in r.get("pastes", []))
    inc = {k: sum(table[s][k] for s in INCREMENT_SOURCES) for k in classes}
    quota = profile["quota"]
    checks = {k: {"have": inc.get(k, 0), "need": v, "ok": inc.get(k, 0) >= v}
              for k, v in quota.items()}
    inc_imgs = sum(table[s]["images"] for s in INCREMENT_SOURCES)
    share = {s: (table[s]["images"] / inc_imgs if inc_imgs else 0.0) for s in INCREMENT_SOURCES}
    return {"profile": profile["name"], "classes": classes, "table": table,
            "pasted_new_instances": dict(pasted), "increment": inc, "increment_share": share,
            "quota": checks, "quota_ok": all(v["ok"] for v in checks.values()),
            "boxes_per_image": {g: dict(sorted(v.items())) for g, v in per_image.items()}}


def histogram(counter: dict, width: int = 40) -> list[str]:
    if not counter:
        return ["  (empty)"]
    top = max(counter.values())
    rows = []
    for k in sorted(counter):
        n = counter[k]
        label = f"{k}+" if k == 20 else str(k)
        rows.append(f"  {label:>3} boxes | {'#' * max(1, round(n / top * width)) if n else ''} {n}")
    return rows


def render_md(s: dict) -> str:
    cls = s["classes"]
    lines = [f"# Instance statistics · profile `{s['profile']}`", "",
             "Boxes after automatic QA. `head` is a mapped auxiliary class (not in the main table).", "",
             "| group | images | " + " | ".join(cls) + " |",
             "|---|---:|" + "---:|" * len(cls)]
    for g, row in s["table"].items():
        lines.append(f"| {g} | {row['images']} | " + " | ".join(str(row[c]) for c in cls) + " |")
    lines += ["", "Newly pasted instances (subset of `paste` boxes): " +
              ", ".join(f"{k}={v}" for k, v in sorted(s["pasted_new_instances"].items())), "",
              "Increment share by images: " +
              ", ".join(f"{k} {v * 100:.1f}%" for k, v in s["increment_share"].items()), "",
              "## Quota (incremental valid boxes, design §5.3)", "",
              "| class | have | need | ok |", "|---|---:|---:|---|"]
    for k, v in s["quota"].items():
        lines.append(f"| {k} | {v['have']} | {v['need']} | {'yes' if v['ok'] else 'NO'} |")
    lines += ["", "## Boxes per image", ""]
    for g, h in s["boxes_per_image"].items():
        lines += [f"`{g}`", "```", *histogram({int(k): v for k, v in h.items()}), "```"]
    return "\n".join(lines) + "\n"


def run(profile: dict) -> dict:
    s = compute(profile)
    out = get_settings().runs_root / profile["name"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "stats.json").write_text(json.dumps(s, indent=2), encoding="utf-8")
    (out / "stats.md").write_text(render_md(s), encoding="utf-8")
    return s
