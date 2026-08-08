# Kịch bản nhiều giọng

`tao_truyen.py` hỗ trợ một file kịch bản chứa lẫn giọng kể chuyện, nam và nữ.

## Khóa vai

```text
[NARRATOR]
Phần người dẫn chuyện.

[NAM]
Phần thoại nam.

[NU]
Phần thoại nữ.
```

Có thể dùng alias `[NGUOI_KE]`, `[KE_CHUYEN]`, `[MALE]`, `[FEMALE]`. Khóa có hiệu lực cho tới khi gặp khóa tiếp theo. Phần văn bản đứng trước khóa đầu tiên được coi là `NARRATOR`.

Ví dụ:

```text
[NARRATOR]
Đêm đó, Nam trở về căn nhà cũ.

[NAM]
Có ai ở trong đó không?

[NU]
Anh... cuối cùng anh cũng quay lại.

[NAM]
Cô là ai?
```

## Cấu hình giọng

Chỉnh `voice_roles.json`:

```json
{
  "NARRATOR": {
    "voice": "Minh Đức",
    "style": "doc_truyen",
    "temperature": 0.76
  },
  "NAM": {
    "voice": "Minh Đức",
    "style": "tu_nhien",
    "temperature": 0.78
  },
  "NU": {
    "voice": null,
    "style": "tu_nhien",
    "temperature": 0.80
  }
}
```

Nếu `NU.voice` là `null`, script đọc `/voices` và thử tự chọn preset có nhãn nữ. Để cố định tuyệt đối, lấy ID thật bằng:

```cmd
curl http://127.0.0.1:8765/voices
```

rồi điền ID vào `voice_roles.json`.

## Chạy

```cmd
.venv\Scripts\python.exe tao_truyen.py examples\kich_ban_nam_nu.txt
```

File cuối nằm trong `outputs\`. Các đoạn riêng có tên theo vai, ví dụ:

```text
001_NARRATOR.wav
002_NAM.wav
003_NU.wav
```

## Override nhanh từ command line

```cmd
.venv\Scripts\python.exe tao_truyen.py kich_ban.txt --voice-narrator "VOICE_KE" --voice-nam "VOICE_NAM" --voice-nu "VOICE_NU"
```

Kịch bản cũ không có khóa vẫn chạy như trước và vẫn hỗ trợ `--voice`.
