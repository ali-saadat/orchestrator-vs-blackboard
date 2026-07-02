@echo off
rem One-click launcher for Windows.
rem   run.bat            open the live demo in your browser
rem   run.bat bench      run the CLI benchmark instead
rem Prefers `uv` (fast). Falls back to a local .venv + pip on first run.
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1

set ARGS=%*
if "%ARGS%"=="" set ARGS=serve

where uv >nul 2>nul
if %errorlevel%==0 (
  uv run ovb %ARGS%
  goto :eof
)

if not exist .venv (
  echo First run: creating .venv and installing (needs internet)...
  py -3 -m venv .venv || python -m venv .venv
  .venv\Scripts\python -m pip install -q --upgrade pip
  .venv\Scripts\python -m pip install -q -e .
)
.venv\Scripts\python -m ovb %ARGS%
