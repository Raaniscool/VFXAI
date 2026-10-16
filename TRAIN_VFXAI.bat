@echo off
setlocal
pushd "%~dp0" || exit /b 1
title VFXAI local model training
set "VFXAI_PAUSE=1"
if /i "%~1"=="/nopause" (
  set "VFXAI_PAUSE=0"
  shift
)
if not exist .venv\Scripts\python.exe (
  echo Preparing VFXAI's Python and Node development environment first...
  call SETUP_VFXAI.bat /nopause
  if errorlevel 1 goto :failed
)
call .venv\Scripts\activate.bat
if errorlevel 1 goto :failed
echo Training uses the currently active local dataset and starts from random weights unless you explicitly pass --resume.
echo It compares untrained and trained checkpoints on the same held-out test prompts.
python -m vfxai.cli train %1 %2 %3 %4 %5 %6 %7 %8 %9
if errorlevel 1 goto :failed
if "%VFXAI_PAUSE%"=="1" pause
popd
exit /b 0
:failed
echo.
echo Training failed or stopped with an error. Existing datasets, feedback, and checkpoints were preserved.
if "%VFXAI_PAUSE%"=="1" pause
popd
exit /b 1
