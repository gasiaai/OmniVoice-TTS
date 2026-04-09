"""
OmniVoice TTS — FastAPI Server
รันด้วย:  python server.py
เปิดที่:  http://localhost:7862
"""
import sys
import os
import json
import asyncio
import threading
import tempfile

# Ensure project dir is on sys.path (needed for python_embeded)
_app_dir = os.path.dirname(os.path.abspath(__file__))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

# Fix Windows console encoding
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import omnivoice_core as core

# ─── SETUP ─────────────────────────────────────────────────────────────────────
APP_DIR    = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(APP_DIR, "static")
OUTPUT_DIR = os.path.join(APP_DIR, "output")
TMP_DIR    = os.path.join(APP_DIR, "tmp")
os.makedirs(TMP_DIR, exist_ok=True)

app = FastAPI(title="OmniVoice TTS")

# ─── HELPERS ───────────────────────────────────────────────────────────────────
def _to_url(path: str | None) -> str | None:
    """Convert absolute output path → URL path for client."""
    if not path:
        return None
    fname = os.path.basename(path)
    return f"/output/{fname}"


async def _save_upload(upload: UploadFile | None) -> str | None:
    """Save uploaded file to tmp/ and return path, or None."""
    if upload is None or not upload.filename:
        return None
    suffix = os.path.splitext(upload.filename)[1] or ".bin"
    fd, path = tempfile.mkstemp(suffix=suffix, dir=TMP_DIR)
    try:
        data = await upload.read()
        with os.fdopen(fd, "wb") as f:
            f.write(data)
    except Exception:
        os.close(fd)
        raise
    # transcode WebM/Ogg → WAV (Windows Chrome MediaRecorder)
    if suffix.lower() in (".webm", ".ogg"):
        wav_path = path[: -len(suffix)] + ".wav"
        try:
            from pydub import AudioSegment
            seg = AudioSegment.from_file(path)
            seg.export(wav_path, format="wav")
            os.remove(path)
            return wav_path
        except Exception:
            pass  # fall through, use as-is
    return path


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _patch_result_clone(result):
    if result is None:
        return None
    file_path, status, gpu_info = result
    return {"file": _to_url(file_path), "status": status, "gpu_info": gpu_info}


def _patch_result_convert(result):
    if result is None:
        return None
    file_path, transcript, status, gpu_info = result
    return {"file": _to_url(file_path), "transcript": transcript,
            "status": status, "gpu_info": gpu_info}


# ─── SSE STREAM FACTORY ────────────────────────────────────────────────────────
def _make_stream(fn, patch_fn, *args, **kwargs):
    """
    Run fn(*args, **kwargs, progress=cb) in a background thread.
    Yield SSE events: progress + done/error.
    """
    done_event = threading.Event()
    q: list[dict] = []
    result_box: list = []

    def progress_cb(frac, desc=""):
        q.append({"type": "progress", "frac": round(float(frac), 3), "desc": desc})

    def run():
        try:
            out = fn(*args, progress=progress_cb, **kwargs)
            result_box.append(("ok", out))
        except Exception as e:
            result_box.append(("error", str(e)))
        finally:
            done_event.set()

    threading.Thread(target=run, daemon=True).start()

    async def event_gen():
        while not done_event.is_set() or q:
            while q:
                yield _sse(q.pop(0))
            await asyncio.sleep(0.05)
        while q:
            yield _sse(q.pop(0))

        kind, val = result_box[0] if result_box else ("error", "no result")
        if kind == "error":
            yield _sse({"type": "error", "message": val})
        else:
            yield _sse({"type": "done", "result": patch_fn(val)})

    return event_gen()


# ─── STATIC + OUTPUT ───────────────────────────────────────────────────────────
app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


# ─── STATUS + UNLOAD ───────────────────────────────────────────────────────────
@app.get("/api/status")
async def api_status():
    return JSONResponse(core.get_status())


@app.post("/api/unload")
async def api_unload():
    msg, gpu = core.unload_model()
    return JSONResponse({"message": msg, "gpu_info": gpu})


# ─── TRANSCRIBE ────────────────────────────────────────────────────────────────
@app.post("/api/transcribe")
async def api_transcribe(audio: UploadFile = File(...)):
    path = await _save_upload(audio)
    text, status = core.transcribe_source(path)
    return JSONResponse({"text": text, "status": status})


# ─── SAMPLE SCRIPTS ────────────────────────────────────────────────────────────
@app.get("/api/sample_scripts")
async def api_sample_scripts():
    return JSONResponse(core.SAMPLE_SCRIPTS)


# ─── GENERATE: CLONE ───────────────────────────────────────────────────────────
@app.post("/api/generate/clone")
async def api_generate_clone(
    text:           str = Form(...),
    ref_text:       str = Form(""),
    instruct:       str = Form(""),
    steps:          int = Form(32),
    guidance:     float = Form(2.0),
    speed:        float = Form(1.0),
    t_shift:      float = Form(0.1),
    seed:           int = Form(0),
    duration:     float = Form(0.0),
    pos_temp:     float = Form(5.0),
    cls_temp:     float = Form(0.0),
    layer_penalty:float = Form(5.0),
    model_choice:   str = Form("OmniVoice-bf16 (~2 GB, แนะนำ)"),
    dtype_choice:   str = Form("auto"),
    attn_choice:    str = Form("auto"),
    whisper_enable: str = Form("false"),
    ref_audio: UploadFile = File(None),
):
    ref_path = await _save_upload(ref_audio)
    stream = _make_stream(
        core.generate_clone, _patch_result_clone,
        text, ref_path, ref_text, instruct,
        steps, guidance, speed, t_shift,
        seed, duration, pos_temp, cls_temp, layer_penalty,
        model_choice, dtype_choice, attn_choice,
        whisper_enable.lower() == "true",
    )
    return StreamingResponse(stream, media_type="text/event-stream")


# ─── GENERATE: DESIGN ──────────────────────────────────────────────────────────
@app.post("/api/generate/design")
async def api_generate_design(
    text:           str = Form(...),
    instruct:       str = Form(...),
    steps:          int = Form(32),
    guidance:     float = Form(2.0),
    speed:        float = Form(1.0),
    t_shift:      float = Form(0.1),
    seed:           int = Form(0),
    duration:     float = Form(0.0),
    pos_temp:     float = Form(5.0),
    cls_temp:     float = Form(0.0),
    layer_penalty:float = Form(5.0),
    model_choice:   str = Form("OmniVoice-bf16 (~2 GB, แนะนำ)"),
    dtype_choice:   str = Form("auto"),
    attn_choice:    str = Form("auto"),
    whisper_enable: str = Form("false"),
):
    stream = _make_stream(
        core.generate_design, _patch_result_clone,
        text, instruct,
        steps, guidance, speed, t_shift,
        seed, duration, pos_temp, cls_temp, layer_penalty,
        model_choice, dtype_choice, attn_choice,
        whisper_enable.lower() == "true",
    )
    return StreamingResponse(stream, media_type="text/event-stream")


# ─── GENERATE: LONGFORM ────────────────────────────────────────────────────────
@app.post("/api/generate/longform")
async def api_generate_longform(
    text:            str = Form(...),
    ref_text:        str = Form(""),
    instruct:        str = Form(""),
    steps:           int = Form(32),
    guidance:      float = Form(2.0),
    speed:         float = Form(1.0),
    t_shift:       float = Form(0.1),
    seed:            int = Form(0),
    duration:      float = Form(0.0),
    pos_temp:      float = Form(5.0),
    cls_temp:      float = Form(0.0),
    layer_penalty: float = Form(5.0),
    chunk_size:      int = Form(200),
    silence_ms:      int = Form(500),
    use_consistency: str = Form("true"),
    model_choice:    str = Form("OmniVoice-bf16 (~2 GB, แนะนำ)"),
    dtype_choice:    str = Form("auto"),
    attn_choice:     str = Form("auto"),
    whisper_enable:  str = Form("false"),
    ref_audio: UploadFile = File(None),
):
    ref_path = await _save_upload(ref_audio)
    stream = _make_stream(
        core.generate_longform, _patch_result_clone,
        text, ref_path, ref_text, instruct,
        steps, guidance, speed, t_shift,
        seed, duration, pos_temp, cls_temp, layer_penalty,
        chunk_size, silence_ms,
        use_consistency.lower() == "true",
        model_choice, dtype_choice, attn_choice,
        whisper_enable.lower() == "true",
    )
    return StreamingResponse(stream, media_type="text/event-stream")


# ─── GENERATE: VOICE CONVERT ───────────────────────────────────────────────────
@app.post("/api/generate/convert")
async def api_generate_convert(
    src_text:      str = Form(""),
    ref_text:      str = Form(""),
    steps:         int = Form(32),
    guidance:    float = Form(2.0),
    speed:       float = Form(1.0),
    t_shift:     float = Form(0.1),
    seed:          int = Form(0),
    duration:    float = Form(0.0),
    pos_temp:    float = Form(5.0),
    cls_temp:    float = Form(0.0),
    layer_penalty:float = Form(5.0),
    model_choice:  str = Form("OmniVoice-bf16 (~2 GB, แนะนำ)"),
    dtype_choice:  str = Form("auto"),
    attn_choice:   str = Form("auto"),
    src_audio: UploadFile = File(None),
    ref_audio: UploadFile = File(None),
):
    src_path = await _save_upload(src_audio)
    ref_path = await _save_upload(ref_audio)
    stream = _make_stream(
        core.generate_voice_convert, _patch_result_convert,
        src_path, src_text,
        ref_path, ref_text,
        steps, guidance, speed, t_shift,
        seed, duration, pos_temp, cls_temp, layer_penalty,
        model_choice, dtype_choice, attn_choice,
    )
    return StreamingResponse(stream, media_type="text/event-stream")


# ─── MAIN ──────────────────────────────────────────────────────────────────────
def _find_free_port(start: int = 7862, end: int = 7900) -> int:
    import socket
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"ไม่พบ port ว่างในช่วง {start}–{end}")


if __name__ == "__main__":
    import uvicorn
    import webbrowser

    port = _find_free_port()
    url  = f"http://localhost:{port}"
    print(f"[OmniVoice] Starting on {url}")
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
