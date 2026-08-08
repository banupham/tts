@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [LOI] Chua co .venv. Hay chay install_windows.bat truoc.
    pause
    exit /b 1
)

echo Dang khoi dong 4 dich vu...
start "VieNeu TTS" /min cmd /c call "%~dp0start_tts.bat"
timeout /t 2 /nobreak >nul
start "Voice Library" /min cmd /c call "%~dp0start_library.bat"
timeout /t 1 /nobreak >nul
start "Live TTS Queue" /min cmd /c call "%~dp0start_live_tts.bat"
timeout /t 1 /nobreak >nul
start "Live TTS Web" /min cmd /c call "%~dp0start_live_web.bat"

echo.
echo TTS API        : http://127.0.0.1:8765
echo TTS stream     : POST http://127.0.0.1:8765/tts/stream
echo Voice Library  : http://127.0.0.1:8766
echo Live TTS Queue : http://127.0.0.1:8770
echo Live TTS Web   : http://127.0.0.1:8771
echo.
echo Live middleware chi can POST text vao http://127.0.0.1:8770/speak
echo Web 8771 cho phep chon voice, style, priority va gui text vao queue.
echo Neu truy cap tu dien thoai/PC khac, dung IP LAN cua may chu va cong 8766 hoac 8771.
