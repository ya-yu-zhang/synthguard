#!/usr/bin/env bash
# Full MVP profile: same loop as smoke, larger seed/val and quota.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=python
[ -x .venv/bin/python ] && PY=.venv/bin/python
[ -x .venv/Scripts/python.exe ] && PY=.venv/Scripts/python.exe
"$PY" -m synthguard smoke --profile mvp
