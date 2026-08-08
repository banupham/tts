import argparse
import io
import re
import sys
import time
from pathlib import Path
from typing import Iterable

import numpy as np
import requests
import soundfile as sf


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")


def _split_long_piece(text: str, max_chars: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]
    if len(sentences) == 1:
        # Fallback theo dấu phẩy/chấm phẩy nếu câu quá dài.
        sentences = [s.strip() for s in re.split(r"(?<=[,;:])\s+", text) if s.strip()]

    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        if len(sentence) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            # Trường hợp đặc biệt: một câu vẫn quá dài, cắt mềm theo khoảng trắng.
            words = sentence.split()
            part = ""
            for word in words:
                candidate = f"{part} {word}".strip()
                if part and len(candidate) > max_chars:
                    chunks.append(part)
                    part = word
                else:
                    part = candidate
            if part:
                chunks.append(part)
            continue

        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = sentence
        else:
            current = candidate

    if current:
        chunks.append(current)

    return chunks


def split_story(text: str, max_chars: int) -> list[str]:
    """Ưu tiên giữ ranh giới đoạn văn, sau đó mới chia theo câu."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    pieces: list[str] = []

    for paragraph in paragraphs:
        # Gộp newline đơn bên trong một đoạn thành khoảng trắng.
        paragraph = re.sub(r"\s*\n\s*", " ", paragraph).strip()
        pieces.extend(_split_long_piece(paragraph, max_chars))

    # Gộp các piece rất ngắn với piece sau/trước để tránh model nhận quá ít ngữ cảnh.
    merged: list[str] = []
    min_chars = min(70, max_chars // 3)

    for piece in pieces:
        if merged and len(piece) < min_chars and len(merged[-1]) + 1 + len(piece) <= max_chars:
            merged[-1] = f"{merged[-1]} {piece}".strip()
        else:
            merged.append(piece)

    return merged


def request_tts(
    session: requests.Session,
    server: str,
    text: str,
    *,
    voice: str | None,
    style: str,
    temperature: float,
    top_k: int,
    top_p: float,
    server_max_chars: int,
    retries: int,
) -> tuple[np.ndarray, int, float]:
    url = server.rstrip("/") + "/tts"
    payload = {
        "text": text,
        "voice": voice,
        "style": style,
        "temperature": temperature,
        "top_k": top_k,
        "top_p": top_p,
        "max_chars": server_max_chars,
    }

    last_error: Exception | None = None

    for attempt in range(1, retries + 2):
        try:
            started = time.perf_counter()
            response = session.post(url, json=payload, timeout=300)
            response.raise_for_status()
            elapsed = time.perf_counter() - started

            audio, sample_rate = sf.read(
                io.BytesIO(response.content),
                dtype="float32",
                always_2d=False,
            )
            audio = np.asarray(audio, dtype=np.float32)

            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            if audio.size == 0:
                raise RuntimeError("Server trả về WAV rỗng")

            return audio, int(sample_rate), elapsed

        except Exception as exc:
            last_error = exc
            if attempt <= retries:
                print(f"  Lỗi take {attempt}: {exc}. Thử lại...")
                time.sleep(1.0)
            else:
                break

    raise RuntimeError(f"Không tạo được đoạn sau {retries + 1} lần: {last_error}")


def concatenate_with_pause(
    segments: Iterable[np.ndarray],
    sample_rate: int,
    pause_ms: int,
) -> np.ndarray:
    silence = np.zeros(int(sample_rate * pause_ms / 1000), dtype=np.float32)
    parts: list[np.ndarray] = []

    for segment in segments:
        parts.append(np.asarray(segment, dtype=np.float32).reshape(-1))
        parts.append(silence)

    if not parts:
        return np.array([], dtype=np.float32)

    # Không cần khoảng nghỉ thừa ở cuối file.
    if parts and parts[-1] is silence:
        parts.pop()

    return np.concatenate(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Tạo voice cho truyện dài bằng VieNeu local server")
    parser.add_argument("input", help="File TXT UTF-8 chứa truyện")
    parser.add_argument("--output", default="truyen_ma.wav")
    parser.add_argument("--server", default="http://127.0.0.1:8765")
    parser.add_argument("--voice", default=None, help="Voice ID; bỏ trống để dùng default")
    parser.add_argument(
        "--style",
        default="doc_truyen",
        choices=["tu_nhien", "tin_tuc", "doc_truyen"],
    )
    parser.add_argument("--chunk-chars", type=int, default=220, help="Kích thước tối đa đoạn gửi từ client")
    parser.add_argument("--server-max-chars", type=int, default=180, help="max_chars truyền vào VieNeu infer")
    parser.add_argument("--pause-ms", type=int, default=600)
    parser.add_argument("--temperature", type=float, default=0.78)
    parser.add_argument("--top-k", type=int, default=25)
    parser.add_argument("--top-p", type=float, default=0.93)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--keep-going", action="store_true", help="Bỏ qua đoạn lỗi thay vì dừng")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Không tìm thấy file: {input_path}")
        return 2

    story = input_path.read_text(encoding="utf-8").strip()
    if not story:
        print("File truyện rỗng.")
        return 2

    chunks = split_story(story, max_chars=args.chunk_chars)
    if not chunks:
        print("Không chia được đoạn nào.")
        return 2

    print(f"Tổng số đoạn: {len(chunks)}")
    print(f"Chunk tối đa : {args.chunk_chars} ký tự")
    print(f"VieNeu max   : {args.server_max_chars} ký tự")
    print(f"Temperature  : {args.temperature}")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    segment_dir = output_path.with_suffix("")
    segment_dir = segment_dir.parent / f"{segment_dir.name}_segments"
    segment_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()

    try:
        health = session.get(args.server.rstrip("/") + "/health", timeout=10)
        health.raise_for_status()
        print("Server:", health.json())
    except Exception as exc:
        print(f"Không kết nối được TTS server: {exc}")
        return 1

    segments: list[np.ndarray] = []
    target_sr: int | None = None
    failed: list[int] = []
    total_started = time.perf_counter()

    for index, chunk in enumerate(chunks, start=1):
        print()
        print("=" * 72)
        print(f"Đoạn {index}/{len(chunks)} | {len(chunk)} ký tự")
        print(chunk)
        print("=" * 72)

        try:
            audio, sample_rate, elapsed = request_tts(
                session,
                args.server,
                chunk,
                voice=args.voice,
                style=args.style,
                temperature=args.temperature,
                top_k=args.top_k,
                top_p=args.top_p,
                server_max_chars=args.server_max_chars,
                retries=args.retries,
            )

            if target_sr is None:
                target_sr = sample_rate
            elif sample_rate != target_sr:
                raise RuntimeError(
                    f"Sample rate thay đổi: đoạn trước {target_sr} Hz, đoạn này {sample_rate} Hz"
                )

            segment_path = segment_dir / f"{index:03d}.wav"
            sf.write(segment_path, audio, sample_rate, subtype="PCM_16")
            segments.append(audio)

            print(f"OK: {elapsed:.2f} giây -> {segment_path}")

        except Exception as exc:
            print(f"LỖI đoạn {index}: {exc}")
            failed.append(index)
            if not args.keep_going:
                print("Dừng để tránh tạo file truyện bị thiếu. Dùng --keep-going nếu muốn bỏ qua đoạn lỗi.")
                return 1

    if target_sr is None or not segments:
        print("Không có audio hợp lệ để ghép.")
        return 1

    final_audio = concatenate_with_pause(segments, target_sr, args.pause_ms)
    sf.write(output_path, final_audio, target_sr, subtype="PCM_16")

    elapsed_total = time.perf_counter() - total_started
    duration = len(final_audio) / target_sr

    print()
    print("=" * 72)
    print("HOÀN THÀNH")
    print(f"File       : {output_path.resolve()}")
    print(f"Segments   : {segment_dir.resolve()}")
    print(f"Thời lượng : {duration:.1f} giây")
    print(f"Thời gian  : {elapsed_total:.1f} giây")
    if failed:
        print("Đoạn lỗi   :", ", ".join(map(str, failed)))
    print("=" * 72)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
