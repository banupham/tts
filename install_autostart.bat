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
>> "%LAUNCHER%" echo start "VieNeu TTS" /min "%~dp0start_tts.bat"

echo.
echo Da cai tu khoi dong cung Windows:
echo   %LAUNCHER%
echo.
echo Server se duoc mo thu nho khi ban dang nhap Windows.
echo Muon go bo: chay remove_autostart.bat
pause
