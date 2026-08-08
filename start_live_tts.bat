@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title VieNeu Live TTS Queue

if not exist ".venv\Scripts\python.exe" (
    echo [LOI] Chua co .venv. Hay chay install_windows.bat truoc.
    pause
    exit /b 1
)

if "%LIVE_TTS_HOST%"=="" set LIVE_TTS_HOST=127.0.0.1
if "%LIVE_TTS_PORT%"=="" set LIVE_TTS_PORT=8770
if "%LIVE_TTS_SERVER%"=="" set LIVE_TTS_SERVER=http://127.0.0.1:8765

echo ============================================================
echo  VIE-NEU LIVE TTS QUEUE
echo ============================================================
echo QUEUE API = http://%LIVE_TTS_HOST%:%LIVE_TTS_PORT%
echo TTS API   = %LIVE_TTS_SERVER%
echo.
echo POST text vao /speak de xep hang va phat loa realtime.
echo ============================================================
echo.

.venv\Scripts\python.exe live_tts.py
set EXIT_CODE=%ERRORLEVEL%

echo.
echo Live TTS da dung. Exit code: %EXIT_CODE%
pause
exit /b %EXIT_CODE%
