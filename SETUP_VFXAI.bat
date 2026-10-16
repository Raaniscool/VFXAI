@echo off
setlocal
pushd "%~dp0" || exit /b 1
title Set up VFXAI local source project
set "PYTHON_CMD="
where py.exe >nul 2>&1
if not errorlevel 1 (
  py -3.11 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)" >nul 2>&1
  if not errorlevel 1 set "PYTHON_CMD=py -3.11"
)
if not defined PYTHON_CMD (
  where python.exe >nul 2>&1
  if not errorlevel 1 (
    python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=python"
  )
)
if not defined PYTHON_CMD goto :python_missing
where node.exe >nul 2>&1
if errorlevel 1 goto :node_missing
where npm.cmd >nul 2>&1
if errorlevel 1 goto :node_missing
node scripts\check-node.cjs
if errorlevel 1 goto :failed
if not exist .venv\Scripts\python.exe (
  echo Creating the project-local Python 3.11 environment...
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 goto :failed
)
call .venv\Scripts\activate.bat
if errorlevel 1 goto :failed
echo Installing the small, pinned CPU-only Python dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 goto :failed
if not exist node_modules\vite\bin\vite.js (
  echo Installing the locked Three.js/Vite development dependencies...
  call npm.cmd ci
  if errorlevel 1 goto :failed
)
echo Building the local browser interface...
call npm.cmd run build
if errorlevel 1 goto :failed
echo Preparing local synthetic examples and the untrained random baseline...
python -m vfxai.cli init
if errorlevel 1 goto :failed
echo.
echo VFXAI source setup is ready. Double-click START_VFXAI.bat to launch it.
if /i not "%~1"=="/nopause" pause
popd
exit /b 0
:python_missing
echo Python 3.11 was not found. Install 64-bit Python 3.11, including the Python launcher, then try again.
echo Download Python only from https://www.python.org/downloads/ . Do not install Python into the Windows Store alias folder.
goto :failed
:node_missing
echo Node.js 22.12 or newer and npm were not found. Install the current Node.js LTS release, then try again.
echo Download Node.js only from https://nodejs.org/ .
:failed
echo.
echo Setup did not complete. Read the error above. Your source files and .vfxai data are preserved.
if /i not "%~1"=="/nopause" pause
popd
exit /b 1
