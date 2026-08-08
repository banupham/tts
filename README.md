# Local VieNeu TTS Service

Dịch vụ TTS tiếng Việt chạy local bằng VieNeu-TTS. Model được nạp một lần và giữ thường trực trong RAM. Repo hiện có hai server độc lập:

- **TTS API** tại `127.0.0.1:8765` để sinh audio.
- **Voice Library LAN** tại `0.0.0.0:8766` để mở trình duyệt trên điện thoại/PC khác, xem toàn bộ audio đã tạo và phát lại trực tiếp.

Phiên bản VieNeu đang pin: `vieneu==3.2.4`.

## Thành phần

- `tts_server.py` — server sinh TTS thường trực.
- `voice_library_server.py` — thư viện audio trên web cho mạng LAN.
- `noi.py` — tạo nhanh một WAV; mặc định lưu vào `outputs\voice_<timestamp>.wav`.
- `tao_truyen.py` — tạo truyện dài; mặc định lưu vào `outputs\truyen_<timestamp>.wav` và thư mục segment tương ứng.
- `install_windows.bat` — tạo `.venv` và cài dependency.
- `start_tts.bat` — chạy TTS API.
- `start_library.bat` — chạy Voice Library LAN.
- `start_all.bat` — chạy cả hai server.
- `test_tts.bat` — test nhanh TTS.
- `allow_lan_firewall.bat` — mở TCP port 8766 trên Windows Firewall cho mạng Private; cần Run as administrator.
- `install_autostart.bat` — tự chạy cả hai server khi đăng nhập Windows.
- `remove_autostart.bat` — gỡ tự khởi động.
- `examples/truyen_mau.txt` — truyện mẫu.

## Cài nhanh trên Windows

```cmd
git clone https://github.com/banupham/tts.git
cd tts
install_windows.bat
```

Sau đó chạy cả hai server:

```cmd
start_all.bat
```

Hoặc chạy riêng:

```cmd
start_tts.bat
start_library.bat
```

## Voice Library trên trình duyệt

Trên chính máy chủ:

```text
http://127.0.0.1:8766
```

Trên điện thoại hoặc máy khác cùng Wi-Fi/LAN:

```text
http://IP_MAY_CHU:8766
```

Ví dụ:

```text
http://192.168.1.20:8766
```

Xem IP máy chủ bằng:

```cmd
ipconfig
```

Tìm dòng `IPv4 Address` của card mạng đang dùng.

Web Library có:

- tự quét toàn bộ WAV/MP3/FLAC/OGG/M4A/AAC trong thư mục audio;
- tìm kiếm theo tên file/thư mục;
- sắp xếp mới nhất, cũ nhất, A-Z;
- phát từng file bằng audio player của trình duyệt;
- `Phát tất cả` theo danh sách hiện đang lọc;
- nút Refresh để thấy file mới mà không cần restart server;
- tải file về máy client.

Mặc định Library quét:

```text
<repo>\outputs
```

Nếu muốn quét thêm các thư mục audio cũ trên PC, đặt nhiều root cách nhau bằng dấu `;` trước khi chạy:

```cmd
set VOICE_LIBRARY_ROOTS=C:\Users\duong\Desktop\tts\outputs;D:\voice;D:\truyen_audio
start_library.bat
```

Server chỉ cho đọc các file audio nằm bên trong các root đã cấu hình.

## Nếu điện thoại không mở được cổng 8766

Đảm bảo hai thiết bị cùng LAN/Wi-Fi. Sau đó chạy:

```cmd
allow_lan_firewall.bat
```

bằng **Run as administrator**. Rule chỉ mở TCP port 8766 cho profile mạng Private.

## Tạo voice nhanh

Khi TTS server 8765 đã chạy:

```cmd
.venv\Scripts\python.exe noi.py "Đừng mở cánh cửa đó."
```

Không chỉ định `--output` thì file tự vào `outputs\` với tên timestamp, vì vậy Voice Library sẽ thấy ngay sau khi Refresh.

Có thể chọn giọng/style:

```cmd
.venv\Scripts\python.exe noi.py "Đêm hôm đó, tôi nghe thấy tiếng bước chân." --voice "Minh Đức" --style doc_truyen
```

Hoặc chỉ định file riêng:

```cmd
.venv\Scripts\python.exe noi.py "Xin chào" --output outputs\test.wav
```

Danh sách voice preset:

```cmd
curl http://127.0.0.1:8765/voices
```

## Tạo cả truyện

```cmd
.venv\Scripts\python.exe tao_truyen.py examples\truyen_mau.txt
```

Nếu bỏ `--output`, file hoàn chỉnh và các segment đều nằm trong `outputs\`, nên web Library có thể phát cả bản hoàn chỉnh lẫn từng đoạn.

Có thể chỉ định tên file:

```cmd
.venv\Scripts\python.exe tao_truyen.py truyen.txt --output outputs\truyen_ma.wav
```

## TTS API

### `GET /health`

Kiểm tra server/model.

### `GET /voices`

Danh sách voice preset.

### `POST /tts`

```json
{
  "text": "Đêm hôm đó... tôi tỉnh giấc lúc ba giờ sáng.",
  "voice": null,
  "style": "doc_truyen",
  "temperature": 0.78,
  "top_k": 25,
  "top_p": 0.93,
  "max_chars": 200
}
```

Phản hồi là `audio/wav`.

## Cấu hình TTS server

```cmd
set TTS_HOST=127.0.0.1
set TTS_PORT=8765
set TTS_PRECISION=int8
set TTS_THREADS=0
set TTS_WARMUP=1
start_tts.bat
```

Chất lượng cao hơn trên CPU:

```cmd
set TTS_PRECISION=fp32
start_tts.bat
```

## Cấu hình Voice Library

Các biến hỗ trợ:

- `VOICE_LIBRARY_HOST` — mặc định `0.0.0.0`.
- `VOICE_LIBRARY_PORT` — mặc định `8766`.
- `VOICE_LIBRARY_MAX_FILES` — mặc định `5000`.
- `VOICE_LIBRARY_ROOTS` — danh sách thư mục quét, cách nhau bằng `;`; mặc định là `<repo>\outputs`.

## Chạy thường trực cùng Windows

Sau khi đã cài `.venv`:

```cmd
install_autostart.bat
```

Từ lần đăng nhập tiếp theo sẽ tự chạy cả cổng 8765 và 8766.

Gỡ:

```cmd
remove_autostart.bat
```

## Warm-up và chất lượng

Server TTS mặc định warm-up một câu khi khởi động để giảm nguy cơ méo ở lần infer đầu tiên. Preset sampling mặc định:

- `temperature = 0.78`
- `top_k = 25`
- `top_p = 0.93`
- `max_chars = 200`

Nếu cần ổn định hơn, giảm `temperature` về khoảng `0.70–0.75`. Tăng temperature có thể biểu cảm hơn nhưng độ ổn định giảm.

## File nặng

Repo không commit model, `.venv`, cache Hugging Face, `outputs` hay audio sinh ra. Toàn bộ audio vẫn nằm trên PC của bạn.