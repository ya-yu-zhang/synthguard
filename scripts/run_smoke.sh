#!/usr/bin/env bash
# SynthGuard smoke loop (Linux/macOS/Git Bash).
set -euo pipefail
cd "$(dirname "$0")/.."
PY=python
[ -x .venv/bin/python ] && PY=.venv/bin/python
[ -x .venv/Scripts/python.exe ] && PY=.venv/Scripts/python.exe
start=$(date +%s)
"$PY" -m pytest -q
"$PY" -m synthguard smoke --profile smoke
echo "wall clock: $(( ($(date +%s) - start) / 60 )) min"
