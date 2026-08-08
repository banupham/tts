@echo off
setlocal
chcp 65001 >nul

set PORT=8766
if not "%VOICE_LIBRARY_PORT%"=="" set PORT=%VOICE_LIBRARY_PORT%

echo Them Windows Firewall rule cho TCP port %PORT%...
echo Can chay file nay bang Run as administrator.
echo.

netsh advfirewall firewall add rule name="VieNeu Voice Library %PORT%" dir=in action=allow protocol=TCP localport=%PORT% profile=private
if errorlevel 1 (
    echo.
    echo [LOI] Khong them duoc firewall rule. Hay chuot phai file va chon Run as administrator.
    pause
    exit /b 1
)

echo.
echo Da mo TCP port %PORT% cho mang Private.
pause
