@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo First launch: installing the local environment ...
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_workbench.ps1"
  if errorlevel 1 (
    echo.
    echo Installation failed. Please review the message above.
    pause
    exit /b 1
  )
)
echo.
echo Format Agent Workbench will open in your browser.
echo Keep this window open. Press Ctrl+C here to stop the workbench.
echo.
"%~dp0.venv\Scripts\python.exe" -m streamlit run "%~dp0app.py" --server.address=127.0.0.1 --server.port=8501 --browser.gatherUsageStats=false
if errorlevel 1 pause
