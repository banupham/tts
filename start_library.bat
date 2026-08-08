@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title VieNeu Voice Library LAN

if not exist ".venv\Scripts\python.exe" (
    echo [LOI] Chua co .venv.
    echo Hay chay install_windows.bat truoc.
    pause
    exit /b 1
)

if "%VOICE_LIBRARY_HOST%"=="" set VOICE_LIBRARY_HOST=0.0.0.0
if "%VOICE_LIBRARY_PORT%"=="" set VOICE_LIBRARY_PORT=8766
if "%VOICE_LIBRARY_MAX_FILES%"=="" set VOICE_LIBRARY_MAX_FILES=5000

echo ============================================================
echo  VIE-NEU VOICE LIBRARY LAN SERVER
echo ============================================================
echo HOST = %VOICE_LIBRARY_HOST%
echo PORT = %VOICE_LIBRARY_PORT%
if not "%VOICE_LIBRARY_ROOTS%"=="" echo ROOTS = %VOICE_LIBRARY_ROOTS%
echo ============================================================
echo.
echo Trinh duyet tren PC nay:
echo   http://127.0.0.1:%VOICE_LIBRARY_PORT%
echo.
echo Dia chi LAN se duoc in ra khi server khoi dong.
echo.

.venv\Scripts\python.exe voice_library_server.py
set EXIT_CODE=%ERRORLEVEL%

echo.
echo Library server da dung. Exit code: %EXIT_CODE%
pause
exit /b %EXIT_CODE%
