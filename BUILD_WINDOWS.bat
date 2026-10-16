@echo off
setlocal
pushd "%~dp0" || exit /b 1
echo This source workflow no longer packages an Electron app or creates an EXE.
echo It prepares/tests the Python + browser development project instead.
call SETUP_VFXAI.bat /nopause
if errorlevel 1 goto :failed
call TEST_VFXAI.bat /nopause
if errorlevel 1 goto :failed
echo.
echo VFXAI source setup and checks completed. Use START_VFXAI.bat to launch.
pause
popd
exit /b 0
:failed
echo.
echo Source setup/checks failed. No EXE was created.
pause
popd
exit /b 1
