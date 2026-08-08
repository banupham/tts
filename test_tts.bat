@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [LOI] Chua co .venv. Hay chay install_windows.bat truoc.
    pause
    exit /b 1
)

.venv\Scripts\python.exe noi.py "Đêm hôm đó... tôi nghe thấy tiếng bước chân ngay phía sau mình." --style doc_truyen --output test_output.wav --play

if errorlevel 1 (
    echo.
    echo [GOI Y] Neu ket noi that bai, hay kiem tra start_tts.bat dang chay.
    pause
    exit /b 1
)

exit /b 0
