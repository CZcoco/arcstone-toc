@echo off
setlocal EnableExtensions

set "PYTHON_VERSION=3.12.10"
set "OUT_DIR=%~dp0..\frontend\resources\python"
set "ZIP_PATH=%TEMP%\python-%PYTHON_VERSION%-embed-amd64.zip"
set "GET_PIP_PATH=%TEMP%\get-pip.py"
set "PTH_FILE=%OUT_DIR%\python312._pth"

echo [1/5] Preparing %OUT_DIR%
if exist "%OUT_DIR%" rmdir /s /q "%OUT_DIR%"
mkdir "%OUT_DIR%" || exit /b 1

echo [2/5] Downloading embedded Python %PYTHON_VERSION%
curl -fL -o "%ZIP_PATH%" "https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-embed-amd64.zip" || exit /b 1
powershell -Command "Expand-Archive -Path '%ZIP_PATH%' -DestinationPath '%OUT_DIR%' -Force" || exit /b 1

echo [3/5] Enabling site-packages
if not exist "%PTH_FILE%" (
    echo [ERROR] Missing _pth file: %PTH_FILE%
    exit /b 1
)
powershell -Command "(gc '%PTH_FILE%') -replace '#import site','import site' | sc '%PTH_FILE%'" || exit /b 1

echo [4/5] Installing pip
curl -fL -o "%GET_PIP_PATH%" https://bootstrap.pypa.io/get-pip.py || exit /b 1
"%OUT_DIR%\python.exe" "%GET_PIP_PATH%" || exit /b 1

echo [5/5] Installing uv (fast Python package installer)
"%OUT_DIR%\python.exe" -m pip install uv --no-warn-script-location --no-compile || exit /b 1

echo.
echo ========================================
echo Embedded Python + uv ready at %OUT_DIR%
echo Python: %OUT_DIR%\python.exe
echo uv: %OUT_DIR%\Scripts\uv.exe
echo ========================================
echo.
echo Note: Dependencies will be installed on first app launch.
pause
