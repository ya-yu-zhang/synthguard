"""`synthguard` command line. One entry point; every step is also runnable alone."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from .records import load_yaml


def _profile(name: str) -> dict:
    return load_yaml(name)


def cmd_download(a):
    from .download_public import download, spot_check

    p = _profile(a.profile)
    print(json.dumps(download(p, everything=getattr(a, "all", False)), indent=2))
    rows = spot_check(p)
    bad = [r for r in rows if r[1] != r[2] and r[2] != "missing"]
    for rel, want, got in rows:
        print(f"  checksum {rel}: {'ok' if want == got else ('not downloaded' if got == 'missing' else 'MISMATCH')}")
    if bad:
        sys.exit("checksum mismatch: dataset revision changed?")


def cmd_make_splits(a):
    """Maintainer only, once per dataset: freeze val/seed lists and a checksum sample."""
    from .dataset import dataset_cfg, real_dir
    from .download_public import download, sha256_file
    from .records import read_records
    from .settings import get_settings
    from .splits import make_splits

    p = _profile(a.profile)
    ds = dataset_cfg(p)
    if ds["format"] == "fiftyone":
        sys.exit("fiftyone splits are frozen already (configs/splits/hardhat)")
    download(p)
    recs = read_records(real_dir(p))
    cfg_dir = get_settings().configs_dir
    sizes = ds["split_sizes"]
    print(make_splits([r["id"] for r in recs], cfg_dir / ds["val_list"], cfg_dir / ds["seed_list"],
                      sizes["val"], sizes["seed"], force=a.force))
    by = {r["id"]: r for r in recs}
    val = (cfg_dir / ds["val_list"]).read_text(encoding="utf-8").split()[:3]
    seed = (cfg_dir / ds["seed_list"]).read_text(encoding="utf-8").split()[:2]
    lines = [f"{sha256_file(real_dir(p) / by[i]['file'])} {by[i]['file']}" for i in val + seed]
    (cfg_dir / ds["checksums"]).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def cmd_augment(a):
    from .augment_classic import augment

    print(json.dumps(augment(_profile(a.profile)), indent=2))


def cmd_paste(a):
    from .copy_paste import paste

    print(json.dumps(paste(_profile(a.profile)), indent=2))


def cmd_gen(a):
    from .gen_client import run

    print(json.dumps(run(_profile(a.profile), n=a.n), indent=2))


def cmd_probe(a):
    from .gen_client import choose_generator, probe
    from .settings import get_settings

    s = get_settings()
    st = probe(s.comfy_url)
    if st is None:
        print(f"ComfyUI offline at {s.comfy_url}")
        sys.exit(1)
    print(json.dumps(st, indent=2))
    print(choose_generator(load_yaml(f"gen_{s.gen_profile}"), s.comfy_url))


def cmd_stats(a):
    from .stats_instances import histogram, run

    s = run(_profile(a.profile))
    for g, row in s["table"].items():
        print(f"{g:>12}: " + "  ".join(f"{k}={v}" for k, v in row.items()))
    print("boxes per image (seed):")
    print("\n".join(histogram({int(k): v for k, v in s["boxes_per_image"]["seed (real)"].items()})))
    print("quota:", "OK" if s["quota_ok"] else "NOT MET", json.dumps(s["quota"]))


def cmd_export(a):
    from .export_yolo import export

    print(export(_profile(a.profile), a.exp))


def cmd_train(a):
    from .train_eval import train

    for r in train(_profile(a.profile), a.exp, a.seeds):
        print(f"{r['experiment']} seed {r['seed']}: mAP50(person,helmet)={r['map50_eval'] * 100:.1f}")


def cmd_z0(a):
    from .label_pseudo import run_z0

    r = run_z0(_profile(a.profile))
    print(json.dumps({k: r[k] for k in ("status", "allowed_classes")}, indent=2))


def cmd_compare(a):
    from .compare import write

    print(write(a.profile))


def cmd_viz(a):
    from .viz_compare import run

    print(run(_profile(a.profile)))


def cmd_scenes(a):
    from .scenes import run

    weights = dict(kv.split("=", 1) for kv in a.weights.split(",")) if a.weights else None
    print(json.dumps(run(a.spec, a.n, a.batch, a.seed, operator=a.operator,
                         weights_override=weights), indent=2, ensure_ascii=False))


def cmd_ui(a):
    from .ui_server import serve

    serve(a.host, a.port, allow_remote_config=a.allow_remote_config, open_browser=a.open,
          allow_hosts=a.allow_host)


def cmd_smoke(a):
    """download -> z0 -> augment -> paste -> gen (skip-aware) -> stats -> E0/E2 -> compare -> viz."""
    p = a.profile
    t0 = time.time()
    steps = [("download", cmd_download), ("z0", cmd_z0), ("augment", cmd_augment),
             ("paste", cmd_paste), ("gen", cmd_gen), ("stats", cmd_stats)]
    for name, fn in steps:
        print(f"\n== {name}")
        fn(argparse.Namespace(profile=p, n=None, all=False))
    for exp in ("E0", "E2"):
        print(f"\n== train {exp}")
        cmd_train(argparse.Namespace(profile=p, exp=exp, seeds=None))
    print("\n== compare")
    cmd_compare(argparse.Namespace(profile=p))
    print("\n== viz")
    cmd_viz(argparse.Namespace(profile=p))
    print(f"\nsmoke finished in {(time.time() - t0) / 60:.1f} min")


def main(argv=None):
    # reproducibility: never let ultralytics pip-install packages behind the lock file
    os.environ.setdefault("YOLO_AUTOINSTALL", "false")
    ap = argparse.ArgumentParser(prog="synthguard")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, profile=True, help=None):
        sp = sub.add_parser(name, help=help)
        if profile:
            sp.add_argument("--profile", default="smoke", help="configs/<profile>.yaml (smoke|mvp)")
        sp.set_defaults(fn=fn)
        return sp

    sp = add("download", cmd_download, help="download the profile's pinned public dataset")
    sp.add_argument("--all", action="store_true", help="every image, not only the profile's splits")
    sp = add("make-splits", cmd_make_splits, help="maintainer only: freeze val/seed lists")
    sp.add_argument("--force", action="store_true")
    add("augment", cmd_augment, help="classic augmentation pool")
    add("paste", cmd_paste, help="copy-paste pool")
    sp = add("gen", cmd_gen, help="diffusion via ComfyUI (respects SKIP_DIFFUSION)")
    sp.add_argument("--n", type=int, default=None)
    add("probe-comfy", cmd_probe, profile=False, help="check ComfyUI and visible weights")
    add("stats", cmd_stats, help="instance statistics + quota")
    sp = add("export", cmd_export, help="write YOLO dataset for an experiment")
    sp.add_argument("exp", choices=["E0", "E2", "E1"])
    sp = add("train", cmd_train, help="train + evaluate an experiment")
    sp.add_argument("exp", choices=["E0", "E2", "E1"])
    sp.add_argument("--seeds", type=int, nargs="*", default=None)
    add("z0", cmd_z0, help="pseudo-labeler gate on the real val split")
    add("compare", cmd_compare, help="write runs/compare.md")
    add("viz", cmd_viz, help="triptych examples into assets/examples")
    add("smoke", cmd_smoke, help="the whole smoke loop")
    sp = add("scenes", cmd_scenes, profile=False,
             help="text-to-image scene batch for manual labeling (no boxes)")
    sp.add_argument("--spec", default="substation", help="configs/scenes_<spec>.yaml")
    sp.add_argument("--n", type=int, default=50)
    sp.add_argument("--batch", required=True, help="output folder name under <data>/scenes/")
    sp.add_argument("--seed", type=int, default=0)
    sp.add_argument("--operator", default="", help="who started the batch (recorded in batch.json)")
    sp.add_argument("--weights", default="", help="element weight overrides, e.g. robot_arm=3,fumes=0.5")
    sp = add("ui", cmd_ui, profile=False, help="local web UI: generate scenes, browse batches, edit .env")
    sp.add_argument("--host", default="127.0.0.1", help="0.0.0.0 to let colleagues on the LAN open it")
    sp.add_argument("--port", type=int, default=8765)
    sp.add_argument("--allow-remote-config", action="store_true",
                    help="let non-local browsers edit .env (off by default)")
    sp.add_argument("--open", action="store_true", help="open the browser after start")
    sp.add_argument("--allow-host", action="append", default=[], metavar="NAME",
                    help="extra host name colleagues use (IPs and this machine's name always work)")
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
