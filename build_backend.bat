@echo off
setlocal
cd /d "%~dp0"

echo === Building backend.exe (PyInstaller --onedir) ===

set "PYTHON_CMD="

if defined PYINSTALLER_PYTHON if exist "%PYINSTALLER_PYTHON%" set "PYTHON_CMD=%PYINSTALLER_PYTHON%"

if not defined PYTHON_CMD (
    python -m PyInstaller --version >nul 2>&1
    if %ERRORLEVEL% EQU 0 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    py -3 -m PyInstaller --version >nul 2>&1
    if %ERRORLEVEL% EQU 0 set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
    echo [ERROR] Could not find a usable Python with PyInstaller installed.
    echo [ERROR] Install PyInstaller for your current Python, or set PYINSTALLER_PYTHON.
    exit /b 1
)

echo Using Python launcher: %PYTHON_CMD%
%PYTHON_CMD% -m PyInstaller backend.spec --noconfirm
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PyInstaller failed.
    exit /b 1
)

echo.
echo Done. Output: dist\backend\backend.exe
echo.
echo Next step: cd frontend ^&^& npm run electron:build
exit /b 0
