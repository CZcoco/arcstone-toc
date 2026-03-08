@echo off
setlocal

set PYTHON_VERSION=3.11.9
set OUT_DIR=%~dp0..\frontend\resources\python

echo [1/4] Preparing %OUT_DIR%
mkdir "%OUT_DIR%" 2>nul

echo [2/4] Downloading embedded Python %PYTHON_VERSION%
curl -L -o "%TEMP%\python-embed.zip" "https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-embed-amd64.zip"
tar -xf "%TEMP%\python-embed.zip" -C "%OUT_DIR%"

echo [3/4] Enabling site-packages
powershell -Command "(gc '%OUT_DIR%\python311._pth') -replace '#import site','import site' | sc '%OUT_DIR%\python311._pth'"

echo [4/4] Installing dependencies and pruning non-runtime files
curl -L -o "%TEMP%\get-pip.py" https://bootstrap.pypa.io/get-pip.py
"%OUT_DIR%\python.exe" "%TEMP%\get-pip.py"
"%OUT_DIR%\python.exe" -m pip install -r "%~dp0..\requirements.txt" --no-warn-script-location --no-compile
"%OUT_DIR%\python.exe" "%~dp0prune_embedded_python.py" "%OUT_DIR%"

echo Embedded Python ready at %OUT_DIR%
pause
