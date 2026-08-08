@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title VieNeu Local TTS Server

if not exist ".venv\Scripts\python.exe" (
    echo [LOI] Chua co .venv.
    echo Hay chay install_windows.bat truoc.
    pause
    exit /b 1
)

if "%TTS_HOST%"=="" set TTS_HOST=127.0.0.1
if "%TTS_PORT%"=="" set TTS_PORT=8765
if "%TTS_PRECISION%"=="" set TTS_PRECISION=int8
if "%TTS_THREADS%"=="" set TTS_THREADS=0
if "%TTS_WARMUP%"=="" set TTS_WARMUP=1

echo ============================================================
echo  VIE-NEU LOCAL TTS SERVER
echo ============================================================
echo HOST      = %TTS_HOST%
echo PORT      = %TTS_PORT%
echo PRECISION = %TTS_PRECISION%
echo THREADS   = %TTS_THREADS%
echo WARMUP    = %TTS_WARMUP%
echo ============================================================
echo.

.venv\Scripts\python.exe tts_server.py
set EXIT_CODE=%ERRORLEVEL%

echo.
echo Server da dung. Exit code: %EXIT_CODE%
pause
exit /b %EXIT_CODE%
