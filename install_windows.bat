@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo  CAI DAT LOCAL VIENEU TTS
echo ============================================================

where python >nul 2>nul
if errorlevel 1 (
    echo [LOI] Khong tim thay Python trong PATH.
    echo Hay cai Python 3.10+ va chon Add Python to PATH.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Tao virtual environment .venv...
    python -m venv .venv
    if errorlevel 1 goto :error
) else (
    echo [1/3] .venv da ton tai, bo qua.
)

echo [2/3] Nang cap pip...
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto :error

echo [3/3] Cai dependencies...
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo ============================================================
echo  CAI DAT XONG
echo ============================================================
echo Khoi dong server bang:
echo   start_tts.bat
echo.
pause
exit /b 0

:error
echo.
echo [LOI] Cai dat that bai. Xem thong bao phia tren.
pause
exit /b 1
