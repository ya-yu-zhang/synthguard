#!/usr/bin/env bash
# SynthGuard web UI (Linux / Git Bash). Pass --host 0.0.0.0 to share on the LAN.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=python
[ -x .venv/bin/python ] && PY=.venv/bin/python
[ -x .venv/Scripts/python.exe ] && PY=.venv/Scripts/python.exe
exec "$PY" -m synthguard ui --port 8765 "$@"
