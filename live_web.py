import os
import sys
from typing import Optional

import requests
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HOST = os.getenv("LIVE_WEB_HOST", "0.0.0.0")
PORT = int(os.getenv("LIVE_WEB_PORT", "8771"))
TTS_SERVER = os.getenv("LIVE_WEB_TTS_SERVER", "http://127.0.0.1:8765").rstrip("/")
LIVE_QUEUE = os.getenv("LIVE_WEB_QUEUE", "http://127.0.0.1:8770").rstrip("/")

app = FastAPI(title="VieNeu Live TTS Web", version="1.1.0")


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


@app.post("/api/stream")
def stream_to_browser(req: SpeakRequest):
    payload = req.model_dump()
    payload.pop("priority", None)

    try:
        upstream = requests.post(
            TTS_SERVER + "/tts/stream",
            json=payload,
            stream=True,
            timeout=(10, 300),
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=503, detail=f"Không kết nối được TTS stream: {exc}") from exc

    if not upstream.ok:
        try:
            detail = upstream.json()
        except Exception:
            detail = upstream.text or f"HTTP {upstream.status_code}"
        status_code = upstream.status_code
        upstream.close()
        raise HTTPException(status_code=status_code, detail=detail)

    sample_rate = upstream.headers.get("X-TTS-Sample-Rate", "48000")
    channels = upstream.headers.get("X-TTS-Channels", "1")
    audio_format = upstream.headers.get("X-TTS-Format", "s16le")

    def body():
        try:
            for chunk in upstream.iter_content(chunk_size=4096):
                if chunk:
                    yield chunk
        finally:
            upstream.close()

    return StreamingResponse(
        body(),
        media_type=f"audio/pcm; rate={sample_rate}; channels={channels}",
        headers={
            "Cache-Control": "no-store",
            "X-TTS-Sample-Rate": sample_rate,
            "X-TTS-Channels": channels,
            "X-TTS-Format": audio_format,
        },
    )


HTML = r'''<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VieNeu Live TTS</title>
<style>
:root{color-scheme:dark;font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif}*{box-sizing:border-box}body{margin:0;background:#0c0e12;color:#eef1f6}.wrap{width:min(920px,calc(100% - 28px));margin:0 auto;padding:24px 0 50px}h1{margin:0 0 6px;font-size:26px}.sub{color:#98a3b3;margin-bottom:18px}.panel{background:#12161d;border:1px solid #252a33;border-radius:16px;padding:16px}.grid{display:grid;grid-template-columns:2fr 1.4fr 1fr 1fr;gap:10px}label{display:block;color:#aab4c3;font-size:12px;margin-bottom:6px}select,input,textarea,button{width:100%;border:1px solid #303744;background:#151922;color:#eef1f6;border-radius:10px;padding:10px 12px;font:inherit}textarea{min-height:150px;resize:vertical;margin-top:10px}.buttons{display:grid;grid-template-columns:2fr 1fr 1fr;gap:10px;margin-top:10px}button{cursor:pointer;font-weight:700}button:hover{background:#202633}.primary{background:#243047}.stop{background:#2a1c20}.status{margin-top:14px;padding:11px 12px;background:#0f1319;border:1px solid #252a33;border-radius:10px;color:#aeb8c7;font-size:13px;min-height:42px}.advanced{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-top:12px}.note{margin-top:12px;color:#7f8998;font-size:12px;line-height:1.5}@media(max-width:760px){.grid,.advanced,.buttons{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">
<h1>Live TTS Control</h1>
<div class="sub">Có thể phát trên loa PC hoặc phát trực tiếp trên điện thoại/laptop đang mở trang web.</div>
<div class="panel">
<div class="grid">
<div><label>Nơi phát âm thanh</label><select id="outputMode"><option value="web" selected>Thiết bị đang mở web</option><option value="pc">Loa PC (Live Queue)</option></select></div>
<div><label>Giọng nói</label><select id="voice"><option value="">Đang tải giọng...</option></select></div>
<div><label>Phong cách</label><select id="style"><option value="tu_nhien">Tự nhiên</option><option value="doc_truyen">Đọc truyện</option><option value="tin_tuc">Tin tức</option></select></div>
<div><label>Ưu tiên (chỉ loa PC)</label><input id="priority" type="number" min="0" max="1000" value="50"></div>
</div>
<textarea id="text" placeholder="Nhập câu muốn đọc realtime..."></textarea>
<div class="advanced">
<div><label>Temperature</label><input id="temperature" type="number" step="0.01" value="0.78"></div>
<div><label>Top K</label><input id="topK" type="number" value="25"></div>
<div><label>Top P</label><input id="topP" type="number" step="0.01" value="0.93"></div>
<div><label>Max chars</label><input id="maxChars" type="number" value="180"></div>
<div><label>Âm lượng web</label><input id="volume" type="range" min="0" max="150" value="100"></div>
</div>
<div class="buttons"><button class="primary" id="speak">▶ ĐỌC NGAY</button><button class="stop" id="stopWeb">■ Dừng web</button><button id="clear">Xóa queue PC</button></div>
<div class="status" id="status">Sẵn sàng phát trên thiết bị đang mở web.</div>
<div class="note">Nếu mở trang này bằng điện thoại, chế độ “Thiết bị đang mở web” sẽ phát âm thanh trên loa/tai nghe của điện thoại. Chế độ “Loa PC” vẫn dùng queue 8770 và priority như trước.</div>
</div></div>
<script>
const $=id=>document.getElementById(id);let audioCtx=null,gainNode=null,activeSources=[],activeAbort=null,playSession=0,webPlaying=false;
async function loadVoices(){try{const r=await fetch('/api/voices',{cache:'no-store'}),d=await r.json();if(!r.ok)throw new Error(JSON.stringify(d));$('voice').innerHTML='<option value="">Mặc định</option>';for(const v of d){const o=document.createElement('option');o.value=v.id;o.textContent=v.label||v.id;$('voice').appendChild(o)}}catch(e){$('voice').innerHTML='<option value="">Không tải được voice</option>'}}
function payload(){return{text:$('text').value.trim(),voice:$('voice').value||null,style:$('style').value,priority:Number($('priority').value||50),temperature:Number($('temperature').value||.78),top_k:Number($('topK').value||25),top_p:Number($('topP').value||.93),max_chars:Number($('maxChars').value||180),repetition_penalty:1.2,apply_watermark:false}}
async function ensureAudio(){if(!audioCtx){const C=window.AudioContext||window.webkitAudioContext;if(!C)throw new Error('Trình duyệt không hỗ trợ Web Audio API');audioCtx=new C();gainNode=audioCtx.createGain();gainNode.connect(audioCtx.destination)}gainNode.gain.value=Number($('volume').value||100)/100;if(audioCtx.state==='suspended')await audioCtx.resume()}
function stopWeb(show=true){playSession++;webPlaying=false;if(activeAbort){activeAbort.abort();activeAbort=null}for(const s of activeSources){try{s.stop()}catch(e){}}activeSources=[];if(show)$('status').textContent='Đã dừng phát trên web.'}
function merge(a,b){if(!a||!a.length)return b;const o=new Uint8Array(a.length+b.length);o.set(a);o.set(b,a.length);return o}
async function playWeb(p){stopWeb(false);const session=playSession;await ensureAudio();activeAbort=new AbortController();webPlaying=true;$('status').textContent='Đang chờ audio đầu tiên...';const r=await fetch('/api/stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p),signal:activeAbort.signal});if(!r.ok)throw new Error(await r.text()||`HTTP ${r.status}`);if(!r.body)throw new Error('Trình duyệt không hỗ trợ streaming response');const sr=Number(r.headers.get('X-TTS-Sample-Rate')||48000),fmt=(r.headers.get('X-TTS-Format')||'s16le').toLowerCase();if(fmt!=='s16le')throw new Error('Format stream không hỗ trợ: '+fmt);const reader=r.body.getReader();let carry=new Uint8Array(0),next=audioCtx.currentTime+.16,first=true;while(true){const {done,value}=await reader.read();if(done)break;if(session!==playSession)return;if(!value||!value.length)continue;const data=merge(carry,value),n=data.length-data.length%2;carry=data.slice(n);if(!n)continue;const count=n/2,f=new Float32Array(count),v=new DataView(data.buffer,data.byteOffset,n);for(let i=0;i<count;i++)f[i]=v.getInt16(i*2,true)/32768;const b=audioCtx.createBuffer(1,count,sr);b.copyToChannel(f,0);const s=audioCtx.createBufferSource();s.buffer=b;s.connect(gainNode);if(next<audioCtx.currentTime+.06)next=audioCtx.currentTime+.10;s.start(next);next+=b.duration;activeSources.push(s);s.onended=()=>activeSources=activeSources.filter(x=>x!==s);if(first){first=false;$('status').textContent=`Đang phát trên thiết bị này · ${sr} Hz`}}const remain=Math.max(0,next-audioCtx.currentTime);if(remain)await new Promise(ok=>setTimeout(ok,remain*1000));if(session===playSession){webPlaying=false;activeAbort=null;$('status').textContent='Đã phát xong trên thiết bị này.'}}
async function sendPc(p){$('status').textContent='Đang gửi vào queue của PC...';const r=await fetch('/api/speak',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)}),d=await r.json();if(!r.ok)throw new Error(JSON.stringify(d));$('status').textContent=`Đã xếp hàng #${d.id} · Queue: ${d.queue_size}`}
async function refreshPc(){if($('outputMode').value!=='pc'||webPlaying)return;try{const r=await fetch('/api/health',{cache:'no-store'}),d=await r.json();if(d.status==='offline'){$('status').textContent='Queue PC offline: '+(d.detail||'không kết nối được');return}const now=d.speaking?`PC đang đọc: ${d.current_text||''}`:'PC đang rảnh';$('status').textContent=`${now} · Queue: ${d.queue_size??'?'} · Đã đọc: ${d.played??0}${d.last_error?' · Lỗi: '+d.last_error:''}`}catch(e){$('status').textContent='Không đọc được trạng thái queue PC.'}}
$('speak').addEventListener('click',async()=>{const p=payload();if(!p.text){$('status').textContent='Hãy nhập nội dung cần đọc.';return}try{if($('outputMode').value==='web')await playWeb(p);else await sendPc(p)}catch(e){if(e&&e.name==='AbortError')return;webPlaying=false;$('status').textContent='Lỗi: '+e}});
$('stopWeb').addEventListener('click',()=>stopWeb(true));$('clear').addEventListener('click',async()=>{try{const r=await fetch('/api/clear',{method:'POST'}),d=await r.json();$('status').textContent=`Đã xóa ${d.cleared??0} câu đang chờ trên PC.`}catch(e){$('status').textContent='Lỗi xóa queue PC: '+e}});$('volume').addEventListener('input',()=>{if(gainNode)gainNode.gain.value=Number($('volume').value)/100});$('outputMode').addEventListener('change',()=>{$('priority').disabled=$('outputMode').value==='web';if($('outputMode').value==='web')$('status').textContent='Sẵn sàng phát trên thiết bị đang mở web.';else refreshPc()});$('priority').disabled=true;loadVoices();setInterval(refreshPc,2000);
</script></body></html>'''


@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(HTML, headers={"Cache-Control": "no-store"})


if __name__ == "__main__":
    print("=" * 64)
    print("VIE-NEU LIVE TTS WEB")
    print(f"Web        : http://127.0.0.1:{PORT}")
    print(f"TTS server : {TTS_SERVER}")
    print(f"Live queue : {LIVE_QUEUE}")
    print("Browser mode: audio phát trên thiết bị đang mở web")
    print("=" * 64)
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
