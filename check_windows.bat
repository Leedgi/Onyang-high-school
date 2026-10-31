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
".venv\Scripts\python.exe" -m pip check
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pytest -q
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m scripts.check_auto_ocr
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m scripts.check_ocr_geometry
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m scripts.check_server
if errorlevel 1 goto failed
echo All checks passed.
popd
if /i not "%~1"=="--no-pause" pause
exit /b 0

:failed
echo A check failed. Read the output above.
popd
if /i not "%~1"=="--no-pause" pause
exit /b 1
