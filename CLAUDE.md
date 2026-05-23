# OmniVoice TTS — Agent Guide

This file is the entry point for any AI coding agent (Claude Code, Codex, Cursor, etc.) working in this repo. Read this first before touching code.

> 🇹🇭 **อ่านไฟล์นี้ก่อนแก้โค้ดทุกครั้ง** — เป็นคู่มือสำหรับ AI agent (และมนุษย์ที่เพิ่งเข้าโปรเจกต์) บอกว่าแอปนี้คืออะไร โครงสร้างยังไง ห้ามใส่อะไรกลับ และต้องเช็คอะไรก่อนปิดงาน

## What this is

Standalone desktop TTS app wrapping [k2-fsa/OmniVoice](https://github.com/k2-fsa/omnivoice) (zero-shot multilingual, 600+ languages). Windows-only, embedded Python runtime, FastAPI backend + vanilla-JS frontend. No ComfyUI dependency, no framework on the client side.

Three generation modes only:
- **Voice Clone** — clone from a 3–15s reference audio
- **Voice Design** — generate voice from text description (e.g. `female, young adult, british accent`)
- **Longform** — auto-chunk long text, optional voice consistency across chunks

> 🇹🇭 **คืออะไร:** แอป TTS เดสก์ท็อปแบบ standalone ห่อโมเดล OmniVoice (zero-shot รองรับ 600+ ภาษา). รันบน Windows เท่านั้น, ใช้ Python ฝังในโฟลเดอร์ (`python_embeded/`), backend เป็น FastAPI + UI เป็น HTML/CSS/JS เปล่า ๆ ไม่มี React/Vue/บันเดิลใด ๆ. มี 3 โหมดเท่านั้น: Clone (โคลนเสียงจากไฟล์ ref 3–15 วิ), Design (อธิบายเสียงเป็นข้อความ), Longform (ข้อความยาวอัตโนมัติแบ่ง chunk)

## What this is NOT (do not re-add)

- **No "Re-voice" / Voice Convert tab.** It was removed because zero-shot clone produces equivalent quality with less UX confusion. Do not add it back.
- **No Whisper / ASR step.** An A/B test confirmed zero-shot clone matches Whisper-aided generation. Whisper was dropped to cut model load time and dependencies. Do not reintroduce `openai-whisper` or `faster-whisper`.
- **No ComfyUI nodes.** This is the standalone fork; keep it standalone.

> 🇹🇭 **ห้ามใส่อะไรกลับ:**
> - ❌ แท็บ "Re-voice" / Voice Convert — ลบไปแล้ว เพราะ zero-shot clone คุณภาพเท่ากันแต่ UX สับสนน้อยกว่า
> - ❌ Whisper / ASR — ทดสอบ A/B แล้วไม่จำเป็น (zero-shot ทำได้เทียบเท่า) ลบทิ้งเพื่อลด dep + เวลาโหลดโมเดล
> - ❌ ComfyUI node — เวอร์ชันนี้คือ fork แบบ standalone ห้ามผูกกับ ComfyUI

## Architecture

```
run.bat
  └─ python_embeded\python.exe server.py
       └─ FastAPI on http://localhost:7862 (auto-picks next free port up to 7900)
            ├─ GET  /                       → static/index.html
            ├─ GET  /api/status              → model loaded? GPU info
            ├─ POST /api/unload              → free VRAM
            ├─ POST /api/generate/clone      → SSE: progress + done/error
            ├─ POST /api/generate/design     → SSE: progress + done/error
            └─ POST /api/generate/longform   → SSE: progress + done/error
```

- `server.py` — FastAPI thin wrapper. Each generate endpoint runs `core.generate_*` in a daemon thread and yields SSE events. Nothing more lives here — keep it thin.
- `omnivoice_core.py` — All business logic: model load/unload, text chunking, audio I/O, the three `generate_*` functions. UI-free; safe to import from another Python project (see `omnivoice-inprocess` pattern in user memory).
- `static/` — Pure HTML + CSS + JS. No bundler, no framework. `app.js` handles SSE streaming and DOM updates directly.

> 🇹🇭 **สถาปัตยกรรม:** `run.bat` เรียก `server.py` → FastAPI เปิด port 7862 (ถ้าไม่ว่างจะหา port ถัดไปจนถึง 7900). หน้าที่แบ่งกัน 3 ไฟล์:
> - `server.py` = wrapper บาง ๆ รับ HTTP/Form แล้วโยนเข้า thread → ส่ง SSE event กลับ ห้ามใส่ logic ที่นี่
> - `omnivoice_core.py` = หัวใจของแอป โหลด/unload โมเดล, แบ่ง chunk, I/O เสียง, ฟังก์ชัน `generate_*` 3 ตัว ไม่มี UI dep — เอาไปใช้ใน project อื่นแบบ in-process ได้
> - `static/` = HTML/CSS/JS เปล่า ไม่มี build step. `app.js` รับ SSE แล้วอัปเดต DOM ตรง ๆ

### Model lifecycle
- Lazy-loaded on first generate via `_ensure_model()`. Kept in a module-level global guarded by `_model_lock` (a `threading.Lock`) — generations are serialized.
- Switching `model_choice` triggers unload + reload of the new model_id.
- `unload_model()` clears the global and runs `gc.collect()` + `torch.cuda.empty_cache()`.

> 🇹🇭 **วงจรชีวิตโมเดล:** โหลดครั้งแรกตอนสั่งสร้างเสียง (lazy), เก็บเป็น global ล็อกด้วย `_model_lock` → request ที่เข้ามาพร้อมกันจะรอคิวกัน. สลับ model_id = unload เก่าก่อนโหลดใหม่. ปุ่ม Unload ใน UI เรียก `unload_model()` ล้าง VRAM

### SSE protocol (server → client)
Each event is `data: {json}\n\n` where json is one of:
- `{"type": "progress", "frac": 0.0–1.0, "desc": "..."}`
- `{"type": "done", "result": {"file": "/output/xxx.wav", "status": "...", "gpu_info": "..."}}`
- `{"type": "error", "message": "..."}`

Generated files are saved under `output/` and served via the `/output` static mount.

> 🇹🇭 **SSE protocol:** server ส่ง event 3 ชนิด — `progress` (มี frac 0–1 + คำอธิบาย), `done` (มี path ไฟล์ + status + GPU info), `error` (มี message). ถ้าจะแก้ shape ของ event ต้องแก้ทั้ง `server.py` และ `static/app.js` พร้อมกัน

## Runtime layout (Windows, embedded Python)

```
OmniVoiceApp/
├── install.bat        # one-click installer (downloads Python embeddable, runs bootstrap + install.py)
├── run.bat            # launch server (prefers python_embeded\, falls back to venv\)
├── update.bat         # git pull + re-run install.py (also git-inits a freshly-extracted .rar)
├── bootstrap.py       # patches python_embeded\python311._pth + side-loads pip from PyPI wheel
├── install.py         # pip-installs PyTorch (CUDA-auto-detected) + OmniVoice (--no-deps) + deps
├── server.py
├── omnivoice_core.py
├── static/{index.html, style.css, app.js}
├── python_embeded/    # bundled Python 3.11.9, gitignored
├── output/            # generated audio, gitignored
└── tmp/               # uploaded refs, gitignored
```

**Important constraints:**
- Embedded Python (`python_embeded/python.exe`) is the canonical runtime, not a venv. Path is patched via `python311._pth` so `import site` works and `Lib\site-packages` is discoverable.
- Windows 260-char path limit. `install.bat` refuses to install if the full path exceeds ~180 chars. Tell users to extract to `C:\OmniVoice-TTS\`, never Desktop / Downloads.
- ffmpeg is provided by the `imageio-ffmpeg` pip package; `omnivoice_core.py` prepends its bin dir to `PATH` at import time so pydub / transformers find it without a separate ffmpeg install.

> 🇹🇭 **ข้อจำกัดสำคัญ:**
> - runtime หลักคือ `python_embeded\python.exe` (Python 3.11.9 ฝัง) ไม่ใช่ venv. ใช้ `python311._pth` เปิด site-packages — bootstrap.py จัดการให้แล้ว
> - Windows path ห้ามเกิน 260 ตัวอักษร — `install.bat` จะปฏิเสธถ้า path ยาวเกิน ~180. ต้องบอกผู้ใช้ extract ไปที่ `C:\OmniVoice-TTS\` ห้ามอยู่บน Desktop/Downloads
> - ffmpeg มาจาก pip package `imageio-ffmpeg` (ไม่ต้องลง ffmpeg แยก). `omnivoice_core.py` prepend ลง `PATH` ตอน import เพื่อให้ pydub/transformers หาเจอ

## Dev workflow

There is no test suite, no linter, no CI. Verification is manual.

```bash
# Smoke-test after a change:
.\run.bat                 # browser opens to http://localhost:7862
# Generate one clip in each mode (Clone / Design / Longform) and listen.

# Backend-only iteration (no model required for UI work):
python_embeded\python.exe server.py
# Then open http://localhost:7862 and use the UI without hitting /api/generate/*
```

To install pure-Python deps after editing `install.py` or `requirements.txt`:
```bash
python_embeded\python.exe -m pip install <package>
# OR re-run install.bat (idempotent)
```

> 🇹🇭 **วิธีทดสอบ:** ไม่มี test/lint/CI — ต้อง smoke-test ด้วยมือ. รัน `run.bat` แล้วลองสร้างเสียงทั้ง 3 โหมด ฟังผลด้วยหู. ถ้าทำงานแค่ UI ไม่ต้องโหลดโมเดล (แค่ห้ามกดปุ่มสร้าง). เพิ่ม dep ใหม่ → ทั้ง `install.py` (`deps` list) และ `requirements.txt`

## Code conventions

- **Comments** — mostly absent. Don't add explanatory comments unless the *why* is non-obvious (a workaround, a Windows quirk, a model API gotcha).
- **Thai in user-facing strings is fine** — error messages, status text, sample scripts. Backend log lines mix Thai + English; that's intentional. Module-level constants and code identifiers stay in English.
- **Encoding** — both `server.py` and `omnivoice_core.py` reconfigure stdout/stderr to UTF-8 at startup; preserve that boilerplate when refactoring.
- **No new files unless necessary.** The whole app is intentionally < 10 source files. Prefer extending `omnivoice_core.py` over creating new modules.
- **Frontend** — vanilla JS only. No build step, no npm, no React. CSS uses CSS variables for the light/dark theme; check `static/style.css` before adding new colors.

> 🇹🇭 **ธรรมเนียมการเขียนโค้ด:**
> - คอมเมนต์น้อย ๆ — เขียนเฉพาะตอน *ทำไม* ไม่ชัดเจน (workaround, Windows quirk, gotcha ของโมเดล)
> - text ที่ user เห็นเป็นภาษาไทยได้ (error/status/sample script). log mix ไทย-อังกฤษได้. แต่ตัวแปร/ค่าคงที่/identifier ต้องเป็นอังกฤษ
> - boilerplate UTF-8 reconfigure ที่หัวไฟล์ — ห้ามลบ ไม่งั้น Thai log แตกบน Windows console
> - อย่าสร้างไฟล์ใหม่ถ้าไม่จำเป็น — แอปนี้ตั้งใจให้ < 10 ไฟล์. ขยาย `omnivoice_core.py` ดีกว่าแยก module
> - frontend เป็น vanilla JS เท่านั้น ห้าม React/Vue/npm/บันเดิล. ธีมใช้ CSS variable — ดู `static/style.css` ก่อนเพิ่มสีใหม่

## Common tasks — where to look

| If you need to…                          | Open                                    |
|-------------------------------------------|-----------------------------------------|
| Add/change a generation parameter         | `omnivoice_core.py` (`_call_model`) + `server.py` (matching `Form()`) + `static/app.js` (form serialization) |
| Add a UI mode / panel                     | `static/index.html` (mode-btn + panel) + `static/app.js` (wire submit) |
| Tune text chunking                        | `omnivoice_core.py` → `split_text()`   |
| Change sample reference scripts           | `omnivoice_core.py` → `SAMPLE_SCRIPTS` |
| Adjust install / PyTorch selection logic  | `install.py`                            |
| Add a new dependency                      | `install.py` `deps` list + `requirements.txt` |
| Theme / styling                           | `static/style.css` (CSS vars at `:root` and `[data-theme="dark"]`) |

> 🇹🇭 **อยากแก้อะไร → ไปที่ไหน:**
> - เพิ่ม/แก้ parameter สร้างเสียง → แก้ 3 ที่: `omnivoice_core.py` (`_call_model`), `server.py` (`Form()`), `static/app.js` (form data)
> - เพิ่มโหมด UI ใหม่ → `static/index.html` (ปุ่ม + panel) + `static/app.js`
> - chunk ข้อความ → `split_text()` ใน core
> - sample script ตอนอัดเสียง → `SAMPLE_SCRIPTS` ใน core
> - logic เลือก CUDA / PyTorch build → `install.py`
> - ธีม/สี → `static/style.css` (`:root` กับ `[data-theme="dark"]`)

## Distribution

Two channels, kept in sync:
1. **GitHub repo** — `git clone` → `install.bat` → `run.bat`. `update.bat` handles `git pull`.
2. **`.rar` release on GitHub Releases** — ships `python_embeded/` pre-extracted (or not, depending on size). `update.bat` detects a missing `.git`, runs `git init` + `git remote add origin` + `git reset --hard origin/main` to convert a `.rar` install into a git checkout on first update.

Don't break the no-git-installed path of `update.bat`. Test it if you change `update.bat` or the repo layout.

> 🇹🇭 **ช่องทางแจกจ่าย:** มี 2 ทาง — (1) clone จาก GitHub แล้วรัน install/run, (2) โหลด .rar จาก Releases. ผู้ใช้ที่โหลด .rar ตอน update ครั้งแรก `update.bat` จะ `git init` + `git remote add` + `reset --hard origin/main` ให้อัตโนมัติ. **อย่าทำพังเส้นทาง .rar** ตอนแก้ `update.bat` หรือเปลี่ยน repo layout

## Future direction (heads-up)

The user is planning a **Tauri 2.x desktop rewrite** in a separate folder for commercial release. This current FastAPI app stays as the reference implementation. Don't refactor this app to share code with the future Tauri version — keep this one stable and simple. The Tauri rewrite will use the in-process embedding pattern (see `omnivoice-inprocess` skill in user's notes), not HTTP.

> 🇹🇭 **ทิศทางอนาคต:** เจ้าของวางแผนเขียนเวอร์ชัน Tauri 2.x (สำหรับขายเชิงพาณิชย์) ในโฟลเดอร์ใหม่ — แอป FastAPI นี้ **จะอยู่เป็น reference**. อย่ารีแฟกเตอร์แอปนี้ให้ใช้โค้ดร่วมกับ Tauri version. Tauri จะ embed OmniVoice แบบ in-process (ไม่ใช่ HTTP)

## Things to double-check before declaring "done"

- [ ] Run `run.bat` and generate at least one clip per mode you touched.
- [ ] Confirm `/api/status` still returns valid JSON (model_loaded, gpu_info).
- [ ] If you edited `install.py` / `requirements.txt` / `bootstrap.py`: blow away `python_embeded/` and re-run `install.bat` from scratch on a clean path.
- [ ] If you changed SSE event shapes: grep `static/app.js` for `event.data` / `JSON.parse` and update both sides.
- [ ] No new `.wav` / `.mp3` / `.flac` files committed. `.gitignore` excludes them but double-check `git status`.

> 🇹🇭 **เช็คก่อนปิดงาน:**
> - [ ] รัน `run.bat` แล้วสร้างเสียงในโหมดที่แก้ — ฟังด้วยหู
> - [ ] `/api/status` ยัง return JSON ถูกต้อง (`model_loaded`, `gpu_info`)
> - [ ] ถ้าแตะ `install.py` / `requirements.txt` / `bootstrap.py` → ลบ `python_embeded/` แล้วลง install ใหม่จาก path สะอาด
> - [ ] ถ้าแก้ SSE event shape → grep `static/app.js` หา `event.data` / `JSON.parse` แก้ทั้งสองฝั่ง
> - [ ] อย่าเผลอ commit ไฟล์ `.wav`/`.mp3`/`.flac` — `.gitignore` กรองอยู่แล้วแต่เช็ค `git status` ก่อน

## Credits

- OmniVoice model — [k2-fsa/OmniVoice](https://github.com/k2-fsa/omnivoice)
- ComfyUI node that inspired the standalone fork — [Saganaki22/ComfyUI-OmniVoice-TTS](https://github.com/Saganaki22/ComfyUI-OmniVoice-TTS)
