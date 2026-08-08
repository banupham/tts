import io
import os
import sys
import time
from contextlib import asynccontextmanager
from threading import Lock
from typing import Optional

import numpy as np
import soundfile as sf
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from vieneu import Vieneu


# Windows terminals can otherwise fall back to cp1252.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


HOST = os.getenv("TTS_HOST", "127.0.0.1")
PORT = int(os.getenv("TTS_PORT", "8765"))
PRECISION = os.getenv("TTS_PRECISION", "int8").strip().lower()
THREADS = int(os.getenv("TTS_THREADS", "0"))
WARMUP = os.getenv("TTS_WARMUP", "1").strip().lower() not in {"0", "false", "no", "off"}

if PRECISION not in {"int8", "fp32"}:
    raise RuntimeError("TTS_PRECISION chỉ hỗ trợ int8 hoặc fp32")


tts: Optional[Vieneu] = None
tts_lock = Lock()


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    voice: Optional[str] = None
    style: str = "doc_truyen"
    temperature: float = Field(default=0.78, ge=0.1, le=1.5)
    top_k: int = Field(default=25, ge=1, le=200)
    top_p: float = Field(default=0.93, gt=0.0, le=1.0)
    max_chars: int = Field(default=200, ge=50, le=1000)
    repetition_penalty: float = Field(default=1.2, ge=0.5, le=3.0)
    apply_watermark: bool = False


def _validate_request(req: TTSRequest) -> str:
    if tts is None:
        raise HTTPException(status_code=503, detail="Model chưa sẵn sàng")

    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text không được rỗng")

    if req.style not in {"tu_nhien", "tin_tuc", "doc_truyen"}:
        raise HTTPException(
            status_code=400,
            detail="style phải là tu_nhien, tin_tuc hoặc doc_truyen",
        )

    # Với streaming, lỗi voice xảy ra sau khi HTTP headers đã gửi sẽ khó báo lại
    # cho client, nên kiểm tra voice trước khi tạo StreamingResponse.
    if req.voice:
        try:
            tts.get_preset_voice(req.voice)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return text


def _warmup_model() -> None:
    if not WARMUP or tts is None:
        return

    print("Đang warm-up TTS...")
    started = time.perf_counter()

    try:
        _ = tts.infer(
            "Xin chào. Hệ thống đã sẵn sàng.",
            voice=None,
            style="tu_nhien",
            temperature=0.75,
            top_k=20,
            top_p=0.90,
            max_chars=120,
            apply_watermark=False,
        )
        print(f"Warm-up xong sau {time.perf_counter() - started:.2f} giây.")
    except Exception as exc:
        # Warm-up không được phép làm server chết; request thật vẫn có thể chạy.
        print(f"Cảnh báo warm-up thất bại: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global tts

    print("=" * 60)
    print("Đang nạp VieNeu-TTS...")
    print("Backend   : onnx")
    print(f"Precision : {PRECISION}")
    print(f"Threads   : {THREADS if THREADS else 'auto'}")
    print("=" * 60)

    started = time.perf_counter()
    tts = Vieneu(
        backend="onnx",
        precision=PRECISION,
        threads=THREADS,
    )
    print(f"Nạp model xong sau {time.perf_counter() - started:.2f} giây.")

    _warmup_model()

    print("=" * 60)
    print(f"TTS SERVER READY: http://{HOST}:{PORT}")
    print(f"Swagger UI      : http://{HOST}:{PORT}/docs")
    print("WAV endpoint    : POST /tts")
    print("Realtime stream : POST /tts/stream")
    print("=" * 60)

    yield

    print("TTS server stopped.")


app = FastAPI(
    title="VieNeu Local TTS",
    version="1.1.0",
    lifespan=lifespan,
)


@app.get("/")
def root():
    return {
        "service": "VieNeu Local TTS",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "voices": "/voices",
        "tts": "POST /tts",
        "tts_stream": "POST /tts/stream",
    }


@app.get("/health")
def health():
    return {
        "status": "ok" if tts is not None else "loading",
        "model_loaded": tts is not None,
        "backend": "onnx",
        "precision": PRECISION,
        "sample_rate": getattr(tts, "sample_rate", None),
        "warmup": WARMUP,
        "streaming": bool(tts is not None and hasattr(tts, "infer_stream")),
    }


@app.get("/voices")
def voices():
    if tts is None:
        raise HTTPException(status_code=503, detail="Model chưa sẵn sàng")

    return [
        {"label": label, "id": voice_id}
        for label, voice_id in tts.list_preset_voices()
    ]


def _clean_audio(audio: np.ndarray) -> np.ndarray:
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    if audio.size == 0:
        return audio

    if not np.isfinite(audio).all():
        audio = np.nan_to_num(audio, nan=0.0, posinf=1.0, neginf=-1.0)

    peak = float(np.max(np.abs(audio)))
    if peak > 1.0:
        audio = audio / peak * 0.98

    return audio


def _wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
    audio = _clean_audio(audio)
    if audio.size == 0:
        raise RuntimeError("Model trả về audio rỗng")

    buffer = io.BytesIO()
    sf.write(buffer, audio, sample_rate, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


def _pcm16_bytes(audio: np.ndarray) -> bytes:
    """Float32 [-1, 1] -> mono signed PCM16 little-endian."""
    audio = _clean_audio(audio)
    if audio.size == 0:
        return b""
    pcm = np.clip(audio, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype("<i2", copy=False)
    return pcm.tobytes()


@app.post("/tts")
def generate_tts(req: TTSRequest):
    text = _validate_request(req)
    assert tts is not None

    started = time.perf_counter()

    print("-" * 60)
    print(f"TEXT : {text[:160]}")
    print(f"VOICE: {req.voice or '(default)'}")
    print(f"STYLE: {req.style}")
    print(
        "SAMPLE: "
        f"temp={req.temperature}, top_k={req.top_k}, "
        f"top_p={req.top_p}, max_chars={req.max_chars}"
    )

    try:
        # ONNX engine/model state được dùng tuần tự để tránh hai request infer
        # cùng lúc gây tranh chấp tài nguyên hoặc khó chẩn đoán artifact.
        with tts_lock:
            audio = tts.infer(
                text,
                voice=req.voice,
                style=req.style,
                temperature=req.temperature,
                top_k=req.top_k,
                top_p=req.top_p,
                max_chars=req.max_chars,
                repetition_penalty=req.repetition_penalty,
                apply_watermark=req.apply_watermark,
            )

        sample_rate = int(tts.sample_rate)
        wav = _wav_bytes(audio, sample_rate)
        elapsed = time.perf_counter() - started

        print(f"OK: {elapsed:.2f} giây, {len(wav) / 1024:.1f} KB")

        return Response(
            content=wav,
            media_type="audio/wav",
            headers={
                "Content-Disposition": 'inline; filename="tts.wav"',
                "X-TTS-Elapsed-Seconds": f"{elapsed:.3f}",
                "X-TTS-Sample-Rate": str(sample_rate),
                "X-TTS-Precision": PRECISION,
            },
        )

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        print(f"TTS ERROR: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/tts/stream")
def generate_tts_stream(req: TTSRequest):
    """Stream mono PCM16 little-endian as soon as VieNeu produces audio frames."""
    text = _validate_request(req)
    assert tts is not None

    sample_rate = int(tts.sample_rate)

    print("-" * 60)
    print(f"STREAM TEXT : {text[:160]}")
    print(f"STREAM VOICE: {req.voice or '(default)'}")
    print(f"STREAM STYLE: {req.style}")

    def pcm_generator():
        started = time.perf_counter()
        first_audio_at: Optional[float] = None
        total_bytes = 0
        chunks = 0

        try:
            # Giữ lock suốt một lượt nói. Request /tts hoặc /tts/stream khác sẽ
            # chờ, giúp một câu không bị trộn audio với câu khác.
            with tts_lock:
                for audio in tts.infer_stream(
                    text,
                    voice=req.voice,
                    style=req.style,
                    temperature=req.temperature,
                    top_k=req.top_k,
                    top_p=req.top_p,
                    max_chars=req.max_chars,
                    repetition_penalty=req.repetition_penalty,
                    apply_watermark=req.apply_watermark,
                ):
                    pcm = _pcm16_bytes(audio)
                    if not pcm:
                        continue

                    if first_audio_at is None:
                        first_audio_at = time.perf_counter()
                        ttfa = first_audio_at - started
                        print(f"STREAM FIRST AUDIO: {ttfa:.3f} giây")

                    chunks += 1
                    total_bytes += len(pcm)
                    yield pcm

            elapsed = time.perf_counter() - started
            duration = total_bytes / 2 / sample_rate
            print(
                f"STREAM OK: {elapsed:.2f} giây | chunks={chunks} | "
                f"audio={duration:.2f} giây"
            )

        except GeneratorExit:
            print("STREAM: client đã ngắt kết nối.")
            return
        except Exception as exc:
            # Headers có thể đã gửi, nên lỗi giữa stream được ghi log và kết thúc stream.
            print(f"STREAM ERROR: {exc}")
            return

    return StreamingResponse(
        pcm_generator(),
        media_type=f"audio/pcm; rate={sample_rate}; channels=1",
        headers={
            "Cache-Control": "no-store",
            "X-TTS-Sample-Rate": str(sample_rate),
            "X-TTS-Channels": "1",
            "X-TTS-Format": "s16le",
            "X-TTS-Precision": PRECISION,
        },
    )


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info",
    )
