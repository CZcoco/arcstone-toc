@echo off
setlocal
set PYTHON_VERSION=3.11.9
set OUT_DIR=%~dp0..\frontend\resources\python

echo [1/4] 创建目录 %OUT_DIR%
mkdir "%OUT_DIR%" 2>nul

echo [2/4] 下载 Python embedded %PYTHON_VERSION%...
curl -L -o "%TEMP%\python-embed.zip" "https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-embed-amd64.zip"
tar -xf "%TEMP%\python-embed.zip" -C "%OUT_DIR%"

echo [3/4] 启用 site-packages（修改 .pth 文件）...
powershell -Command "(gc '%OUT_DIR%\python311._pth') -replace '#import site','import site' | sc '%OUT_DIR%\python311._pth'"

echo [4/4] 安装 pip 和依赖...
curl -L -o "%TEMP%\get-pip.py" https://bootstrap.pypa.io/get-pip.py
"%OUT_DIR%\python.exe" "%TEMP%\get-pip.py"
"%OUT_DIR%\python.exe" -m pip install -r "%~dp0..\requirements.txt" --no-warn-script-location

echo 完成！Python 环境位于：%OUT_DIR%
pause
