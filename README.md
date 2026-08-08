# Local VieNeu TTS Service

Dịch vụ TTS tiếng Việt chạy local bằng VieNeu-TTS, thiết kế để model được nạp một lần và giữ thường trực trong RAM. Các chương trình khác có thể gọi HTTP API để tạo WAV, xem danh sách giọng, hoặc tạo truyện dài theo từng đoạn.

Phiên bản VieNeu đang pin trong repo: `vieneu==3.2.4`.

## Thành phần

- `tts_server.py` — server FastAPI thường trực tại `127.0.0.1:8765`
- `noi.py` — client CLI tạo nhanh một file WAV từ một câu
- `tao_truyen.py` — chia truyện dài thành các đoạn tự nhiên, tạo từng WAV rồi ghép lại
- `requirements.txt` — thư viện Python cần cài
- `install_windows.bat` — tạo `.venv` và cài thư viện trên Windows
- `start_tts.bat` — khởi động server bằng `.venv`, không cần activate thủ công
- `test_tts.bat` — test nhanh server và tạo `test_output.wav`
- `install_autostart.bat` — tự chạy TTS khi đăng nhập Windows
- `remove_autostart.bat` — gỡ tự khởi động
- `examples/truyen_mau.txt` — văn bản mẫu để test
- `.github/workflows/syntax-check.yml` — kiểm tra cú pháp Python trên GitHub Actions

## Cài nhanh trên Windows

Yêu cầu: Python 3.10+ đã có trong PATH.

```cmd
git clone https://github.com/banupham/tts.git
cd tts
install_windows.bat
```

Sau khi cài xong:

```cmd
start_tts.bat
```

Đợi dòng:

```text
TTS SERVER READY: http://127.0.0.1:8765
```

Giữ cửa sổ server mở. Model chỉ được nạp một lần khi server khởi động.

## Chạy thường trực cùng Windows

Sau khi đã cài `.venv`, chạy một lần:

```cmd
install_autostart.bat
```

Từ lần đăng nhập Windows tiếp theo, `start_tts.bat` sẽ tự chạy ở trạng thái thu nhỏ.

Muốn gỡ:

```cmd
remove_autostart.bat
```

## Test server

Cách nhanh nhất:

```cmd
test_tts.bat
```

Hoặc mở:

```text
http://127.0.0.1:8765/docs
```

Hoặc CMD:

```cmd
curl http://127.0.0.1:8765/health
curl http://127.0.0.1:8765/voices
```

## Tạo voice nhanh

```cmd
.venv\Scripts\python.exe noi.py "Đừng mở cánh cửa đó."
```

Mặc định tạo `output.wav`.

Có thể chọn giọng/style:

```cmd
.venv\Scripts\python.exe noi.py "Đêm hôm đó, tôi nghe thấy tiếng bước chân." --voice "Minh Đức" --style doc_truyen --output ma.wav
```

Nếu tên giọng không đúng với phiên bản VieNeu đang cài, xem danh sách bằng:

```cmd
curl http://127.0.0.1:8765/voices
```

## Tạo cả truyện

Đặt nội dung UTF-8 vào `truyen.txt`, sau đó:

```cmd
.venv\Scripts\python.exe tao_truyen.py truyen.txt --output truyen_ma.wav
```

Hoặc dùng file mẫu:

```cmd
.venv\Scripts\python.exe tao_truyen.py examples\truyen_mau.txt --output truyen_ma.wav
```

Script sẽ:

1. Chia văn bản theo đoạn/câu tự nhiên.
2. Gửi từng đoạn tới server.
3. Lưu riêng từng segment trong thư mục `<ten_output>_segments`.
4. Đọc WAV bằng `soundfile`, kiểm tra sample rate và ghép bằng NumPy.
5. Chèn khoảng nghỉ giữa các đoạn.

Nếu một đoạn đọc chưa đạt, nghe file segment tương ứng rồi tạo lại riêng đoạn đó thay vì dựng lại cả truyện.

## API

### `GET /health`

Kiểm tra server/model.

### `GET /voices`

Danh sách voice preset mà VieNeu hiện có.

### `POST /tts`

Ví dụ JSON:

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

## Cấu hình server bằng biến môi trường

Mặc định server dùng CPU/ONNX int8 để nhẹ và nhanh:

```cmd
set TTS_HOST=127.0.0.1
set TTS_PORT=8765
set TTS_PRECISION=int8
start_tts.bat
```

Nếu muốn thử chất lượng cao hơn trên CPU:

```cmd
set TTS_PRECISION=fp32
start_tts.bat
```

Lần đầu dùng `fp32` có thể phải tải thêm model/cache và sẽ chậm hơn int8.

Các biến hỗ trợ:

- `TTS_HOST` — mặc định `127.0.0.1`
- `TTS_PORT` — mặc định `8765`
- `TTS_PRECISION` — `int8` hoặc `fp32`
- `TTS_THREADS` — `0` để engine tự chọn
- `TTS_WARMUP` — `1` bật warm-up, `0` tắt

## Vì sao có warm-up?

Một số máy có thể gặp artifact/méo ở lần infer đầu tiên sau khi load model. Server mặc định sinh một câu rất ngắn khi khởi động rồi bỏ kết quả đó đi. Request thật đầu tiên vì thế không còn là lần infer đầu của engine.

## Lưu ý chất lượng

VieNeu là mô hình sinh có sampling nên cùng một câu có thể cho ngữ điệu khác nhau giữa các lần. Preset mặc định của server cân bằng giữa ổn định và biểu cảm:

- `temperature = 0.78`
- `top_k = 25`
- `top_p = 0.93`
- `max_chars = 200`

Nếu cần ổn định hơn, giảm `temperature` xuống khoảng `0.70–0.75`. Nếu muốn biểu cảm hơn, tăng nhẹ nhưng khả năng phát sinh take kém cũng tăng.

## Mở cho thiết bị khác trong LAN

Mặc định chỉ máy local truy cập được. Nếu cần điện thoại/PC khác trong LAN gọi TTS:

```cmd
set TTS_HOST=0.0.0.0
start_tts.bat
```

Khi mở ra LAN nên bổ sung API key/firewall trước khi dùng lâu dài.

## Không commit các file nặng

Repo không lưu model, `.venv`, cache Hugging Face hay WAV sinh ra. Model được tải về máy ở lần chạy đầu và giữ trong cache local.
