@echo off
rem SynthGuard 生图台：双击启动，浏览器自动打开 http://127.0.0.1:8765/
rem 想让同事从自己的电脑打开：把下面的 --host 127.0.0.1 改成 --host 0.0.0.0
chcp 65001 >nul
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo 没有找到 .venv，请先按 REPRO.md 第 2 节建环境。
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m synthguard ui --host 127.0.0.1 --port 8765 --open
pause
