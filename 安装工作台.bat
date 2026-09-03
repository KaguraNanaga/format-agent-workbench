@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_workbench.ps1"
if errorlevel 1 (
  echo.
  echo Installation failed. Please review the message above.
  pause
  exit /b 1
)
echo.
echo Installation completed.
pause
