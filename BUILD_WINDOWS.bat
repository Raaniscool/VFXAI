@echo off
setlocal
pushd "%~dp0" || exit /b 1
title Build VFXAI for Windows
where node.exe >nul 2>&1
if errorlevel 1 goto :node_missing
where npm.cmd >nul 2>&1
if errorlevel 1 goto :node_missing
node scripts\check-node.cjs
if errorlevel 1 goto :failed
echo Installing locked dependencies and running foundation checks...
call npm.cmd ci
if errorlevel 1 goto :failed
call npm.cmd test
if errorlevel 1 goto :failed
echo Building the desktop interface, installer, and portable executable...
call npm.cmd run dist:win
if errorlevel 1 goto :failed
echo.
echo Success. Installer and portable EXE files are in:
echo %CD%\release
echo You do not need Node.js or a web server to run those EXE files.
start "" explorer.exe "%CD%\release"
pause
popd
exit /b 0
:node_missing
echo Install Node.js 22.12 or newer from nodejs.org, then run this file again.
:failed
echo.
echo Windows packaging failed. Read the error above. See docs\windows-desktop.md.
pause
popd
exit /b 1
