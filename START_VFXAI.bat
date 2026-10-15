@echo off
setlocal
pushd "%~dp0" || exit /b 1
title VFXAI Desktop Development
where node.exe >nul 2>&1
if errorlevel 1 goto :node_missing
where npm.cmd >nul 2>&1
if errorlevel 1 goto :node_missing
node scripts\check-node.cjs
if errorlevel 1 goto :failed
if not exist node_modules\.bin\electron.cmd (
  echo Installing VFXAI development dependencies. Internet is required the first time.
  call npm.cmd ci
  if errorlevel 1 goto :failed
)
echo Starting VFXAI in a native desktop window. Close the app to stop development.
call npm.cmd run desktop:dev
if errorlevel 1 goto :failed
popd
exit /b 0
:node_missing
echo Node.js and npm were not found. Install Node.js 22.12 or newer from nodejs.org.
echo Then close this window and double-click START_VFXAI.bat again.
:failed
echo.
echo VFXAI did not start. Read the error above. See docs\windows-desktop.md.
pause
popd
exit /b 1
