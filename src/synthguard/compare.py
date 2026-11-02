"""Build runs/<profile>/compare.md (and runs/compare.md) from real run artifacts only."""
from __future__ import annotations

import json
from statistics import mean

from .settings import get_settings

DATA_DESC = {
    "E0": "real seed only",
    "E2": "seed + classic aug + copy-paste (no diffusion)",
    "E1": "seed + full factory output (incl. diffusion)",
}
STOP_LOSS = 2.0  # mAP50 points, design §6.3
# Two seeds cannot estimate run-to-run variance; never call a difference below this real.
MIN_EFFECT = 0.5


def load_runs(profile: str) -> dict[str, list[dict]]:
    root = get_settings().runs_root / profile
    runs: dict[str, list[dict]] = {}
    for f in sorted(root.glob("E*_s*/metrics.json")):
        m = json.loads(f.read_text(encoding="utf-8"))
        runs.setdefault(m["experiment"], []).append(m)
    return runs


def _agg(ms: list[dict], key) -> tuple[float, float]:
    vals = [key(m) * 100 for m in ms]
    return mean(vals), (max(vals) - min(vals))


def _fmt(v: float, spread: float, n: int) -> str:
    return f"{v:.1f}" if n == 1 else f"{v:.1f} ±{spread / 2:.1f}"


def summarize(profile: str) -> dict:
    runs = load_runs(profile)
    rows = {}
    for exp, ms in runs.items():
        classes = ms[0]["eval_classes"]
        rows[exp] = {
            "n": len(ms), "seeds": sorted(m["seed"] for m in ms),
            "map50": _agg(ms, lambda m: m["map50_eval"]),
            "map50_95": _agg(ms, lambda m: m["map50_95_eval"]),
            "per_class": {c: _agg(ms, lambda m, c=c: m["per_class"][c]["ap50"]) for c in classes},
            "train_images": ms[0].get("train_images"),
            "epochs": ms[0]["epochs"], "imgsz": ms[0]["imgsz"], "model": ms[0]["model"],
            "env": ms[0]["env"],
        }
    return {"profile": profile, "rows": rows, "classes": classes if runs else []}


def _gen_status(profile: str) -> dict:
    p = get_settings().runs_root / profile / "gen_status.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def render(profile: str) -> str:
    s = summarize(profile)
    rows, classes = s["rows"], s["classes"]
    if not rows:
        return f"# SynthGuard compare · `{profile}`\n\nNo finished runs yet.\n"
    any_row = next(iter(rows.values()))
    seeds_note = ", ".join(f"{e}: seeds {r['seeds']}" for e, r in sorted(rows.items()))
    lines = [f"# SynthGuard compare · `{profile}`", "",
             f"Model `{any_row['model']}`, {any_row['epochs']} epochs, imgsz {any_row['imgsz']}, "
             f"identical hyper-parameters and the same fixed real val split for every row. "
             f"mAP50 = mean AP50 over {', '.join(classes)}. Values ×100; ± is half the "
             f"min–max range across seeds ({seeds_note}).", "",
             "| exp | data | mAP50 | " + " | ".join(f"AP50 {c}" for c in classes) +
             " | mAP50-95 | Δ mAP50 vs E0 |",
             "|---|---|---:|" + "---:|" * len(classes) + "---:|---:|"]
    base = rows.get("E0", {}).get("map50", (None, 0))[0]
    gen = _gen_status(profile)
    notes = []
    for exp in ("E0", "E2", "E1"):
        if exp not in rows:
            if exp == "E1":
                lines.append(f"| E1 | {DATA_DESC['E1']} | skipped | " +
                             " | ".join("—" for _ in classes) + " | — | — |")
                notes.append("E1 skipped: " + (gen.get("e1_reason") or "diffusion not run for this profile")
                             + (f" (generator: `{gen['generator']}`)" if gen.get("generator") else "") + ".")
            continue
        r = rows[exp]
        n = r["n"]
        delta = "—" if exp == "E0" or base is None else f"{r['map50'][0] - base:+.1f}"
        lines.append(f"| {exp} | {DATA_DESC[exp]} | {_fmt(*r['map50'], n)} | " +
                     " | ".join(_fmt(*r["per_class"][c], n) for c in classes) +
                     f" | {_fmt(*r['map50_95'], n)} | {delta} |")
    if "E1" in rows and gen.get("generator"):
        notes.append(f"E1 diffusion: `{gen['generator']}`, {gen.get('accepted')} of "
                     f"{gen.get('generated')} generated images passed QA."
                     + (" This is a dev-machine stand-in, not the target FLUX.1-dev stack."
                        if "proxy" in gen["generator"] else ""))
    if notes:
        lines += ["", *notes]
    lines += ["", *narrative(rows, classes, gen)]
    env = any_row["env"]
    lines += ["", f"<sub>env: ultralytics {env['ultralytics']}, torch {env['torch']} "
              f"(CUDA {env['cuda']}), {env['device']}, Python {env['python']}. "
              f"Generated from `runs/{profile}/E*_s*/metrics.json` by `synthguard compare`.</sub>"]
    return "\n".join(lines) + "\n"


def narrative(rows: dict, classes: list[str], gen: dict) -> list[str]:
    """Three plain paragraphs: where it wins, where it loses, what next. Numbers only from runs."""
    out = []
    if "E0" not in rows or "E2" not in rows:
        return ["Need both E0 and E2 to compare."]
    e0, e2 = rows["E0"], rows["E2"]
    noise = max(e0["map50"][1] / 2, e2["map50"][1] / 2, MIN_EFFECT)
    wins = [(c, e2["per_class"][c][0] - e0["per_class"][c][0]) for c in classes]
    up = [f"{c} {d:+.1f}" for c, d in wins if d > 0]
    down = [f"{c} {d:+.1f}" for c, d in wins if d <= 0]
    d = e2["map50"][0] - e0["map50"][0]
    d95 = e2["map50_95"][0] - e0["map50_95"][0]
    single = e0["n"] == 1 or e2["n"] == 1
    within = (not single) and abs(d) <= noise
    out.append("**Where it wins.** " + ("Nowhere at this scale. " if d <= 0 and not up else "") + (
        f"Without any generation, E2 changes mAP50 by {d:+.1f} over E0"
        + (f" (classes up: {', '.join(up)})" if up else "") + "."
        + (f" That is within noise (seed spread, or under {MIN_EFFECT:.1f} points with only two seeds), so read it as no change." if within else "")
        + (" Single seed: treat as indicative only." if single else "")))
    floor = [c for c in classes if all(r["per_class"][c][0] < 5.0 for r in rows.values())]
    out.append("**Where it loses.** " + (
        f"Classes not improved by E2: {', '.join(down)}." if down else
        "No eval class got worse with E2 on this split.")
        + (f" {', '.join(floor)} stays below 5 AP50 in every row: the source labels this class "
           "sparsely (most visible people are unboxed, see docs/dataset.md), so detections of "
           "unlabeled people count as false positives and the class mostly measures label "
           "coverage, not the factory." if floor else "")
        + (f" Box tightness drops: mAP50-95 {d95:+.1f} vs E0." if d95 < -MIN_EFFECT else
           f" mAP50-95 moves {d95:+.1f}." if d95 > MIN_EFFECT else "")
        + " Gains on this public domain do not transfer automatically to other cameras; "
          "the val split is fixed and contains no synthetic or derived images.")
    nxt = []
    if "E1" in rows:
        e1d = rows["E1"]["map50"][0] - e0["map50"][0]
        if e1d < -STOP_LOSS:
            nxt.append(f"E1 is {e1d:+.1f} mAP50 vs E0 (beyond the −{STOP_LOSS:.1f} stop-loss): stop adding "
                       "diffusion data and keep E2 as the recommended configuration.")
        else:
            nxt.append(f"E1 is {e1d:+.1f} vs E0; keep diffusion within the ≤50% increment cap.")
    else:
        nxt.append("E1 is pending: " + (gen.get("e1_reason") or "diffusion not run") + ".")
    if d <= 0 or within:
        nxt.append("Next: soften the strongest ops (blur/fog) and check paste scale priors before adding volume.")
    else:
        nxt.append("Next: confirm with the full MVP profile (more seed and val images, two seeds).")
    out.append("**Next.** " + " ".join(nxt))
    return out


def write(profile: str) -> str:
    md = render(profile)
    root = get_settings().runs_root
    (root / profile).mkdir(parents=True, exist_ok=True)
    (root / profile / "compare.md").write_text(md, encoding="utf-8")
    (root / "compare.md").write_text(md, encoding="utf-8")
    return md
