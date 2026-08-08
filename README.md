# Local VieNeu TTS Service

Dịch vụ TTS tiếng Việt chạy local bằng VieNeu-TTS. Model được nạp một lần và giữ thường trực trong RAM.

Hệ thống hiện có 3 dịch vụ:

- **TTS API** `127.0.0.1:8765` — tạo WAV và stream audio realtime.
- **Voice Library LAN** `0.0.0.0:8766` — nghe lại audio đã tạo bằng trình duyệt.
- **Live TTS Queue** `127.0.0.1:8770` — nhận text từ middleware/live, xếp hàng và phát loa realtime.

Phiên bản VieNeu đang pin: `vieneu==3.2.4`.

## Thành phần

- `tts_server.py` — TTS server thường trực; `POST /tts` và `POST /tts/stream`.
- `live_tts.py` — hàng đợi realtime, nhận text và phát PCM stream ra loa.
- `voice_library_server.py` — thư viện audio trên web cho mạng LAN.
- `noi.py` — tạo nhanh một WAV; mặc định lưu vào `outputs\voice_<timestamp>.wav`.
- `tao_truyen.py` — tạo truyện dài/multi-voice.
- `voice_roles.json` — cấu hình voice cho `[NARRATOR]`, `[NAM]`, `[NU]`.
- `start_tts.bat` — chạy TTS API.
- `start_library.bat` — chạy Voice Library.
- `start_live_tts.bat` — chạy Live TTS Queue.
- `start_all.bat` — chạy cả 3 dịch vụ.
- `test_live_tts.bat` — gửi thử nhiều câu với priority khác nhau.

## Cài nhanh trên Windows

```cmd
git clone https://github.com/banupham/tts.git
cd tts
install_windows.bat
```

Nếu repo đã cài từ trước và vừa `git pull`, cài thêm dependency mới:

```cmd
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Chạy toàn bộ:

```cmd
start_all.bat
```

Các cổng local:

```text
TTS API        http://127.0.0.1:8765
Voice Library  http://127.0.0.1:8766
Live TTS Queue http://127.0.0.1:8770
```

## Realtime TTS cho LIVE

VieNeu sinh audio bằng `infer_stream()`. `tts_server.py` chuyển từng phần audio thành **mono PCM16 little-endian 48 kHz** và gửi ngay qua HTTP, không chờ tạo xong toàn bộ câu.

### Stream trực tiếp

Endpoint:

```text
POST http://127.0.0.1:8765/tts/stream
```

Body giống `/tts`:

```json
{
  "text": "Cảm ơn bạn vừa follow!",
  "voice": "Minh Đức",
  "style": "tu_nhien",
  "temperature": 0.78,
  "top_k": 25,
  "top_p": 0.93,
  "max_chars": 180
}
```

Response là raw PCM stream. Header quan trọng:

```text
X-TTS-Sample-Rate: 48000
X-TTS-Channels: 1
X-TTS-Format: s16le
```

### Cách dễ nhất cho middleware: Live TTS Queue

Middleware không cần tự phát PCM. Chỉ cần POST text vào:

```text
POST http://127.0.0.1:8770/speak
```

Ví dụ CMD:

```cmd
curl -X POST http://127.0.0.1:8770/speak -H "Content-Type: application/json" -d "{\"text\":\"Cảm ơn bạn vừa follow!\",\"priority\":20,\"style\":\"tu_nhien\"}"
```

Queue sẽ:

1. nhận text;
2. xếp hàng theo `priority`;
3. gọi `/tts/stream`;
4. phát chunk đầu ngay khi nhận được;
5. tiếp tục phát các chunk sau;
6. đọc xong mới chuyển sang câu kế tiếp.

**Câu đang phát không bị cắt ngang.** Priority chỉ sắp xếp các câu còn đang chờ.

Gợi ý priority cho live:

```text
GIFT    = 10
FOLLOW  = 20
COMMENT = 50
JOIN    = 80
```

Số nhỏ hơn được ưu tiên trước.

Kiểm tra trạng thái queue:

```cmd
curl http://127.0.0.1:8770/health
```

Xóa các câu đang chờ, không cắt câu đang phát:

```cmd
curl -X POST http://127.0.0.1:8770/clear
```

Test nhanh:

```cmd
test_live_tts.bat
```

## Voice Library trên trình duyệt

Trên máy chủ:

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

Xem IP bằng `ipconfig`. Nếu Windows Firewall chặn port 8766, chạy `allow_lan_firewall.bat` bằng **Run as administrator**.

Library mặc định quét `<repo>\outputs`. Có thể thêm nhiều thư mục:

```cmd
set VOICE_LIBRARY_ROOTS=C:\Users\duong\Desktop\tts\outputs;D:\voice;D:\truyen_audio
start_library.bat
```

## Tạo voice WAV nhanh

Khi TTS server 8765 đang chạy:

```cmd
.venv\Scripts\python.exe noi.py "Đừng mở cánh cửa đó."
```

Chọn voice/style:

```cmd
.venv\Scripts\python.exe noi.py "Đêm hôm đó, tôi nghe thấy tiếng bước chân." --voice "Minh Đức" --style doc_truyen
```

Danh sách preset:

```cmd
curl http://127.0.0.1:8765/voices
```

## Tạo truyện

Kịch bản thường:

```cmd
.venv\Scripts\python.exe tao_truyen.py truyen.txt
```

Kịch bản nhiều giọng:

```text
[NARRATOR]
Đêm đó, Nam trở về căn nhà cũ.

[NAM]
Có ai ở trong đó không?

[NU]
Anh... cuối cùng anh cũng quay lại.
```

Chạy:

```cmd
.venv\Scripts\python.exe tao_truyen.py examples\kich_ban_nam_nu.txt
```

Cấu hình giọng nằm trong `voice_roles.json`.

## TTS API

### `GET /health`

Kiểm tra model và khả năng streaming.

### `GET /voices`

Danh sách voice preset.

### `POST /tts`

Tạo xong toàn bộ câu rồi trả `audio/wav`. Dùng cho lưu file/truyện.

### `POST /tts/stream`

Sinh và trả audio từng chunk dưới dạng PCM16 realtime. Dùng cho live/chatbot/tương tác.

## Cấu hình TTS server

```cmd
set TTS_HOST=127.0.0.1
set TTS_PORT=8765
set TTS_PRECISION=int8
set TTS_THREADS=0
set TTS_WARMUP=1
start_tts.bat
```

CPU chất lượng cao hơn nhưng chậm hơn:

```cmd
set TTS_PRECISION=fp32
start_tts.bat
```

## Cấu hình Live TTS Queue

Mặc định:

```cmd
set LIVE_TTS_HOST=127.0.0.1
set LIVE_TTS_PORT=8770
set LIVE_TTS_SERVER=http://127.0.0.1:8765
start_live_tts.bat
```

`LIVE_TTS_HOST=127.0.0.1` cố ý chỉ cho phần mềm trên chính PC truy cập. Chỉ đổi sang `0.0.0.0` nếu thật sự cần nhận text từ máy khác trong LAN và đã kiểm soát firewall.

## Chạy cùng Windows

```cmd
install_autostart.bat
```

Từ lần đăng nhập tiếp theo, `start_all.bat` sẽ bật:

```text
8765 TTS API
8766 Voice Library
8770 Live TTS Queue
```

Gỡ:

```cmd
remove_autostart.bat
```

## Warm-up và chất lượng

Mặc định:

```text
temperature = 0.78
top_k       = 25
top_p       = 0.93
max_chars   = 200
```

Nếu cần ổn định hơn, thử giảm `temperature` về `0.70–0.75`.

## File nặng

Repo không commit model, `.venv`, cache Hugging Face, `outputs` hoặc audio sinh ra. Audio vẫn nằm trên PC.