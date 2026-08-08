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
from fastapi.responses import Response
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


def _warmup_model() -> None:
    if not WARMUP or tts is None:
        return

    print("Đang warm-up TTS...")
    started = time.perf_counter()

    try:
        # Dùng default preset voice để không phụ thuộc tên voice cụ thể.
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
    print(f"Backend   : onnx")
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
    print("=" * 60)

    yield

    print("TTS server stopped.")


app = FastAPI(
    title="VieNeu Local TTS",
    version="1.0.0",
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
    }


@app.get("/voices")
def voices():
    if tts is None:
        raise HTTPException(status_code=503, detail="Model chưa sẵn sàng")

    return [
        {"label": label, "id": voice_id}
        for label, voice_id in tts.list_preset_voices()
    ]


def _wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)

    if audio.size == 0:
        raise RuntimeError("Model trả về audio rỗng")

    if not np.isfinite(audio).all():
        audio = np.nan_to_num(audio, nan=0.0, posinf=1.0, neginf=-1.0)

    # Tránh clipping khi đổi sang PCM16. Không normalize từng đoạn lên 100%,
    # vì làm vậy sẽ khiến âm lượng giữa các đoạn truyện thay đổi bất thường.
    peak = float(np.max(np.abs(audio)))
    if peak > 1.0:
        audio = audio / peak * 0.98

    buffer = io.BytesIO()
    sf.write(buffer, audio, sample_rate, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


@app.post("/tts")
def generate_tts(req: TTSRequest):
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


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info",
    )
