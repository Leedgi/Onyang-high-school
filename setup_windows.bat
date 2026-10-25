@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
pushd "%~dp0"
if errorlevel 1 exit /b 1

set "BOOTSTRAP_PY=py -3.12"
py -3.12 -c "import sys,struct; assert sys.version_info[:2] == (3,12) and struct.calcsize('P') == 8" >nul 2>&1
if errorlevel 1 (
    set "BOOTSTRAP_PY=python"
    python -c "import sys,struct; assert sys.version_info[:2] == (3,12) and struct.calcsize('P') == 8" >nul 2>&1
    if errorlevel 1 goto missing_python
)

if exist ".venv" if not exist ".venv\Scripts\python.exe" (
    echo An incompatible .venv folder exists. Move it aside and try again.
    goto failed
)
if not exist ".venv\Scripts\python.exe" (
    %BOOTSTRAP_PY% -m venv .venv
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -c "import sys,struct; assert sys.version_info[:2] == (3,12) and struct.calcsize('P') == 8"
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements-windows.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip check
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m scripts.prepare_ocr
if errorlevel 1 goto failed
echo.
echo Setup completed. Double-click run_windows.bat to open the app.
popd
if /i not "%~1"=="--no-pause" pause
exit /b 0

:missing_python
echo Python 3.12 x64 was not found. Install it from python.org and try again.
:failed
echo Setup failed. Read the error above, fix it, and run this file again.
popd
if /i not "%~1"=="--no-pause" pause
exit /b 1
