@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [LOI] Chua co .venv. Hay chay install_windows.bat truoc.
    pause
    exit /b 1
)

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "LAUNCHER=%STARTUP%\VieNeuTTS.cmd"

> "%LAUNCHER%" echo @echo off
>> "%LAUNCHER%" echo cd /d "%~dp0"
>> "%LAUNCHER%" echo call "%~dp0start_all.bat"

echo.
echo Da cai tu khoi dong cung Windows:
echo   %LAUNCHER%
echo.
echo Khi dang nhap Windows se khoi dong:
echo   - TTS API: port 8765
echo   - Voice Library LAN: port 8766
echo.
echo Muon go bo: chay remove_autostart.bat
pause
