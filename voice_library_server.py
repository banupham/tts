import mimetypes
import os
import socket
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import soundfile as sf
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


BASE_DIR = Path(__file__).resolve().parent
HOST = os.getenv("VOICE_LIBRARY_HOST", "0.0.0.0")
PORT = int(os.getenv("VOICE_LIBRARY_PORT", "8766"))
MAX_FILES = int(os.getenv("VOICE_LIBRARY_MAX_FILES", "5000"))
AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"}
IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".cache",
    ".cache_huggingface",
    "models",
    "node_modules",
}


def _configured_roots() -> list[Path]:
    raw = os.getenv("VOICE_LIBRARY_ROOTS", "").strip()
    if raw:
        items = [item.strip() for item in raw.split(";") if item.strip()]
    else:
        items = [str(BASE_DIR / "outputs")]

    roots: list[Path] = []
    seen: set[str] = set()

    for item in items:
        path = Path(os.path.expandvars(os.path.expanduser(item)))
        if not path.is_absolute():
            path = BASE_DIR / path
        path = path.resolve()
        key = os.path.normcase(str(path))
        if key not in seen:
            roots.append(path)
            seen.add(key)

    return roots


ROOTS = _configured_roots()
for root in ROOTS:
    root.mkdir(parents=True, exist_ok=True)


app = FastAPI(title="VieNeu Voice Library", version="1.0.0")


def _lan_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"
    finally:
        sock.close()


def _duration_seconds(path: Path) -> float | None:
    try:
        info = sf.info(str(path))
        if info.samplerate and info.frames:
            return round(info.frames / info.samplerate, 2)
    except Exception:
        pass
    return None


def _scan_audio_files() -> list[dict]:
    files: list[dict] = []

    for root_index, root in enumerate(ROOTS):
        if not root.exists():
            continue

        for current_dir, dirs, names in os.walk(root):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
            current = Path(current_dir)

            for name in names:
                path = current / name
                if path.suffix.lower() not in AUDIO_EXTENSIONS:
                    continue

                try:
                    stat = path.stat()
                    relative = path.relative_to(root).as_posix()
                except (OSError, ValueError):
                    continue

                encoded_path = "/".join(quote(part, safe="") for part in relative.split("/"))
                files.append(
                    {
                        "root_id": root_index,
                        "root": str(root),
                        "name": path.name,
                        "relative_path": relative,
                        "extension": path.suffix.lower(),
                        "size_bytes": stat.st_size,
                        "modified_ts": stat.st_mtime,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                        "duration_seconds": _duration_seconds(path),
                        "url": f"/audio/{root_index}/{encoded_path}",
                        "download_url": f"/audio/{root_index}/{encoded_path}?download=1",
                    }
                )

                if len(files) >= MAX_FILES:
                    break

            if len(files) >= MAX_FILES:
                break
        if len(files) >= MAX_FILES:
            break

    files.sort(key=lambda item: item["modified_ts"], reverse=True)
    return files


def _safe_audio_path(root_id: int, relative_path: str) -> Path:
    if root_id < 0 or root_id >= len(ROOTS):
        raise HTTPException(status_code=404, detail="Root không tồn tại")

    root = ROOTS[root_id].resolve()
    candidate = (root / relative_path).resolve()

    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Đường dẫn không hợp lệ") from exc

    if not candidate.is_file() or candidate.suffix.lower() not in AUDIO_EXTENSIONS:
        raise HTTPException(status_code=404, detail="Không tìm thấy audio")

    return candidate


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "host": HOST,
        "port": PORT,
        "lan_ip": _lan_ip(),
        "roots": [str(root) for root in ROOTS],
        "max_files": MAX_FILES,
    }


@app.get("/api/files")
def files():
    items = _scan_audio_files()
    total_bytes = sum(item["size_bytes"] for item in items)
    return JSONResponse(
        {
            "count": len(items),
            "total_bytes": total_bytes,
            "roots": [str(root) for root in ROOTS],
            "files": items,
        },
        headers={"Cache-Control": "no-store"},
    )


@app.get("/audio/{root_id}/{relative_path:path}")
def audio_file(root_id: int, relative_path: str, download: bool = Query(default=False)):
    path = _safe_audio_path(root_id, relative_path)
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    disposition = "attachment" if download else "inline"
    return FileResponse(
        str(path),
        media_type=media_type,
        filename=path.name if download else None,
        content_disposition_type=disposition,
    )


HTML = r'''<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VieNeu Voice Library</title>
<style>
:root { color-scheme: dark; font-family: Inter, system-ui, -apple-system, Segoe UI, sans-serif; }
* { box-sizing: border-box; }
body { margin: 0; background: #0c0e12; color: #eef1f6; }
header { position: sticky; top: 0; z-index: 3; padding: 18px; background: rgba(12,14,18,.95); border-bottom: 1px solid #252a33; backdrop-filter: blur(10px); }
.wrap { width: min(1100px, calc(100% - 28px)); margin: 0 auto; }
h1 { margin: 0 0 5px; font-size: 24px; }
.sub { color: #9aa4b2; font-size: 13px; }
.controls { display: grid; grid-template-columns: 1fr auto auto auto; gap: 8px; margin-top: 14px; }
input, select, button { border: 1px solid #303744; background: #151922; color: #eef1f6; border-radius: 10px; padding: 10px 12px; font: inherit; }
button { cursor: pointer; }
button:hover { background: #202633; }
main { padding: 18px 0 50px; }
.stats { display: flex; gap: 16px; flex-wrap: wrap; color: #9aa4b2; font-size: 13px; margin-bottom: 14px; }
.list { display: grid; gap: 10px; }
.card { border: 1px solid #252a33; background: #12161d; border-radius: 14px; padding: 13px; }
.card.playing { border-color: #7d8ba8; background: #171c25; }
.row { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.name { font-weight: 700; overflow-wrap: anywhere; }
.path { color: #7f8998; font-size: 12px; overflow-wrap: anywhere; margin-top: 4px; }
.meta { color: #9aa4b2; font-size: 12px; white-space: nowrap; }
audio { width: 100%; margin-top: 11px; height: 38px; }
.actions { margin-top: 8px; display: flex; gap: 8px; }
a { color: #bdc8dc; text-decoration: none; font-size: 13px; }
.empty { text-align: center; color: #8e98a7; padding: 50px 10px; }
@media (max-width: 720px) { .controls { grid-template-columns: 1fr 1fr; } .controls input { grid-column: 1 / -1; } .row { display: block; } .meta { margin-top: 7px; } }
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>Voice Library</h1>
    <div class="sub">Nghe lại audio được tạo trên PC qua mạng LAN</div>
    <div class="controls">
      <input id="search" placeholder="Tìm tên file hoặc thư mục..." autocomplete="off">
      <select id="sort">
        <option value="newest">Mới nhất</option>
        <option value="oldest">Cũ nhất</option>
        <option value="name">Tên A-Z</option>
      </select>
      <button id="playAll">▶ Phát tất cả</button>
      <button id="refresh">↻ Refresh</button>
    </div>
  </div>
</header>
<main class="wrap">
  <div class="stats" id="stats"><span>Đang tải...</span></div>
  <div class="list" id="list"></div>
</main>
<script>
const listEl = document.getElementById('list');
const statsEl = document.getElementById('stats');
const searchEl = document.getElementById('search');
const sortEl = document.getElementById('sort');
let files = [];
let playQueue = [];
let queueIndex = -1;

function fmtBytes(n) {
  if (n < 1024) return n + ' B';
  if (n < 1024*1024) return (n/1024).toFixed(1) + ' KB';
  if (n < 1024*1024*1024) return (n/1024/1024).toFixed(1) + ' MB';
  return (n/1024/1024/1024).toFixed(2) + ' GB';
}
function fmtDuration(s) {
  if (s == null) return 'không rõ thời lượng';
  const m = Math.floor(s/60), sec = Math.round(s%60);
  return `${m}:${String(sec).padStart(2,'0')}`;
}
function filtered() {
  const q = searchEl.value.trim().toLowerCase();
  let arr = files.filter(f => !q || f.name.toLowerCase().includes(q) || f.relative_path.toLowerCase().includes(q));
  if (sortEl.value === 'oldest') arr.sort((a,b) => a.modified_ts - b.modified_ts);
  else if (sortEl.value === 'name') arr.sort((a,b) => a.name.localeCompare(b.name, 'vi'));
  else arr.sort((a,b) => b.modified_ts - a.modified_ts);
  return arr;
}
function stopOthers(current) {
  document.querySelectorAll('audio').forEach(a => { if (a !== current && !a.paused) a.pause(); });
  document.querySelectorAll('.card').forEach(c => c.classList.remove('playing'));
  current.closest('.card')?.classList.add('playing');
}
function render() {
  const arr = filtered();
  listEl.innerHTML = '';
  statsEl.innerHTML = `<span>${arr.length} / ${files.length} file</span>`;
  if (!arr.length) {
    listEl.innerHTML = '<div class="empty">Không có audio phù hợp.</div>';
    return;
  }
  for (const f of arr) {
    const card = document.createElement('div');
    card.className = 'card';
    const row = document.createElement('div'); row.className = 'row';
    const left = document.createElement('div');
    const name = document.createElement('div'); name.className = 'name'; name.textContent = f.name;
    const path = document.createElement('div'); path.className = 'path'; path.textContent = f.relative_path;
    left.append(name, path);
    const meta = document.createElement('div'); meta.className = 'meta';
    meta.textContent = `${fmtDuration(f.duration_seconds)} · ${fmtBytes(f.size_bytes)} · ${new Date(f.modified_ts*1000).toLocaleString('vi-VN')}`;
    row.append(left, meta);
    const audio = document.createElement('audio');
    audio.controls = true; audio.preload = 'none'; audio.src = f.url; audio.dataset.url = f.url;
    audio.addEventListener('play', () => stopOthers(audio));
    audio.addEventListener('ended', () => playNext(audio.dataset.url));
    const actions = document.createElement('div'); actions.className = 'actions';
    const dl = document.createElement('a'); dl.href = f.download_url; dl.textContent = 'Tải file';
    actions.append(dl);
    card.append(row, audio, actions);
    listEl.append(card);
  }
}
function playNext(endedUrl=null) {
  if (!playQueue.length) return;
  if (endedUrl) {
    const idx = playQueue.findIndex(f => f.url === endedUrl);
    if (idx >= 0) queueIndex = idx + 1;
  }
  if (queueIndex < 0) queueIndex = 0;
  if (queueIndex >= playQueue.length) { queueIndex = -1; return; }
  const target = [...document.querySelectorAll('audio')].find(a => a.dataset.url === playQueue[queueIndex].url);
  if (target) target.play().catch(() => {});
}
async function load() {
  statsEl.innerHTML = '<span>Đang quét audio...</span>';
  const res = await fetch('/api/files', {cache:'no-store'});
  const data = await res.json();
  files = data.files || [];
  statsEl.innerHTML = `<span>${data.count} file</span><span>${fmtBytes(data.total_bytes || 0)}</span><span>${(data.roots || []).join(' · ')}</span>`;
  render();
}
searchEl.addEventListener('input', render);
sortEl.addEventListener('change', render);
document.getElementById('refresh').addEventListener('click', load);
document.getElementById('playAll').addEventListener('click', () => { playQueue = filtered(); queueIndex = 0; playNext(); });
load().catch(err => { statsEl.textContent = 'Lỗi tải thư viện: ' + err; });
</script>
</body>
</html>'''


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(HTML, headers={"Cache-Control": "no-store"})


if __name__ == "__main__":
    lan_ip = _lan_ip()
    print("=" * 64)
    print("VIE-NEU VOICE LIBRARY SERVER")
    print(f"Local : http://127.0.0.1:{PORT}")
    print(f"LAN   : http://{lan_ip}:{PORT}")
    print("Roots :")
    for root in ROOTS:
        print(f"  - {root}")
    print("=" * 64)
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
