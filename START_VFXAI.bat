@echo off
setlocal
pushd "%~dp0" || exit /b 1
title VFXAI local development
if not exist .venv\Scripts\python.exe (
  echo First-run source setup is required. This installs Python and Node packages into this folder.
  call SETUP_VFXAI.bat /nopause
  if errorlevel 1 goto :failed
)
if not exist node_modules\vite\bin\vite.js (
  echo VFXAI's web dependencies are missing; running source setup first.
  call SETUP_VFXAI.bat /nopause
  if errorlevel 1 goto :failed
)
call .venv\Scripts\activate.bat
if errorlevel 1 goto :failed
echo Building the current browser UI, then starting the Python API and 3D preview...
call npm.cmd run build
if errorlevel 1 goto :failed
python -m vfxai.cli init
if errorlevel 1 goto :failed
echo.
echo VFXAI runs only on this computer. Keep this window open while using it.
echo Press Ctrl+C in this window to stop the local app.
python -m vfxai.cli serve
set "RESULT=%ERRORLEVEL%"
echo.
echo VFXAI has stopped.
if not "%RESULT%"=="0" goto :failed
popd
exit /b 0
:failed
echo.
echo VFXAI did not start. Read the error above; your local dataset/checkpoints were not deleted.
pause
popd
exit /b 1
