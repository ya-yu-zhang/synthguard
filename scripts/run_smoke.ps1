# SynthGuard smoke loop (Windows). Run from anywhere; uses the repo's .venv if present.
# native tools write progress to stderr; rely on exit codes, not PowerShell error records
$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$py = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
$start = Get-Date
& $py -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "tests failed" }
& $py -m synthguard smoke --profile smoke
if ($LASTEXITCODE -ne 0) { throw "smoke failed" }
"wall clock: {0:N1} min" -f ((Get-Date) - $start).TotalMinutes
