import itertools
import os
import sys
import threading
import time
import uuid
from contextlib import asynccontextmanager
from queue import Empty, PriorityQueue
from typing import Optional

import requests
import sounddevice as sd
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


HOST = os.getenv("LIVE_TTS_HOST", "127.0.0.1")
PORT = int(os.getenv("LIVE_TTS_PORT", "8770"))
TTS_SERVER = os.getenv("LIVE_TTS_SERVER", "http://127.0.0.1:8765").rstrip("/")
HTTP_CHUNK_BYTES = int(os.getenv("LIVE_TTS_HTTP_CHUNK_BYTES", "4096"))


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    voice: Optional[str] = None
    style: str = "tu_nhien"
    priority: int = Field(default=50, ge=0, le=1000)
    temperature: float = Field(default=0.78, ge=0.1, le=1.5)
    top_k: int = Field(default=25, ge=1, le=200)
    top_p: float = Field(default=0.93, gt=0.0, le=1.0)
    max_chars: int = Field(default=180, ge=50, le=1000)
    repetition_penalty: float = Field(default=1.2, ge=0.5, le=3.0)
    apply_watermark: bool = False


speech_queue: PriorityQueue = PriorityQueue()
sequence = itertools.count()
stop_event = threading.Event()
worker_thread: Optional[threading.Thread] = None
state_lock = threading.Lock()
state = {
    "speaking": False,
    "current_id": None,
    "current_text": None,
    "last_error": None,
    "played": 0,
}


def _set_state(**kwargs) -> None:
    with state_lock:
        state.update(kwargs)


def _snapshot_state() -> dict:
    with state_lock:
        return dict(state)


def _play_stream(item: dict) -> None:
    req = item["request"]
    text = req["text"].strip()
    payload = {
        "text": text,
        "voice": req.get("voice"),
        "style": req.get("style", "tu_nhien"),
        "temperature": req.get("temperature", 0.78),
        "top_k": req.get("top_k", 25),
        "top_p": req.get("top_p", 0.93),
        "max_chars": req.get("max_chars", 180),
        "repetition_penalty": req.get("repetition_penalty", 1.2),
        "apply_watermark": req.get("apply_watermark", False),
    }

    print("-" * 64)
    print(f"LIVE #{item['id']} priority={item['priority']}")
    print(f"TEXT : {text[:180]}")
    print(f"VOICE: {payload['voice'] or '(default)'}")

    started = time.perf_counter()
    first_audio = None

    with requests.post(
        TTS_SERVER + "/tts/stream",
        json=payload,
        stream=True,
        timeout=(10, 300),
    ) as response:
        response.raise_for_status()

        sample_rate = int(response.headers.get("X-TTS-Sample-Rate", "48000"))
        fmt = response.headers.get("X-TTS-Format", "s16le")
        channels = int(response.headers.get("X-TTS-Channels", "1"))

        if fmt.lower() != "s16le":
            raise RuntimeError(f"Format stream không hỗ trợ: {fmt}")
        if channels != 1:
            raise RuntimeError(f"Chỉ hỗ trợ mono, server trả channels={channels}")

        carry = b""
        total_bytes = 0

        with sd.RawOutputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
            blocksize=0,
            latency="low",
        ) as audio_out:
            for chunk in response.iter_content(chunk_size=max(512, HTTP_CHUNK_BYTES)):
                if not chunk:
                    continue

                if first_audio is None:
                    first_audio = time.perf_counter()
                    print(f"FIRST AUDIO: {first_audio - started:.3f} giây")

                data = carry + chunk
                even_len = len(data) - (len(data) % 2)
                if even_len:
                    audio_out.write(data[:even_len])
                    total_bytes += even_len
                carry = data[even_len:]

            # Một sample int16 luôn cần 2 byte. Nếu HTTP stream kết thúc với 1 byte
            # lẻ thì bỏ byte đó thay vì phát sample hỏng.
            if carry:
                print("Cảnh báo: stream kết thúc với 1 byte PCM lẻ, đã bỏ qua.")

    elapsed = time.perf_counter() - started
    duration = total_bytes / 2 / sample_rate
    print(f"PLAYED: audio={duration:.2f}s total={elapsed:.2f}s")


def _worker() -> None:
    session_errors = 0
    while not stop_event.is_set():
        try:
            priority, seq, item = speech_queue.get(timeout=0.5)
        except Empty:
            continue

        if item is None:
            speech_queue.task_done()
            break

        _set_state(
            speaking=True,
            current_id=item["id"],
            current_text=item["request"]["text"],
            last_error=None,
        )

        try:
            _play_stream(item)
            snap = _snapshot_state()
            _set_state(played=int(snap.get("played", 0)) + 1)
            session_errors = 0
        except Exception as exc:
            session_errors += 1
            _set_state(last_error=str(exc))
            print(f"LIVE TTS ERROR #{item['id']}: {exc}")
            if session_errors >= 3:
                print("Gợi ý: kiểm tra TTS server 8765 và thiết bị loa mặc định của Windows.")
        finally:
            _set_state(speaking=False, current_id=None, current_text=None)
            speech_queue.task_done()


def _start_worker() -> None:
    global worker_thread
    stop_event.clear()
    worker_thread = threading.Thread(target=_worker, name="live-tts-worker", daemon=True)
    worker_thread.start()


def _stop_worker() -> None:
    stop_event.set()
    speech_queue.put((-1, next(sequence), None))
    if worker_thread is not None:
        worker_thread.join(timeout=3)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _start_worker()
    print("=" * 64)
    print("VIE-NEU LIVE TTS QUEUE READY")
    print(f"Queue API : http://{HOST}:{PORT}")
    print(f"TTS source: {TTS_SERVER}/tts/stream")
    print("Priority  : số nhỏ hơn được đọc trước; không cắt câu đang phát")
    print("=" * 64)
    yield
    _stop_worker()


app = FastAPI(
    title="VieNeu Live TTS Queue",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
def root():
    return {
        "service": "VieNeu Live TTS Queue",
        "status": "running",
        "speak": "POST /speak",
        "clear": "POST /clear",
        "health": "/health",
        "tts_server": TTS_SERVER,
    }


@app.get("/health")
def health():
    snap = _snapshot_state()
    return {
        "status": "ok",
        "queue_size": speech_queue.qsize(),
        "tts_server": TTS_SERVER,
        **snap,
    }


@app.post("/speak")
def speak(req: SpeakRequest):
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text không được rỗng")

    if req.style not in {"tu_nhien", "tin_tuc", "doc_truyen"}:
        raise HTTPException(
            status_code=400,
            detail="style phải là tu_nhien, tin_tuc hoặc doc_truyen",
        )

    item_id = uuid.uuid4().hex[:8]
    item = {
        "id": item_id,
        "priority": req.priority,
        "request": req.model_dump(),
        "queued_at": time.time(),
    }
    speech_queue.put((req.priority, next(sequence), item))

    return {
        "queued": True,
        "id": item_id,
        "priority": req.priority,
        "queue_size": speech_queue.qsize(),
        "note": "Câu đang phát không bị cắt; priority chỉ sắp xếp các câu đang chờ.",
    }


@app.post("/clear")
def clear_queue():
    removed = 0
    while True:
        try:
            _priority, _seq, item = speech_queue.get_nowait()
        except Empty:
            break
        else:
            speech_queue.task_done()
            if item is not None:
                removed += 1

    return {
        "cleared": removed,
        "speaking_continues": _snapshot_state()["speaking"],
    }


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
