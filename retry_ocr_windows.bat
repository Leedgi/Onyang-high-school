@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
pushd "%~dp0"
if errorlevel 1 exit /b 1
if not exist ".venv\Scripts\python.exe" (
    echo Python environment not found. Run setup_windows.bat first.
    popd
    if /i not "%~1"=="--no-pause" pause
    exit /b 1
)
".venv\Scripts\python.exe" -m scripts.prepare_ocr
set "OCR_EXIT=%ERRORLEVEL%"
echo.
echo OCR diagnostics: artifacts\ocr-setup.txt
popd
if /i not "%~1"=="--no-pause" pause
exit /b %OCR_EXIT%
