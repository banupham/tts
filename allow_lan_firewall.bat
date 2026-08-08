@echo off
setlocal
chcp 65001 >nul

set LIB_PORT=8766
set WEB_PORT=8771
if not "%VOICE_LIBRARY_PORT%"=="" set LIB_PORT=%VOICE_LIBRARY_PORT%
if not "%LIVE_WEB_PORT%"=="" set WEB_PORT=%LIVE_WEB_PORT%

echo Them Windows Firewall rule cho:
echo   Voice Library TCP %LIB_PORT%
echo   Live TTS Web  TCP %WEB_PORT%
echo Can chay file nay bang Run as administrator.
echo.

netsh advfirewall firewall add rule name="VieNeu Voice Library %LIB_PORT%" dir=in action=allow protocol=TCP localport=%LIB_PORT% profile=private
if errorlevel 1 goto :error

netsh advfirewall firewall add rule name="VieNeu Live TTS Web %WEB_PORT%" dir=in action=allow protocol=TCP localport=%WEB_PORT% profile=private
if errorlevel 1 goto :error

echo.
echo Da mo TCP %LIB_PORT% va %WEB_PORT% cho mang Private.
pause
exit /b 0

:error
echo.
echo [LOI] Khong them duoc firewall rule. Hay chuot phai file va chon Run as administrator.
pause
exit /b 1
