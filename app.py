# OmniVoice TTS Standalone App
# A Gradio-based standalone app for OmniVoice TTS — no ComfyUI required.
#
# Credits:
#   - OmniVoice model: k2-fsa/OmniVoice (https://github.com/k2-fsa/omnivoice)
#   - ComfyUI integration that inspired this app:
#     Saganaki22/ComfyUI-OmniVoice-TTS (https://github.com/Saganaki22/ComfyUI-OmniVoice-TTS)

import sys
import os
import io

# Fix Windows console encoding
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
os.environ["PYTHONIOENCODING"] = "utf-8"

import gradio as gr
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
_model          = None
_whisper_pipe   = None
_loaded_model_id = None   # แค่เก็บ model_id ที่โหลดอยู่


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
def _ensure_model(model_choice, dtype_choice, attn_choice, whisper_enable):
    """โหลดโมเดลถ้ายังไม่ได้โหลด หรือถ้าสลับ model_id"""
    global _model, _whisper_pipe, _loaded_model_id

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
    _model.to(device)
    _loaded_model_id = model_id
    print(f"[OmniVoice] โหลดสำเร็จ — พร้อมใช้งาน")

    if whisper_enable and _whisper_pipe is None:
        print("[OmniVoice] กำลังโหลด Whisper ...")
        try:
            from transformers import pipeline as hf_pipeline
            _whisper_pipe = hf_pipeline(
                "automatic-speech-recognition",
                model="openai/whisper-large-v3-turbo",
                device=device,
            )
            print("[OmniVoice] Whisper โหลดสำเร็จ")
        except Exception as e:
            print(f"[OmniVoice] Whisper ล้มเหลว: {e}")


# ─── ENSURE WHISPER (แยกจาก main model) ───────────────────────────────────────
def _ensure_whisper():
    global _whisper_pipe
    if _whisper_pipe is not None:
        return
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("[OmniVoice] กำลังโหลด Whisper ...")
    try:
        from transformers import pipeline as hf_pipeline
        _whisper_pipe = hf_pipeline(
            "automatic-speech-recognition",
            model="openai/whisper-large-v3-turbo",
            device=device,
        )
        print("[OmniVoice] Whisper โหลดสำเร็จ")
    except Exception as e:
        raise RuntimeError(f"โหลด Whisper ล้มเหลว: {e}")


# ─── UNLOAD ────────────────────────────────────────────────────────────────────
def unload_model():
    global _model, _whisper_pipe, _loaded_model_id
    _model           = None
    _whisper_pipe    = None
    _loaded_model_id = None
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return "Unload เรียบร้อย", get_gpu_info()


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


def auto_transcribe(audio_path: str) -> str:
    if _whisper_pipe is None:
        return ""
    result = _whisper_pipe(audio_path, return_timestamps=True)
    return result.get("text", "").strip()


def save_audio(audio_np: np.ndarray, prefix="tts") -> str:
    """บันทึกไฟล์ลง output/ และ return path"""
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUTPUT_DIR, f"{prefix}_{ts}.wav")
    sf.write(path, audio_np, SAMPLE_RATE)
    return path

def to_gradio_audio(audio_np: np.ndarray):
    """Convert float32 → int16 แล้ว return tuple ให้ Gradio"""
    audio_int16 = (audio_np * 32767).clip(-32768, 32767).astype(np.int16)
    return (SAMPLE_RATE, audio_int16)


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
def _call_model(text, ref_audio_file, ref_text, instruct, steps, guidance, speed, t_shift):
    """ref_audio_file: path string หรือ gr.File object (มี .name) หรือ None"""
    ref_tensor = None
    ref_audio_path = None
    if ref_audio_file is not None:
        ref_audio_path = ref_audio_file.name if hasattr(ref_audio_file, "name") else ref_audio_file
    if ref_audio_path:
        ref_tensor = load_audio_tensor(ref_audio_path)
        if not ref_text:
            ref_text = auto_transcribe(ref_audio_path)

    audio_list = _model.generate(
        text=text,
        num_step=int(steps),
        guidance_scale=float(guidance),
        t_shift=float(t_shift),
        speed=float(speed),
        ref_audio=(ref_tensor, SAMPLE_RATE) if ref_tensor is not None else None,
        ref_text=ref_text if ref_text else None,
        position_temperature=5.0,
        class_temperature=0.0,
        layer_penalty_factor=5.0,
        denoise=True,
        preprocess_prompt=True,
        postprocess_output=True,
        instruct=instruct if instruct else None,
    )
    arr = audio_list[0]
    if not isinstance(arr, np.ndarray):
        arr = arr.numpy()
    return arr.squeeze() if arr.ndim > 1 else arr


# ─── TAB FUNCTIONS ─────────────────────────────────────────────────────────────
def generate_clone(text, ref_audio, ref_mic, ref_text,
                   steps, guidance, speed, t_shift,
                   model_choice, dtype_choice, attn_choice, whisper_enable,
                   progress=gr.Progress()):
    ref_audio = resolve_ref(ref_audio, ref_mic)
    if not text.strip():
        return None, "กรุณาใส่ข้อความ", get_gpu_info()
    if not ref_audio:
        return None, "กรุณาอัปโหลดหรืออัดเสียง reference", get_gpu_info()
    t0 = time.time()
    try:
        progress(0.05, desc="กำลังโหลดโมเดล…")
        _ensure_model(model_choice, dtype_choice, attn_choice, whisper_enable)
        progress(0.2, desc="กำลังสร้างเสียง…")
        arr = _call_model(text.strip(), ref_audio, ref_text.strip(),
                          None, steps, guidance, speed, t_shift)
        save_audio(arr, "clone")
        return to_gradio_audio(arr), f"สำเร็จ ({time.time()-t0:.1f}s)", get_gpu_info()
    except Exception as e:
        return None, f"เกิดข้อผิดพลาด: {e}", get_gpu_info()


def generate_design(text, instruct,
                    steps, guidance, speed, t_shift,
                    model_choice, dtype_choice, attn_choice, whisper_enable,
                    progress=gr.Progress()):
    if not text.strip():
        return None, "กรุณาใส่ข้อความ", get_gpu_info()
    if not instruct.strip():
        return None, "กรุณาระบุ voice description", get_gpu_info()
    t0 = time.time()
    try:
        progress(0.05, desc="กำลังโหลดโมเดล…")
        _ensure_model(model_choice, dtype_choice, attn_choice, whisper_enable)
        progress(0.2, desc="กำลังสร้างเสียง…")
        arr = _call_model(text.strip(), None, None,
                          instruct.strip(), steps, guidance, speed, t_shift)
        save_audio(arr, "design")
        return to_gradio_audio(arr), f"สำเร็จ ({time.time()-t0:.1f}s)", get_gpu_info()
    except Exception as e:
        return None, f"เกิดข้อผิดพลาด: {e}", get_gpu_info()


def load_txt(file_obj):
    if file_obj is None:
        return ""
    with open(file_obj.name, encoding="utf-8", errors="replace") as f:
        return f.read()


def generate_longform(text, ref_audio, ref_mic, ref_text, instruct,
                      steps, guidance, speed, t_shift,
                      chunk_size, silence_ms, use_consistency,
                      model_choice, dtype_choice, attn_choice, whisper_enable,
                      progress=gr.Progress()):
    if not text.strip():
        return None, "กรุณาใส่ข้อความ", get_gpu_info()

    ref_audio = resolve_ref(ref_audio, ref_mic)
    chunks = split_text(text.strip(), max_chars=int(chunk_size))
    total  = len(chunks)
    t0     = time.time()

    try:
        progress(0.02, desc="กำลังโหลดโมเดล…")
        _ensure_model(model_choice, dtype_choice, attn_choice, whisper_enable)
    except Exception as e:
        return None, f"เกิดข้อผิดพลาด: {e}", get_gpu_info()

    silence = np.zeros(int(SAMPLE_RATE * silence_ms / 1000), dtype=np.float32)
    all_audio     = []
    cur_ref_audio = ref_audio
    cur_ref_text  = ref_text.strip() if ref_text else ""
    tmp_ref_path  = None

    try:
        for i, chunk in enumerate(chunks):
            progress((i + 0.5) / total, desc=f"Chunk {i+1}/{total}…")
            arr = _call_model(chunk, cur_ref_audio, cur_ref_text,
                              instruct.strip() if instruct else None,
                              steps, guidance, speed, t_shift)
            all_audio.append(arr)

            if use_consistency and i == 0 and cur_ref_audio is None:
                tmp_ref_path  = os.path.join(OUTPUT_DIR, "_tmp_ref.wav")
                sf.write(tmp_ref_path, arr, SAMPLE_RATE)
                cur_ref_audio = tmp_ref_path
                cur_ref_text  = chunk

            if i < total - 1:
                all_audio.append(silence)

        combined = np.concatenate(all_audio)
        save_audio(combined, "longform")
        dur = len(combined) / SAMPLE_RATE

        if tmp_ref_path and os.path.exists(tmp_ref_path):
            os.remove(tmp_ref_path)

        return to_gradio_audio(combined), f"สำเร็จ | {total} chunks | {dur:.1f}s | ({time.time()-t0:.1f}s)", get_gpu_info()
    except Exception as e:
        return None, f"เกิดข้อผิดพลาด: {e}", get_gpu_info()


def do_transcribe(audio_file):
    if not audio_file:
        return ""
    if _whisper_pipe is None:
        return "(เปิดใช้ Whisper ในตั้งค่าโมเดลก่อน)"
    path = audio_file.name if hasattr(audio_file, "name") else audio_file
    return auto_transcribe(path)


def pick_script(script_name: str) -> str:
    return SAMPLE_SCRIPTS.get(script_name, "")


def resolve_ref(file_upload, mic_recording):
    """mic_recording (filepath str) มีความสำคัญกว่า file_upload"""
    if mic_recording:
        return mic_recording
    return file_upload


# ─── TAB: VOICE CONVERT ────────────────────────────────────────────────────────
def transcribe_source(src_file, progress=gr.Progress()):
    """Transcribe เสียงต้นทาง — เรียกจากปุ่มแยก ก่อนกด Generate"""
    if not src_file:
        return "", "กรุณาอัปโหลดไฟล์เสียงต้นทาง"
    try:
        progress(0.1, desc="กำลังโหลด Whisper…")
        _ensure_whisper()
        progress(0.5, desc="กำลัง transcribe…")
        path = src_file.name if hasattr(src_file, "name") else src_file
        text = auto_transcribe(path)
        return text, f"Transcribe สำเร็จ ({len(text)} ตัวอักษร)"
    except Exception as e:
        return "", f"เกิดข้อผิดพลาด: {e}"


def generate_voice_convert(src_file, src_text,
                           ref_file, ref_mic, ref_text,
                           steps, guidance, speed, t_shift,
                           model_choice, dtype_choice, attn_choice,
                           progress=gr.Progress()):
    src_path = src_file.name if hasattr(src_file, "name") else src_file if src_file else None
    if not src_path:
        return None, "", "กรุณาอัปโหลดไฟล์เสียงต้นทาง", get_gpu_info()

    ref = resolve_ref(ref_file, ref_mic)
    if not ref:
        return None, src_text, "กรุณาอัปโหลดหรืออัดเสียง reference", get_gpu_info()

    t0 = time.time()
    try:
        # โหลด model + whisper
        progress(0.05, desc="กำลังโหลดโมเดล…")
        _ensure_model(model_choice, dtype_choice, attn_choice, False)
        _ensure_whisper()

        # transcribe ถ้ายังไม่มีข้อความ
        text = src_text.strip()
        if not text:
            progress(0.2, desc="กำลัง transcribe…")
            text = auto_transcribe(src_path)
        if not text:
            return None, "", "Transcribe ไม่ได้ข้อความ", get_gpu_info()

        progress(0.4, desc="กำลังสร้างเสียง…")
        arr = _call_model(text, ref, ref_text.strip() if ref_text else "",
                          None, steps, guidance, speed, t_shift)
        save_audio(arr, "vconv")
        return to_gradio_audio(arr), text, f"สำเร็จ ({time.time()-t0:.1f}s)", get_gpu_info()
    except Exception as e:
        return None, src_text, f"เกิดข้อผิดพลาด: {e}", get_gpu_info()


# ─── UI ────────────────────────────────────────────────────────────────────────
def build_ui():
    with gr.Blocks(title="OmniVoice TTS", theme=gr.themes.Soft()) as demo:

        gr.Markdown("# OmniVoice TTS\nZero-shot TTS รองรับ 600+ ภาษา")

        # ── Model settings + Unload ────────────────────────────────────────────
        with gr.Accordion("ตั้งค่าโมเดล", open=False):
            with gr.Row():
                model_dd   = gr.Dropdown(list(MODEL_CHOICES), value=list(MODEL_CHOICES)[0],
                                         label="โมเดล", scale=3)
                dtype_dd   = gr.Dropdown(["auto", "bf16", "fp16", "fp32"],
                                         value="auto", label="Precision", scale=1)
                attn_dd    = gr.Dropdown(["auto", "eager", "flash_attention_2"],
                                         value="auto", label="Attention", scale=1)
            whisper_chk = gr.Checkbox(label="โหลด Whisper (auto-transcribe ref audio)", value=False)
            gr.Markdown("*โมเดลจะโหลดอัตโนมัติตอนกด 'สร้างเสียง' ครั้งแรก*")

        with gr.Row():
            gpu_box     = gr.Textbox(value=get_gpu_info(), interactive=False,
                                     label="GPU Status", scale=4)
            unload_btn  = gr.Button("Unload Model", variant="stop", scale=1)

        status_box = gr.Textbox(label="สถานะ", interactive=False)
        unload_btn.click(unload_model, outputs=[status_box, gpu_box])

        # helper: รวม model settings ให้ส่งเป็น input ได้
        _model_inputs = [model_dd, dtype_dd, attn_dd, whisper_chk]

        gr.Markdown("---")

        def adv_params(default_steps=16):
            steps    = gr.Slider(4, 64,  value=default_steps, step=1,
                                 label="Diffusion Steps (น้อย=เร็ว, มาก=คุณภาพดี)")
            guidance = gr.Slider(0.0, 10.0, value=3.0, step=0.5, label="Guidance Scale")
            speed    = gr.Slider(0.5, 2.0,  value=1.0, step=0.05, label="ความเร็วเสียง")
            t_shift  = gr.Slider(0.0, 1.0,  value=0.3, step=0.05, label="t-shift")
            return steps, guidance, speed, t_shift

        with gr.Tabs():

            # ── Voice Clone ────────────────────────────────────────────────────
            with gr.Tab("Voice Clone"):
                gr.Markdown("โคลนเสียงจาก reference audio (3–15 วินาที)")
                with gr.Row():
                    with gr.Column(scale=2):
                        vc_text = gr.Textbox(label="ข้อความ", lines=6)

                        with gr.Tabs():
                            # อัปโหลดไฟล์ (default)
                            with gr.Tab("อัปโหลดไฟล์"):
                                vc_ref = gr.File(
                                    label="Reference Audio (.wav/.mp3/.flac)",
                                    file_types=["audio"],
                                )

                            # อัดเสียงเอง
                            with gr.Tab("อัดเสียงเอง"):
                                vc_script_dd = gr.Dropdown(
                                    choices=list(SAMPLE_SCRIPTS.keys()),
                                    value=list(SAMPLE_SCRIPTS.keys())[0],
                                    label="เลือกสคริปต์สำหรับอ่าน (~5 วินาที)",
                                )
                                vc_script_box = gr.Textbox(
                                    value=list(SAMPLE_SCRIPTS.values())[0],
                                    label="อ่านข้อความนี้ตอนอัดเสียง",
                                    interactive=False,
                                    lines=2,
                                )
                                vc_script_dd.change(pick_script, [vc_script_dd], [vc_script_box])
                                vc_mic = gr.Audio(
                                    label="อัดเสียง",
                                    sources=["microphone"],
                                    type="filepath",
                                )

                        with gr.Row():
                            vc_ref_txt = gr.Textbox(label="Transcript (ไม่จำเป็น)", lines=2,
                                                    placeholder="ปล่อยว่างได้ถ้าโหลด Whisper")
                            vc_asr_btn = gr.Button("Auto Transcribe", size="sm", scale=0)
                        vc_asr_btn.click(
                            lambda f, m: do_transcribe(resolve_ref(f, m)),
                            [vc_ref, vc_mic], [vc_ref_txt]
                        )

                        with gr.Accordion("Advanced", open=False):
                            vc_steps, vc_guid, vc_spd, vc_ts = adv_params()
                        vc_btn = gr.Button("สร้างเสียง", variant="primary")

                    with gr.Column(scale=1):
                        vc_out    = gr.Audio(label="ผลลัพธ์")
                        vc_status = gr.Textbox(label="สถานะ", interactive=False)

                vc_btn.click(
                    generate_clone,
                    inputs=[vc_text, vc_ref, vc_mic, vc_ref_txt,
                            vc_steps, vc_guid, vc_spd, vc_ts,
                            *_model_inputs],
                    outputs=[vc_out, vc_status, gpu_box],
                )

            # ── Voice Design ───────────────────────────────────────────────────
            with gr.Tab("Voice Design"):
                gr.Markdown("สร้างเสียงจาก description ไม่ต้องมี reference audio")
                with gr.Row():
                    with gr.Column(scale=2):
                        vd_text = gr.Textbox(label="ข้อความ", lines=6)
                        vd_inst = gr.Textbox(label="Voice Description (English)",
                                             lines=2,
                                             placeholder='"female, calm, low pitch, british accent"')
                        with gr.Accordion("Advanced", open=False):
                            vd_steps, vd_guid, vd_spd, vd_ts = adv_params()
                        vd_btn = gr.Button("สร้างเสียง", variant="primary")
                    with gr.Column(scale=1):
                        vd_out    = gr.Audio(label="ผลลัพธ์")
                        vd_status = gr.Textbox(label="สถานะ", interactive=False)

                vd_btn.click(
                    generate_design,
                    inputs=[vd_text, vd_inst,
                            vd_steps, vd_guid, vd_spd, vd_ts,
                            *_model_inputs],
                    outputs=[vd_out, vd_status, gpu_box],
                )

            # ── Longform ───────────────────────────────────────────────────────
            with gr.Tab("Longform"):
                gr.Markdown("ข้อความยาว — แบ่ง chunk อัตโนมัติและต่อเสียงเป็นไฟล์เดียว")
                with gr.Row():
                    with gr.Column(scale=2):
                        lf_text = gr.Textbox(label="ข้อความ", lines=10)
                        lf_file = gr.File(label="อัปโหลด .txt", file_types=[".txt"])
                        lf_file.change(load_txt, [lf_file], [lf_text])

                        with gr.Accordion("Reference Voice (ไม่จำเป็น)", open=False):
                            with gr.Tabs():
                                with gr.Tab("อัปโหลดไฟล์"):
                                    lf_ref = gr.File(label="Reference Audio (.wav/.mp3/.flac)",
                                                     file_types=["audio"])
                                with gr.Tab("อัดเสียงเอง"):
                                    lf_script_dd = gr.Dropdown(
                                        choices=list(SAMPLE_SCRIPTS.keys()),
                                        value=list(SAMPLE_SCRIPTS.keys())[0],
                                        label="เลือกสคริปต์",
                                    )
                                    lf_script_box = gr.Textbox(
                                        value=list(SAMPLE_SCRIPTS.values())[0],
                                        label="อ่านข้อความนี้ตอนอัดเสียง",
                                        interactive=False, lines=2,
                                    )
                                    lf_script_dd.change(pick_script, [lf_script_dd], [lf_script_box])
                                    lf_mic = gr.Audio(
                                        label="อัดเสียง",
                                        sources=["microphone"],
                                        type="filepath",
                                    )
                            with gr.Row():
                                lf_ref_txt = gr.Textbox(label="Transcript", lines=2)
                                lf_asr_btn = gr.Button("Auto Transcribe", size="sm", scale=0)
                            lf_asr_btn.click(
                                lambda f, m: do_transcribe(resolve_ref(f, m)),
                                [lf_ref, lf_mic], [lf_ref_txt]
                            )

                        with gr.Accordion("Voice Design (ถ้าไม่มี ref)", open=False):
                            lf_inst = gr.Textbox(label="Voice Description", lines=2)

                        with gr.Accordion("Advanced", open=False):
                            lf_steps, lf_guid, lf_spd, lf_ts = adv_params()
                            with gr.Row():
                                lf_chunk  = gr.Slider(50, 400, value=200, step=10,
                                                      label="ความยาว chunk (ตัวอักษร)")
                                lf_sil    = gr.Slider(0, 2000, value=500, step=100,
                                                      label="silence ระหว่าง chunk (ms)")
                            lf_consist = gr.Checkbox(
                                label="Voice Consistency (ใช้ chunk แรกเป็น ref ถ้าไม่มี ref audio)",
                                value=True)

                        lf_btn = gr.Button("สร้างเสียง", variant="primary")
                    with gr.Column(scale=1):
                        lf_out    = gr.Audio(label="ผลลัพธ์")
                        lf_status = gr.Textbox(label="สถานะ", interactive=False)

                lf_btn.click(
                    generate_longform,
                    inputs=[lf_text, lf_ref, lf_mic, lf_ref_txt, lf_inst,
                            lf_steps, lf_guid, lf_spd, lf_ts,
                            lf_chunk, lf_sil, lf_consist,
                            *_model_inputs],
                    outputs=[lf_out, lf_status, gpu_box],
                )

            # ── Voice Convert ──────────────────────────────────────────────────
            with gr.Tab("Voice Convert"):
                gr.Markdown(
                    "แปลงเสียงจากไฟล์เสียงต้นทาง → เสียง reference ที่เลือก  \n"
                    "*(Whisper transcribe ข้อความจากเสียงต้นทาง → OmniVoice สร้างใหม่ด้วยเสียง reference)*"
                )
                with gr.Row():
                    with gr.Column(scale=2):

                        # เสียงต้นทาง
                        gr.Markdown("#### เสียงต้นทาง")
                        vc2_src = gr.File(label="อัปโหลดไฟล์เสียงที่ต้องการแปลง (.wav/.mp3/.flac)",
                                          file_types=["audio"])
                        with gr.Row():
                            vc2_transcribe_btn = gr.Button("Transcribe ข้อความ (Whisper)", size="sm")
                            vc2_src_status = gr.Textbox(label="", interactive=False,
                                                        scale=2, show_label=False)
                        vc2_src_text = gr.Textbox(
                            label="ข้อความจากเสียงต้นทาง (แก้ไขได้)",
                            lines=4,
                            placeholder="กด 'Transcribe' หรือพิมพ์เองก็ได้",
                        )
                        vc2_transcribe_btn.click(
                            transcribe_source,
                            inputs=[vc2_src],
                            outputs=[vc2_src_text, vc2_src_status],
                        )

                        gr.Markdown("#### เสียง Reference (เสียงที่ต้องการเปลี่ยนเป็น)")
                        with gr.Tabs():
                            with gr.Tab("อัปโหลดไฟล์"):
                                vc2_ref = gr.File(label="Reference Audio (.wav/.mp3/.flac)",
                                                  file_types=["audio"])
                            with gr.Tab("อัดเสียงเอง"):
                                vc2_script_dd = gr.Dropdown(
                                    choices=list(SAMPLE_SCRIPTS.keys()),
                                    value=list(SAMPLE_SCRIPTS.keys())[0],
                                    label="เลือกสคริปต์",
                                )
                                vc2_script_box = gr.Textbox(
                                    value=list(SAMPLE_SCRIPTS.values())[0],
                                    label="อ่านข้อความนี้ตอนอัดเสียง",
                                    interactive=False, lines=2,
                                )
                                vc2_script_dd.change(pick_script, [vc2_script_dd], [vc2_script_box])
                                vc2_mic = gr.Audio(label="อัดเสียง",
                                                   sources=["microphone"], type="filepath")

                        vc2_ref_text = gr.Textbox(label="Transcript ของ Reference (ไม่จำเป็น)",
                                                  lines=2)

                        with gr.Accordion("Advanced", open=False):
                            vc2_steps, vc2_guid, vc2_spd, vc2_ts = adv_params()

                        vc2_btn = gr.Button("แปลงเสียง", variant="primary")

                    with gr.Column(scale=1):
                        vc2_out        = gr.Audio(label="ผลลัพธ์")
                        vc2_text_out   = gr.Textbox(label="ข้อความที่ใช้สร้างเสียง", interactive=False, lines=4)
                        vc2_status     = gr.Textbox(label="สถานะ", interactive=False)

                # model inputs ไม่รวม whisper_chk เพราะ Voice Convert บังคับโหลด Whisper เอง
                _model_inputs_no_whisper = [model_dd, dtype_dd, attn_dd]

                vc2_btn.click(
                    generate_voice_convert,
                    inputs=[vc2_src, vc2_src_text,
                            vc2_ref, vc2_mic, vc2_ref_text,
                            vc2_steps, vc2_guid, vc2_spd, vc2_ts,
                            *_model_inputs_no_whisper],
                    outputs=[vc2_out, vc2_text_out, vc2_status, gpu_box],
                )

    return demo


if __name__ == "__main__":
    demo = build_ui()
    demo.launch(server_name="0.0.0.0", server_port=7861, inbrowser=True)
