@echo off
setlocal
pushd "%~dp0" || exit /b 1
title VFXAI source tests
if not exist .venv\Scripts\python.exe (
  call SETUP_VFXAI.bat /nopause
  if errorlevel 1 goto :failed
)
if not exist node_modules\vite\bin\vite.js (
  call SETUP_VFXAI.bat /nopause
  if errorlevel 1 goto :failed
)
call .venv\Scripts\activate.bat
if errorlevel 1 goto :failed
echo Running Python model, data, schema, and API tests...
python -m unittest discover -s tests-python -v
if errorlevel 1 goto :failed
echo Running JavaScript plan/engine/UI tests...
call npm.cmd test
if errorlevel 1 goto :failed
echo Building the browser interface...
call npm.cmd run build
if errorlevel 1 goto :failed
echo Evaluating the current checkpoint on held-out local prompts...
python -m vfxai.cli test
if errorlevel 1 goto :failed
echo.
echo All configured local source checks passed.
if /i not "%~1"=="/nopause" pause
popd
exit /b 0
:failed
echo.
echo One or more source checks failed. Review the first error above; no user data was removed.
if /i not "%~1"=="/nopause" pause
popd
exit /b 1
