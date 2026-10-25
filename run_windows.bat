@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
pushd "%~dp0"
if errorlevel 1 exit /b 1
if not exist ".venv\Scripts\python.exe" (
    echo Run setup_windows.bat first.
    goto failed
)
echo Opening Ingredient Lab. Keep this window open while using the app.
echo Press Ctrl+C to stop the server.
".venv\Scripts\python.exe" -m streamlit run app.py --server.address=127.0.0.1 --server.port=8501 --server.headless=false
set "APP_EXIT=%ERRORLEVEL%"
popd
if /i not "%~1"=="--no-pause" pause
exit /b %APP_EXIT%

:failed
popd
if /i not "%~1"=="--no-pause" pause
exit /b 1
