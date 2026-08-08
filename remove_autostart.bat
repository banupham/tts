@echo off
setlocal
chcp 65001 >nul

set "LAUNCHER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\VieNeuTTS.cmd"

if exist "%LAUNCHER%" (
    del /q "%LAUNCHER%"
    echo Da go tu khoi dong VieNeu TTS.
) else (
    echo Khong tim thay launcher tu khoi dong.
)

pause
