@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
pushd "%~dp0"
if errorlevel 1 exit /b 1

set "BOOTSTRAP_PY=py -3.14"
py -3.14 -c "import sys,struct,sysconfig; assert sys.version_info[:2] == (3,14) and struct.calcsize('P') == 8 and not sysconfig.get_config_var('Py_GIL_DISABLED')" >nul 2>&1
if errorlevel 1 (
    set "BOOTSTRAP_PY=python"
    python -c "import sys,struct,sysconfig; assert sys.version_info[:2] == (3,14) and struct.calcsize('P') == 8 and not sysconfig.get_config_var('Py_GIL_DISABLED')" >nul 2>&1
    if errorlevel 1 goto missing_python
)

%BOOTSTRAP_PY% scripts\setup_windows_env.py
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements-windows.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip check
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m scripts.prepare_ocr
if errorlevel 1 (
    echo OCR details: artifacts\ocr-setup.txt
    echo Retry models only: .venv\Scripts\python.exe -m scripts.prepare_ocr
    goto failed
)
echo.
echo Setup completed. Double-click run_windows.bat to open the app.
popd
if /i not "%~1"=="--no-pause" pause
exit /b 0

:missing_python
echo Standard Python 3.14 x64 was not found.
echo Download: https://www.python.org/ftp/python/3.14.10/python-3.14.10-amd64.exe
echo Install Python 3.14, then run this setup again.
:failed
echo Setup failed. Read the error above, fix it, and run this file again.
popd
if /i not "%~1"=="--no-pause" pause
exit /b 1
