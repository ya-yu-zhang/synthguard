import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRIVE = re.compile(r"\b[A-Za-z]:[\\/]")
HOME = re.compile(r"(/home/|/Users/|\\Users\\)")


def test_src_and_configs_have_no_machine_paths():
    files = list((ROOT / "src").rglob("*.py")) + list((ROOT / "configs").glob("*.yaml")) + \
        list((ROOT / "comfy").rglob("*.json"))
    # committed run artifacts too (ultralytics work dirs and raw logs are gitignored)
    files += [f for pat in ("*.json", "*.md", "*.yaml", "*.csv") for f in (ROOT / "runs").rglob(pat)
              if "train" not in f.relative_to(ROOT / "runs").parts]
    # everything a public reader sees: docs, examples, scripts and the UI source
    files += [ROOT / n for n in (".env.example", "README.md", "REPRO.md", "DATA_LICENSE")]
    files += list((ROOT / "docs").glob("*.md")) + list((ROOT / "scripts").glob("*"))
    files += [f for pat in ("*.ts", "*.tsx", "*.css", "*.mjs", "*.md") for f in (ROOT / "web").rglob(pat)
              if "node_modules" not in f.parts]
    offenders = []
    for f in files:
        text = f.read_text(encoding="utf-8")
        if DRIVE.search(text) or HOME.search(text):
            offenders.append(str(f.relative_to(ROOT)))
    assert not offenders, offenders


def test_ui_build_ships_license_notices():
    # minified bundles drop license comments; the build must carry them in a file instead
    text = (ROOT / "src" / "synthguard" / "ui_static" / "THIRD_PARTY_LICENSES.md").read_text(encoding="utf-8")
    for name in ("react", "@fontsource-variable/inter", "@fontsource-variable/geist-mono", "shadcn/ui"):
        assert f"## {name}" in text, name
    assert "SIL Open Font License" in text
