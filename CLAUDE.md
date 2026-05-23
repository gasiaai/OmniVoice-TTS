# OmniVoice TTS — Agent Guide

This file is the entry point for any AI coding agent (Claude Code, Codex, Cursor, etc.) working in this repo. Read this first before touching code.

## What this is

Standalone desktop TTS app wrapping [k2-fsa/OmniVoice](https://github.com/k2-fsa/omnivoice) (zero-shot multilingual, 600+ languages). Windows-only, embedded Python runtime, FastAPI backend + vanilla-JS frontend. No ComfyUI dependency, no framework on the client side.

Three generation modes only:
- **Voice Clone** — clone from a 3–15s reference audio
- **Voice Design** — generate voice from text description (e.g. `female, young adult, british accent`)
- **Longform** — auto-chunk long text, optional voice consistency across chunks

## What this is NOT (do not re-add)

- **No "Re-voice" / Voice Convert tab.** It was removed because zero-shot clone produces equivalent quality with less UX confusion. Do not add it back.
- **No Whisper / ASR step.** An A/B test confirmed zero-shot clone matches Whisper-aided generation. Whisper was dropped to cut model load time and dependencies. Do not reintroduce `openai-whisper` or `faster-whisper`.
- **No ComfyUI nodes.** This is the standalone fork; keep it standalone.

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

### Model lifecycle
- Lazy-loaded on first generate via `_ensure_model()`. Kept in a module-level global guarded by `_model_lock` (a `threading.Lock`) — generations are serialized.
- Switching `model_choice` triggers unload + reload of the new model_id.
- `unload_model()` clears the global and runs `gc.collect()` + `torch.cuda.empty_cache()`.

### SSE protocol (server → client)
Each event is `data: {json}\n\n` where json is one of:
- `{"type": "progress", "frac": 0.0–1.0, "desc": "..."}`
- `{"type": "done", "result": {"file": "/output/xxx.wav", "status": "...", "gpu_info": "..."}}`
- `{"type": "error", "message": "..."}`

Generated files are saved under `output/` and served via the `/output` static mount.

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

## Code conventions

- **Comments** — mostly absent. Don't add explanatory comments unless the *why* is non-obvious (a workaround, a Windows quirk, a model API gotcha).
- **Thai in user-facing strings is fine** — error messages, status text, sample scripts. Backend log lines mix Thai + English; that's intentional. Module-level constants and code identifiers stay in English.
- **Encoding** — both `server.py` and `omnivoice_core.py` reconfigure stdout/stderr to UTF-8 at startup; preserve that boilerplate when refactoring.
- **No new files unless necessary.** The whole app is intentionally < 10 source files. Prefer extending `omnivoice_core.py` over creating new modules.
- **Frontend** — vanilla JS only. No build step, no npm, no React. CSS uses CSS variables for the light/dark theme; check `static/style.css` before adding new colors.

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

## Distribution

Two channels, kept in sync:
1. **GitHub repo** — `git clone` → `install.bat` → `run.bat`. `update.bat` handles `git pull`.
2. **`.rar` release on GitHub Releases** — ships `python_embeded/` pre-extracted (or not, depending on size). `update.bat` detects a missing `.git`, runs `git init` + `git remote add origin` + `git reset --hard origin/main` to convert a `.rar` install into a git checkout on first update.

Don't break the no-git-installed path of `update.bat`. Test it if you change `update.bat` or the repo layout.

## Future direction (heads-up)

The user is planning a **Tauri 2.x desktop rewrite** in a separate folder for commercial release. This current FastAPI app stays as the reference implementation. Don't refactor this app to share code with the future Tauri version — keep this one stable and simple. The Tauri rewrite will use the in-process embedding pattern (see `omnivoice-inprocess` skill in user's notes), not HTTP.

## Things to double-check before declaring "done"

- [ ] Run `run.bat` and generate at least one clip per mode you touched.
- [ ] Confirm `/api/status` still returns valid JSON (model_loaded, gpu_info).
- [ ] If you edited `install.py` / `requirements.txt` / `bootstrap.py`: blow away `python_embeded/` and re-run `install.bat` from scratch on a clean path.
- [ ] If you changed SSE event shapes: grep `static/app.js` for `event.data` / `JSON.parse` and update both sides.
- [ ] No new `.wav` / `.mp3` / `.flac` files committed. `.gitignore` excludes them but double-check `git status`.

## Credits

- OmniVoice model — [k2-fsa/OmniVoice](https://github.com/k2-fsa/omnivoice)
- ComfyUI node that inspired the standalone fork — [Saganaki22/ComfyUI-OmniVoice-TTS](https://github.com/Saganaki22/ComfyUI-OmniVoice-TTS)
