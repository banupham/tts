import argparse
import os
import sys
import time
from pathlib import Path

import requests


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Tạo WAV nhanh từ VieNeu local TTS server")
    parser.add_argument("text", nargs="*", help="Nội dung cần đọc")
    parser.add_argument("--server", default="http://127.0.0.1:8765")
    parser.add_argument("--voice", default=None, help="Voice ID; bỏ trống để dùng default")
    parser.add_argument(
        "--style",
        default="doc_truyen",
        choices=["tu_nhien", "tin_tuc", "doc_truyen"],
    )
    parser.add_argument("--temperature", type=float, default=0.78)
    parser.add_argument("--top-k", type=int, default=25)
    parser.add_argument("--top-p", type=float, default=0.93)
    parser.add_argument("--max-chars", type=int, default=200)
    parser.add_argument("--output", default="output.wav")
    parser.add_argument("--play", action="store_true", help="Mở file sau khi tạo trên Windows")
    args = parser.parse_args()

    text = " ".join(args.text).strip()
    if not text:
        text = input("Nhập nội dung: ").strip()

    if not text:
        print("Không có nội dung.")
        return 2

    url = args.server.rstrip("/") + "/tts"
    payload = {
        "text": text,
        "voice": args.voice,
        "style": args.style,
        "temperature": args.temperature,
        "top_k": args.top_k,
        "top_p": args.top_p,
        "max_chars": args.max_chars,
    }

    started = time.perf_counter()

    try:
        response = requests.post(url, json=payload, timeout=300)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"Lỗi gọi TTS server: {exc}")
        try:
            print("Phản hồi:", response.text)
        except Exception:
            pass
        return 1

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(response.content)

    elapsed = time.perf_counter() - started
    server_elapsed = response.headers.get("X-TTS-Elapsed-Seconds")

    print(f"Đã tạo: {output.resolve()}")
    print(f"Tổng thời gian client: {elapsed:.2f} giây")
    if server_elapsed:
        print(f"Thời gian infer server: {server_elapsed} giây")

    if args.play and os.name == "nt":
        os.startfile(str(output.resolve()))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
