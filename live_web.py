import os
import sys

import requests
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import Optional

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HOST = os.getenv("LIVE_WEB_HOST", "0.0.0.0")
PORT = int(os.getenv("LIVE_WEB_PORT", "8771"))
TTS_SERVER = os.getenv("LIVE_WEB_TTS_SERVER", "http://127.0.0.1:8765").rstrip("/")
LIVE_QUEUE = os.getenv("LIVE_WEB_QUEUE", "http://127.0.0.1:8770").rstrip("/")

app = FastAPI(title="VieNeu Live TTS Web", version="1.0.0")


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


def _json_or_error(response: requests.Response):
    try:
        data = response.json()
    except Exception:
        data = {"detail": response.text or f"HTTP {response.status_code}"}
    if not response.ok:
        raise HTTPException(status_code=response.status_code, detail=data)
    return data


@app.get("/api/voices")
def voices():
    try:
        response = requests.get(TTS_SERVER + "/voices", timeout=10)
        return _json_or_error(response)
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail=f"Không kết nối được TTS server: {exc}") from exc


@app.get("/api/health")
def health():
    try:
        response = requests.get(LIVE_QUEUE + "/health", timeout=5)
        return _json_or_error(response)
    except requests.RequestException as exc:
        return {"status": "offline", "detail": str(exc), "queue_size": None, "speaking": False}


@app.post("/api/speak")
def speak(req: SpeakRequest):
    try:
        response = requests.post(LIVE_QUEUE + "/speak", json=req.model_dump(), timeout=10)
        return _json_or_error(response)
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail=f"Không kết nối được Live TTS Queue: {exc}") from exc


@app.post("/api/clear")
def clear():
    try:
        response = requests.post(LIVE_QUEUE + "/clear", timeout=10)
        return _json_or_error(response)
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail=f"Không kết nối được Live TTS Queue: {exc}") from exc


HTML = r'''<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VieNeu Live TTS</title>
<style>
:root { color-scheme: dark; font-family: Inter,system-ui,-apple-system,Segoe UI,sans-serif; }
* { box-sizing: border-box; }
body { margin:0; background:#0c0e12; color:#eef1f6; }
.wrap { width:min(900px,calc(100% - 28px)); margin:0 auto; padding:24px 0 50px; }
h1 { margin:0 0 6px; font-size:26px; }
.sub { color:#98a3b3; margin-bottom:18px; }
.panel { background:#12161d; border:1px solid #252a33; border-radius:16px; padding:16px; }
.grid { display:grid; grid-template-columns:2fr 1fr 1fr; gap:10px; }
label { display:block; color:#aab4c3; font-size:12px; margin-bottom:6px; }
select,input,textarea,button { width:100%; border:1px solid #303744; background:#151922; color:#eef1f6; border-radius:10px; padding:10px 12px; font:inherit; }
textarea { min-height:150px; resize:vertical; margin-top:10px; }
.buttons { display:grid; grid-template-columns:2fr 1fr; gap:10px; margin-top:10px; }
button { cursor:pointer; font-weight:700; }
button:hover { background:#202633; }
.primary { background:#243047; }
.status { margin-top:14px; padding:11px 12px; background:#0f1319; border:1px solid #252a33; border-radius:10px; color:#aeb8c7; font-size:13px; }
.advanced { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-top:12px; }
.note { margin-top:12px; color:#7f8998; font-size:12px; line-height:1.5; }
@media(max-width:700px){ .grid,.advanced,.buttons { grid-template-columns:1fr; } }
</style>
</head>
<body>
<div class="wrap">
  <h1>Live TTS Control</h1>
  <div class="sub">Chọn giọng, nhập nội dung và phát realtime qua loa của PC.</div>
  <div class="panel">
    <div class="grid">
      <div><label>Giọng nói</label><select id="voice"><option value="">Đang tải giọng...</option></select></div>
      <div><label>Phong cách</label><select id="style"><option value="tu_nhien">Tự nhiên</option><option value="doc_truyen">Đọc truyện</option><option value="tin_tuc">Tin tức</option></select></div>
      <div><label>Ưu tiên</label><input id="priority" type="number" min="0" max="1000" value="50"></div>
    </div>

    <textarea id="text" placeholder="Nhập câu muốn đọc realtime..."></textarea>

    <div class="advanced">
      <div><label>Temperature</label><input id="temperature" type="number" step="0.01" value="0.78"></div>
      <div><label>Top K</label><input id="topK" type="number" value="25"></div>
      <div><label>Top P</label><input id="topP" type="number" step="0.01" value="0.93"></div>
      <div><label>Max chars</label><input id="maxChars" type="number" value="180"></div>
    </div>

    <div class="buttons">
      <button class="primary" id="speak">▶ ĐỌC NGAY</button>
      <button id="clear">Xóa hàng đợi</button>
    </div>

    <div class="status" id="status">Đang kiểm tra Live TTS Queue...</div>
    <div class="note">Priority số nhỏ hơn được đọc trước. Câu đang phát không bị cắt. Trang web có thể mở từ điện thoại trong LAN nhưng âm thanh vẫn phát trên loa PC chạy Live TTS Queue.</div>
  </div>
</div>
<script>
const $ = id => document.getElementById(id);

async function loadVoices(){
  try {
    const r = await fetch('/api/voices',{cache:'no-store'});
    const data = await r.json();
    if(!r.ok) throw new Error(JSON.stringify(data));
    $('voice').innerHTML = '<option value="">Mặc định</option>';
    for(const v of data){
      const o=document.createElement('option'); o.value=v.id; o.textContent=v.label || v.id; $('voice').appendChild(o);
    }
  } catch(e){ $('voice').innerHTML='<option value="">Không tải được voice</option>'; }
}

async function refreshStatus(){
  try {
    const r=await fetch('/api/health',{cache:'no-store'}); const d=await r.json();
    if(d.status === 'offline') { $('status').textContent='Queue OFFLINE: '+(d.detail||'không kết nối được'); return; }
    const now=d.speaking ? `Đang đọc: ${d.current_text || ''}` : 'Đang rảnh';
    $('status').textContent=`${now} · Queue: ${d.queue_size ?? '?'} · Đã đọc: ${d.played ?? 0}${d.last_error ? ' · Lỗi: '+d.last_error : ''}`;
  } catch(e){ $('status').textContent='Không đọc được trạng thái queue.'; }
}

$('speak').addEventListener('click', async()=>{
  const text=$('text').value.trim();
  if(!text){ $('status').textContent='Hãy nhập nội dung cần đọc.'; return; }
  const payload={
    text,
    voice:$('voice').value || null,
    style:$('style').value,
    priority:Number($('priority').value || 50),
    temperature:Number($('temperature').value || 0.78),
    top_k:Number($('topK').value || 25),
    top_p:Number($('topP').value || 0.93),
    max_chars:Number($('maxChars').value || 180),
    repetition_penalty:1.2,
    apply_watermark:false
  };
  $('status').textContent='Đang gửi vào hàng đợi...';
  try {
    const r=await fetch('/api/speak',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const d=await r.json();
    if(!r.ok) throw new Error(JSON.stringify(d));
    $('status').textContent=`Đã xếp hàng #${d.id} · vị trí queue hiện tại: ${d.queue_size}`;
    setTimeout(refreshStatus,500);
  } catch(e){ $('status').textContent='Lỗi gửi: '+e; }
});

$('clear').addEventListener('click', async()=>{
  try { const r=await fetch('/api/clear',{method:'POST'}); const d=await r.json(); $('status').textContent=`Đã xóa ${d.cleared ?? 0} câu đang chờ.`; }
  catch(e){ $('status').textContent='Lỗi xóa queue: '+e; }
});

loadVoices(); refreshStatus(); setInterval(refreshStatus,2000);
</script>
</body>
</html>'''


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(HTML, headers={"Cache-Control": "no-store"})


if __name__ == "__main__":
    print("=" * 64)
    print("VIE-NEU LIVE TTS WEB")
    print(f"Web        : http://127.0.0.1:{PORT}")
    print(f"TTS server : {TTS_SERVER}")
    print(f"Live queue : {LIVE_QUEUE}")
    print("=" * 64)
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
