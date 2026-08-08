import argparse
import io
import json
import re
import sys
import time
import unicodedata
from datetime import datetime
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


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = BASE_DIR / "outputs"
DEFAULT_ROLE_CONFIG = BASE_DIR / "voice_roles.json"
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")
ROLE_TAG_RE = re.compile(r"^\s*\[([^\]]+)\]\s*(.*)$")

ROLE_ALIASES = {
    "NARRATOR": "NARRATOR",
    "NGUOI_KE": "NARRATOR",
    "KE_CHUYEN": "NARRATOR",
    "VOICE_OVER": "NARRATOR",
    "NAM": "NAM",
    "MALE": "NAM",
    "NU": "NU",
    "FEMALE": "NU",
}


def default_story_output() -> Path:
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return DEFAULT_OUTPUT_DIR / f"truyen_{stamp}.wav"


def _normalize_tag(value: str) -> str:
    value = unicodedata.normalize("NFD", value.strip().upper())
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return re.sub(r"[\s\-]+", "_", value)


def _canonical_role(raw_tag: str) -> str | None:
    return ROLE_ALIASES.get(_normalize_tag(raw_tag))


def parse_role_script(text: str) -> tuple[list[tuple[str, str]], bool]:
    """
    Đọc kịch bản có khóa [NARRATOR], [NAM], [NU].
    Mỗi khóa có hiệu lực cho tới khóa tiếp theo.
    Phần đứng trước khóa đầu tiên mặc định là NARRATOR.
    """
    sections: list[tuple[str, str]] = []
    current_role = "NARRATOR"
    buffer: list[str] = []
    has_role_tags = False

    def flush() -> None:
        nonlocal buffer
        content = "\n".join(buffer).strip()
        if content:
            sections.append((current_role, content))
        buffer = []

    for raw_line in text.splitlines():
        match = ROLE_TAG_RE.match(raw_line)
        if match:
            role = _canonical_role(match.group(1))
            if role is not None:
                flush()
                current_role = role
                has_role_tags = True
                remainder = match.group(2).strip()
                if remainder:
                    buffer.append(remainder)
                continue

        buffer.append(raw_line)

    flush()
    return sections, has_role_tags


def _split_long_piece(text: str, max_chars: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]
    if len(sentences) == 1:
        sentences = [s.strip() for s in re.split(r"(?<=[,;:])\s+", text) if s.strip()]

    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        if len(sentence) > max_chars:
            if current:
                chunks.append(current)
                current = ""

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
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    pieces: list[str] = []

    for paragraph in paragraphs:
        paragraph = re.sub(r"\s*\n\s*", " ", paragraph).strip()
        pieces.extend(_split_long_piece(paragraph, max_chars))

    merged: list[str] = []
    min_chars = min(70, max_chars // 3)

    for piece in pieces:
        if merged and len(piece) < min_chars and len(merged[-1]) + 1 + len(piece) <= max_chars:
            merged[-1] = f"{merged[-1]} {piece}".strip()
        else:
            merged.append(piece)

    return merged


def build_role_chunks(text: str, max_chars: int) -> tuple[list[tuple[str, str]], bool]:
    sections, has_role_tags = parse_role_script(text)
    chunks: list[tuple[str, str]] = []

    for role, content in sections:
        for chunk in split_story(content, max_chars=max_chars):
            chunks.append((role, chunk))

    return chunks, has_role_tags


def _default_role_settings() -> dict[str, dict]:
    return {
        "NARRATOR": {
            "voice": "Minh Đức",
            "style": "doc_truyen",
            "temperature": 0.76,
        },
        "NAM": {
            "voice": "Minh Đức",
            "style": "tu_nhien",
            "temperature": 0.78,
        },
        "NU": {
            "voice": None,
            "style": "tu_nhien",
            "temperature": 0.80,
        },
    }


def load_role_settings(config_path: Path) -> dict[str, dict]:
    settings = _default_role_settings()

    if not config_path.exists():
        return settings

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("voice_roles.json phải là JSON object")

    for raw_role, values in raw.items():
        role = _canonical_role(raw_role)
        if role is None or not isinstance(values, dict):
            continue

        if "voice" in values:
            voice = values["voice"]
            settings[role]["voice"] = None if voice in ("", None) else str(voice)

        if "style" in values:
            style = str(values["style"])
            if style not in {"tu_nhien", "tin_tuc", "doc_truyen"}:
                raise ValueError(f"style không hợp lệ cho {role}: {style}")
            settings[role]["style"] = style

        if "temperature" in values:
            settings[role]["temperature"] = float(values["temperature"])

    return settings


def fetch_voice_catalog(session: requests.Session, server: str) -> list[dict]:
    response = session.get(server.rstrip("/") + "/voices", timeout=30)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise RuntimeError("/voices trả về dữ liệu không hợp lệ")
    return data


def _find_voice_by_id(catalog: list[dict], voice_id: str) -> str | None:
    wanted = voice_id.casefold()
    for item in catalog:
        current = str(item.get("id", ""))
        if current.casefold() == wanted:
            return current
    return None


def _auto_voice(catalog: list[dict], role: str) -> str | None:
    if not catalog:
        return None

    if role == "NARRATOR":
        exact = _find_voice_by_id(catalog, "Minh Đức")
        if exact:
            return exact
        role = "NAM"

    markers = ("NU", "FEMALE") if role == "NU" else ("NAM", "MALE")

    for item in catalog:
        label = _normalize_tag(str(item.get("label", "")))
        voice_id = str(item.get("id", "")).strip()
        if voice_id and any(marker in label for marker in markers):
            return voice_id

    return None


def resolve_role_settings(
    session: requests.Session,
    server: str,
    settings: dict[str, dict],
    *,
    voice_legacy: str | None,
    voice_narrator: str | None,
    voice_nam: str | None,
    voice_nu: str | None,
    has_role_tags: bool,
) -> dict[str, dict]:
    catalog = fetch_voice_catalog(session, server)

    overrides = {
        "NARRATOR": voice_narrator,
        "NAM": voice_nam,
        "NU": voice_nu,
    }

    if not has_role_tags and voice_legacy:
        overrides["NARRATOR"] = voice_legacy

    resolved = {role: dict(values) for role, values in settings.items()}

    for role in ("NARRATOR", "NAM", "NU"):
        if overrides[role]:
            resolved[role]["voice"] = overrides[role]

        configured = resolved[role].get("voice")
        if configured:
            exact = _find_voice_by_id(catalog, str(configured))
            if exact is None:
                raise RuntimeError(
                    f"Voice '{configured}' của {role} không có trong /voices. "
                    "Chạy curl http://127.0.0.1:8765/voices để xem ID đúng."
                )
            resolved[role]["voice"] = exact
            continue

        automatic = _auto_voice(catalog, role)
        if automatic:
            resolved[role]["voice"] = automatic
            continue

        if role == "NU" and has_role_tags:
            raise RuntimeError(
                "Kịch bản có [NU] nhưng chưa xác định được voice nữ. "
                "Hãy đặt voice cho NU trong voice_roles.json hoặc dùng --voice-nu \"VOICE_ID\"."
            )

    return resolved


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

    parts.pop()
    return np.concatenate(parts)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Tạo truyện dài một hoặc nhiều giọng bằng VieNeu local server"
    )
    parser.add_argument("input", help="File TXT UTF-8 chứa truyện/kịch bản")
    parser.add_argument(
        "--output",
        default=None,
        help="File đầu ra. Bỏ trống để tự lưu vào outputs\\truyen_<timestamp>.wav",
    )
    parser.add_argument("--server", default="http://127.0.0.1:8765")
    parser.add_argument(
        "--role-config",
        default=str(DEFAULT_ROLE_CONFIG),
        help="JSON cấu hình voice/style/temperature cho NARRATOR, NAM, NU",
    )
    parser.add_argument(
        "--voice",
        default=None,
        help="Tương thích kịch bản cũ: voice cho truyện không có tag vai",
    )
    parser.add_argument("--voice-narrator", default=None)
    parser.add_argument("--voice-nam", default=None)
    parser.add_argument("--voice-nu", default=None)
    parser.add_argument(
        "--style",
        default=None,
        choices=["tu_nhien", "tin_tuc", "doc_truyen"],
        help="Override style cho toàn bộ vai",
    )
    parser.add_argument("--chunk-chars", type=int, default=220)
    parser.add_argument("--server-max-chars", type=int, default=180)
    parser.add_argument("--pause-ms", type=int, default=450)
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Override temperature cho toàn bộ vai",
    )
    parser.add_argument("--top-k", type=int, default=25)
    parser.add_argument("--top-p", type=float, default=0.93)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--keep-going", action="store_true")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Không tìm thấy file: {input_path}")
        return 2

    story = input_path.read_text(encoding="utf-8").strip()
    if not story:
        print("File truyện rỗng.")
        return 2

    role_chunks, has_role_tags = build_role_chunks(story, max_chars=args.chunk_chars)
    if not role_chunks:
        print("Không chia được đoạn nào.")
        return 2

    session = requests.Session()

    try:
        health = session.get(args.server.rstrip("/") + "/health", timeout=10)
        health.raise_for_status()
        print("Server:", health.json())
    except Exception as exc:
        print(f"Không kết nối được TTS server: {exc}")
        return 1

    try:
        role_settings = load_role_settings(Path(args.role_config))
        role_settings = resolve_role_settings(
            session,
            args.server,
            role_settings,
            voice_legacy=args.voice,
            voice_narrator=args.voice_narrator,
            voice_nam=args.voice_nam,
            voice_nu=args.voice_nu,
            has_role_tags=has_role_tags,
        )
    except Exception as exc:
        print(f"Lỗi cấu hình voice: {exc}")
        return 2

    if args.style:
        for values in role_settings.values():
            values["style"] = args.style

    if args.temperature is not None:
        for values in role_settings.values():
            values["temperature"] = args.temperature

    roles_used: list[str] = []
    for role, _ in role_chunks:
        if role not in roles_used:
            roles_used.append(role)

    print()
    print("=" * 72)
    print("CHẾ ĐỘ:", "KỊCH BẢN NHIỀU GIỌNG" if has_role_tags else "TRUYỆN MỘT GIỌNG")
    print(f"Tổng số đoạn: {len(role_chunks)}")
    for role in roles_used:
        cfg = role_settings[role]
        print(
            f"{role:10s} -> voice={cfg.get('voice') or '(default)'} | "
            f"style={cfg['style']} | temp={cfg['temperature']}"
        )
    print("=" * 72)

    output_path = Path(args.output) if args.output else default_story_output()
    if not output_path.is_absolute():
        output_path = Path.cwd() / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    segment_dir = output_path.with_suffix("")
    segment_dir = segment_dir.parent / f"{segment_dir.name}_segments"
    segment_dir.mkdir(parents=True, exist_ok=True)

    segments: list[np.ndarray] = []
    target_sr: int | None = None
    failed: list[int] = []
    total_started = time.perf_counter()

    for index, (role, chunk) in enumerate(role_chunks, start=1):
        cfg = role_settings[role]

        print()
        print("=" * 72)
        print(
            f"Đoạn {index}/{len(role_chunks)} | {role} | "
            f"voice={cfg.get('voice') or '(default)'} | {len(chunk)} ký tự"
        )
        print(chunk)
        print("=" * 72)

        try:
            audio, sample_rate, elapsed = request_tts(
                session,
                args.server,
                chunk,
                voice=cfg.get("voice"),
                style=cfg["style"],
                temperature=float(cfg["temperature"]),
                top_k=args.top_k,
                top_p=args.top_p,
                server_max_chars=args.server_max_chars,
                retries=args.retries,
            )

            if target_sr is None:
                target_sr = sample_rate
            elif sample_rate != target_sr:
                raise RuntimeError(
                    f"Sample rate thay đổi: trước {target_sr} Hz, đoạn này {sample_rate} Hz"
                )

            segment_path = segment_dir / f"{index:03d}_{role}.wav"
            sf.write(segment_path, audio, sample_rate, subtype="PCM_16")
            segments.append(audio)

            print(f"OK: {elapsed:.2f} giây -> {segment_path}")

        except Exception as exc:
            print(f"LỖI đoạn {index} ({role}): {exc}")
            failed.append(index)
            if not args.keep_going:
                print(
                    "Dừng để tránh tạo file truyện bị thiếu. "
                    "Dùng --keep-going nếu muốn bỏ qua đoạn lỗi."
                )
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
