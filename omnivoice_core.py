# OmniVoice TTS — Core Business Logic
#
# Credits:
#   - OmniVoice model: k2-fsa/OmniVoice (https://github.com/k2-fsa/omnivoice)
#   - ComfyUI integration that inspired this app:
#     Saganaki22/ComfyUI-OmniVoice-TTS (https://github.com/Saganaki22/ComfyUI-OmniVoice-TTS)

import sys
import os
import threading

# Add imageio-ffmpeg to PATH so pydub/torchaudio/transformers can find ffmpeg
try:
    import imageio_ffmpeg
    _ffmpeg_dir = os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())
    if _ffmpeg_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
except Exception:
    pass

# Fix Windows console encoding
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import torch
import numpy as np
import soundfile as sf
import re
import time
import gc
from datetime import datetime

# ─── CONFIG ────────────────────────────────────────────────────────────────────
APP_DIR    = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(APP_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

SAMPLE_RATE = 24000

MODEL_CHOICES = {
    "OmniVoice-bf16 (~2 GB, แนะนำ)": "drbaph/OmniVoice-bf16",
    "OmniVoice (fp32, ~4 GB)":        "k2-fsa/OmniVoice",
}

# สคริปต์สำหรับอ่านตอนอัดเสียง reference (~5 วินาที)
SAMPLE_SCRIPTS = {
    "🇹🇭 ไทย 1 — ทั่วไป":
        "สวัสดีครับ วันนี้อากาศดีมากเลยนะครับ หวังว่าทุกคนจะสบายดีนะครับ ขอบคุณมากครับ",
    "🇹🇭 ไทย 2 — สุภาพ":
        "สวัสดีค่ะ ดิฉันยินดีให้ข้อมูลทุกอย่างค่ะ กรุณาถามได้เลยนะคะ ขอบคุณค่ะ",
    "🇹🇭 ไทย 3 — บรรยาย":
        "เรื่องราวของชีวิตนั้นยาวนาน แต่ทุกการเดินทางย่อมเริ่มต้นจากก้าวแรกเสมอ",
    "🇬🇧 English 1 — neutral":
        "Hello there, how are you doing today? I hope everything is going well for you. Thank you.",
    "🇬🇧 English 2 — warm":
        "Welcome, and thank you for joining us. Please feel free to ask any questions at any time.",
    "🇬🇧 English 3 — narration":
        "The story begins on a quiet morning. The sun was rising slowly over the distant hills.",
    "🇯🇵 日本語":
        "こんにちは、今日はいい天気ですね。どうぞよろしくお願いします。ありがとうございます。",
    "🇨🇳 中文":
        "你好，今天天气真不错。希望大家都平安健康。非常感谢您的聆听。",
}

# ─── MODEL GLOBALS ─────────────────────────────────────────────────────────────
_model           = None
_loaded_model_id = None   # แค่เก็บ model_id ที่โหลดอยู่
_model_lock      = threading.Lock()


# ─── GPU HELPER ────────────────────────────────────────────────────────────────
def get_gpu_info():
    if not torch.cuda.is_available():
        return "GPU: ไม่พบ CUDA (ใช้ CPU)"
    name  = torch.cuda.get_device_name(0)
    total = torch.cuda.get_device_properties(0).total_memory / 1024**3
    used  = torch.cuda.memory_allocated(0) / 1024**3
    free  = total - used
    return f"GPU: {name} | VRAM: {used:.1f}/{total:.1f} GB ({free:.1f} GB ว่าง)"


# ─── AUTO-LOAD ─────────────────────────────────────────────────────────────────
def _ensure_model(model_choice, dtype_choice, attn_choice):
    """โหลดโมเดลถ้ายังไม่ได้โหลด หรือถ้าสลับ model_id"""
    global _model, _loaded_model_id

    model_id = MODEL_CHOICES[model_choice]

    # โหลดแล้วและเป็น model เดียวกัน → ข้ามเลย
    if _model is not None and _loaded_model_id == model_id:
        return

    # สลับ model หรือยังไม่เคยโหลด
    if _model is not None:
        print(f"[OmniVoice] Unload โมเดลเก่า...")
        _model = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    try:
        from omnivoice import OmniVoice
    except ImportError:
        raise RuntimeError("ไม่พบ omnivoice — กรุณารัน install.bat ก่อน")

    device    = "cuda" if torch.cuda.is_available() else "cpu"
    dtype_map = {"auto": None, "bf16": torch.bfloat16,
                 "fp16": torch.float16, "fp32": torch.float32}
    dtype     = dtype_map.get(dtype_choice)
    attn_impl = None if attn_choice == "auto" else attn_choice

    print(f"[OmniVoice] กำลังโหลด {model_id} → {device} ...")
    kwargs = {}
    if dtype is not None:
        kwargs["torch_dtype"] = dtype
    if attn_impl:
        kwargs["attn_implementation"] = attn_impl

    _model = OmniVoice.from_pretrained(model_id, **kwargs)
    print(f"[OmniVoice] ย้ายโมเดลไปที่ {device} ...")
    try:
        _model.to(device)
    except RuntimeError as e:
        if "no kernel image" in str(e):
            raise RuntimeError(
                "GPU ไม่รองรับ PyTorch เวอร์ชันนี้ (no kernel image)\n"
                "วิธีแก้: ลบโฟลเดอร์ venv/ แล้วรัน install.bat ใหม่\n"
                "install.bat จะติดตั้ง PyTorch cu128 ที่รองรับ GPU ใหม่ (RTX 5000+) ให้อัตโนมัติ"
            ) from e
        raise
    _loaded_model_id = model_id
    print(f"[OmniVoice] โหลดสำเร็จ — พร้อมใช้งาน")


# ─── UNLOAD ────────────────────────────────────────────────────────────────────
def unload_model():
    global _model, _loaded_model_id
    with _model_lock:
        _model           = None
        _loaded_model_id = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    return "Unload เรียบร้อย", get_gpu_info()


# ─── STATUS ────────────────────────────────────────────────────────────────────
def get_status():
    return {
        "model_loaded": _model is not None,
        "model_id":     _loaded_model_id,
        "gpu_info":     get_gpu_info(),
    }


# ─── AUDIO HELPERS ─────────────────────────────────────────────────────────────
def load_audio_tensor(path: str):
    import scipy.signal as sps
    audio, sr = sf.read(path, dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr != SAMPLE_RATE:
        new_len = int(len(audio) * SAMPLE_RATE / sr)
        audio   = sps.resample(audio, new_len)
    return torch.from_numpy(audio).unsqueeze(0)


def save_audio(audio_np: np.ndarray, prefix="tts") -> str:
    """บันทึกไฟล์ลง output/ และ return path"""
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUTPUT_DIR, f"{prefix}_{ts}.wav")
    sf.write(path, audio_np, SAMPLE_RATE)
    return path


# ─── TEXT CHUNKING ─────────────────────────────────────────────────────────────
CJK_RE = re.compile(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u0e00-\u0e7f]')

def split_text(text: str, max_chars: int = 200) -> list[str]:
    text = text.strip()
    if len(text) <= max_chars:
        return [text]
    sentences = (re.split(r'(?<=[。！？\n])', text)
                 if CJK_RE.search(text)
                 else re.split(r'(?<=[.!?\n])\s+', text))
    chunks, current = [], ""
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        if len(current) + len(sent) + 1 <= max_chars:
            current = (current + " " + sent).strip() if current else sent
        else:
            if current:
                chunks.append(current)
            while len(sent) > max_chars:
                chunks.append(sent[:max_chars])
                sent = sent[max_chars:]
            current = sent
    if current:
        chunks.append(current)
    return chunks or [text]


# ─── CORE GENERATE ─────────────────────────────────────────────────────────────
def _call_model(text, ref_audio_file, instruct,
                steps, guidance, speed, t_shift,
                seed=0, duration=0.0,
                pos_temp=5.0, cls_temp=0.0, layer_penalty=5.0):
    """ref_audio_file: path string หรือ None"""
    ref_tensor = None
    ref_audio_path = ref_audio_file if isinstance(ref_audio_file, str) else None
    if ref_audio_path:
        ref_tensor = load_audio_tensor(ref_audio_path)

    if seed > 0:
        torch.manual_seed(int(seed))
        if torch.cuda.is_available():
            torch.cuda.manual_seed(int(seed))

    audio_list = _model.generate(
        text=text,
        num_step=int(steps),
        guidance_scale=float(guidance),
        t_shift=float(t_shift),
        speed=float(speed),
        ref_audio=(ref_tensor, SAMPLE_RATE) if ref_tensor is not None else None,
        ref_text=None,
        position_temperature=float(pos_temp),
        class_temperature=float(cls_temp),
        layer_penalty_factor=float(layer_penalty),
        fix_duration=float(duration) if duration > 0 else None,
        denoise=True,
        preprocess_prompt=True,
        postprocess_output=True,
        instruct=instruct if instruct else None,
    )
    arr = audio_list[0]
    if not isinstance(arr, np.ndarray):
        arr = arr.numpy()
    return arr.squeeze() if arr.ndim > 1 else arr


# ─── HELPERS ───────────────────────────────────────────────────────────────────
def resolve_ref(file_upload, mic_recording):
    """mic_recording (filepath str) มีความสำคัญกว่า file_upload"""
    if mic_recording:
        return mic_recording
    return file_upload


def pick_script(script_name: str) -> str:
    return SAMPLE_SCRIPTS.get(script_name, "")


# ─── TAB FUNCTIONS ─────────────────────────────────────────────────────────────
def generate_clone(text, ref_audio, instruct,
                   steps, guidance, speed, t_shift,
                   seed, duration, pos_temp, cls_temp, layer_penalty,
                   model_choice, dtype_choice, attn_choice,
                   progress=None):
    """Returns (file_path, status_msg, gpu_info)"""
    if not text.strip():
        return None, "กรุณาใส่ข้อความ", get_gpu_info()
    if not ref_audio:
        return None, "กรุณาอัปโหลดหรืออัดเสียง reference", get_gpu_info()
    t0 = time.time()
    try:
        with _model_lock:
            if progress: progress(0.05, desc="กำลังโหลดโมเดล…")
            print(f"[Clone] Generating ({len(text.strip())} chars)…")
            _ensure_model(model_choice, dtype_choice, attn_choice)
            if progress: progress(0.2, desc="กำลังสร้างเสียง…")
            arr = _call_model(text.strip(), ref_audio,
                              instruct.strip() if instruct else None,
                              steps, guidance, speed, t_shift,
                              seed, duration, pos_temp, cls_temp, layer_penalty)
        path = save_audio(arr, "clone")
        print(f"[Clone] Done ({time.time()-t0:.1f}s)")
        return path, f"สำเร็จ ({time.time()-t0:.1f}s)", get_gpu_info()
    except Exception as e:
        return None, f"เกิดข้อผิดพลาด: {e}", get_gpu_info()


def generate_design(text, instruct,
                    steps, guidance, speed, t_shift,
                    seed, duration, pos_temp, cls_temp, layer_penalty,
                    model_choice, dtype_choice, attn_choice,
                    progress=None):
    """Returns (file_path, status_msg, gpu_info)"""
    if not text.strip():
        return None, "กรุณาใส่ข้อความ", get_gpu_info()
    if not instruct or not instruct.strip():
        return None, "กรุณาระบุ voice description", get_gpu_info()
    t0 = time.time()
    try:
        with _model_lock:
            if progress: progress(0.05, desc="กำลังโหลดโมเดล…")
            print(f"[Design] Generating ({len(text.strip())} chars)…")
            _ensure_model(model_choice, dtype_choice, attn_choice)
            if progress: progress(0.2, desc="กำลังสร้างเสียง…")
            arr = _call_model(text.strip(), None,
                              instruct.strip(), steps, guidance, speed, t_shift,
                              seed, duration, pos_temp, cls_temp, layer_penalty)
        path = save_audio(arr, "design")
        print(f"[Design] Done ({time.time()-t0:.1f}s)")
        return path, f"สำเร็จ ({time.time()-t0:.1f}s)", get_gpu_info()
    except Exception as e:
        return None, f"เกิดข้อผิดพลาด: {e}", get_gpu_info()


def generate_longform(text, ref_audio, instruct,
                      steps, guidance, speed, t_shift,
                      seed, duration, pos_temp, cls_temp, layer_penalty,
                      chunk_size, silence_ms, use_consistency,
                      model_choice, dtype_choice, attn_choice,
                      progress=None):
    """Returns (file_path, status_msg, gpu_info)"""
    if not text.strip():
        return None, "กรุณาใส่ข้อความ", get_gpu_info()

    chunks = split_text(text.strip(), max_chars=int(chunk_size))
    total  = len(chunks)
    t0     = time.time()
    print(f"[Longform] {len(text.strip())} chars → {total} chunk(s)")

    try:
        with _model_lock:
            if progress: progress(0.02, desc="กำลังโหลดโมเดล…")
            _ensure_model(model_choice, dtype_choice, attn_choice)

            silence = np.zeros(int(SAMPLE_RATE * silence_ms / 1000), dtype=np.float32)
            all_audio     = []
            cur_ref_audio = ref_audio
            tmp_ref_path  = None

            for i, chunk in enumerate(chunks):
                if progress: progress((i + 0.5) / total, desc=f"Chunk {i+1}/{total}…")
                print(f"[Longform] Chunk {i+1}/{total} ({len(chunk)} chars)…")
                arr = _call_model(chunk, cur_ref_audio,
                                  instruct.strip() if instruct else None,
                                  steps, guidance, speed, t_shift,
                                  seed, duration, pos_temp, cls_temp, layer_penalty)
                all_audio.append(arr)

                if use_consistency and i == 0 and cur_ref_audio is None:
                    tmp_ref_path  = os.path.join(OUTPUT_DIR, "_tmp_ref.wav")
                    sf.write(tmp_ref_path, arr, SAMPLE_RATE)
                    cur_ref_audio = tmp_ref_path

                if i < total - 1:
                    all_audio.append(silence)

        combined = np.concatenate(all_audio)
        path = save_audio(combined, "longform")
        dur = len(combined) / SAMPLE_RATE

        if tmp_ref_path and os.path.exists(tmp_ref_path):
            os.remove(tmp_ref_path)

        print(f"[Longform] Done: {total} chunks, {dur:.1f}s audio, {time.time()-t0:.1f}s elapsed")
        return path, f"สำเร็จ | {total} chunks | {dur:.1f}s | ({time.time()-t0:.1f}s)", get_gpu_info()
    except Exception as e:
        return None, f"เกิดข้อผิดพลาด: {e}", get_gpu_info()


