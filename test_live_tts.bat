@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo Gui 3 cau vao Live TTS Queue...

echo [1/3] Comment thuong - priority 50
curl -s -X POST http://127.0.0.1:8770/speak -H "Content-Type: application/json" -d "{\"text\":\"Xin chao. Day la cau binh luan thuong.\",\"priority\":50,\"style\":\"tu_nhien\"}"
echo.

echo [2/3] Follow - priority 20
curl -s -X POST http://127.0.0.1:8770/speak -H "Content-Type: application/json" -d "{\"text\":\"Cam on ban vua theo doi kenh.\",\"priority\":20,\"style\":\"tu_nhien\"}"
echo.

echo [3/3] Gift - priority 10
curl -s -X POST http://127.0.0.1:8770/speak -H "Content-Type: application/json" -d "{\"text\":\"Cam on mon qua cua ban.\",\"priority\":10,\"style\":\"tu_nhien\"}"
echo.
echo.
echo Neu cau dau dang phat, no se phat het. Cac cau dang cho duoc sap theo priority nho hon truoc.
pause
