@echo off
echo === Building backend.exe (PyInstaller --onedir) ===
"D:/miniconda/envs/miner-agent/python.exe" -m PyInstaller backend.spec --noconfirm
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PyInstaller failed.
    pause
    exit /b 1
)
echo.
echo Done. Output: dist\backend\backend.exe
echo.
echo Next step: cd frontend ^&^& npm run electron:build
pause
