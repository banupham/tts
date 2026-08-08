@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [LOI] Chua co .venv. Hay chay install_windows.bat truoc.
    pause
    exit /b 1
)

echo Dang khoi dong 2 server...
start "VieNeu TTS" /min cmd /c call "%~dp0start_tts.bat"
timeout /t 2 /nobreak >nul
start "Voice Library" /min cmd /c call "%~dp0start_library.bat"

echo.
echo TTS API       : http://127.0.0.1:8765
echo Voice Library : http://127.0.0.1:8766
echo.
echo Neu truy cap tu dien thoai/PC khac, dung IP LAN cua may chu va cong 8766.
echo Vi du: http://192.168.1.20:8766
