@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title VieNeu Live TTS Web

if not exist ".venv\Scripts\python.exe" (
    echo [LOI] Chua co .venv. Hay chay install_windows.bat truoc.
    pause
    exit /b 1
)

if "%LIVE_WEB_HOST%"=="" set LIVE_WEB_HOST=0.0.0.0
if "%LIVE_WEB_PORT%"=="" set LIVE_WEB_PORT=8771
if "%LIVE_WEB_TTS_SERVER%"=="" set LIVE_WEB_TTS_SERVER=http://127.0.0.1:8765
if "%LIVE_WEB_QUEUE%"=="" set LIVE_WEB_QUEUE=http://127.0.0.1:8770

echo ============================================================
echo  VIE-NEU LIVE TTS WEB CONTROL
echo ============================================================
echo HOST  = %LIVE_WEB_HOST%
echo PORT  = %LIVE_WEB_PORT%
echo TTS   = %LIVE_WEB_TTS_SERVER%
echo QUEUE = %LIVE_WEB_QUEUE%
echo ============================================================
echo.
echo PC: http://127.0.0.1:%LIVE_WEB_PORT%
echo LAN: http://IP_MAY_CHU:%LIVE_WEB_PORT%
echo.

.venv\Scripts\python.exe live_web.py
set EXIT_CODE=%ERRORLEVEL%

echo.
echo Live web da dung. Exit code: %EXIT_CODE%
pause
exit /b %EXIT_CODE%
