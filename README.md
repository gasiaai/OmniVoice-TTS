# OmniVoice TTS

Zero-shot multilingual text-to-speech (600+ languages) — standalone desktop app, no ComfyUI required.

![Python 3.11](https://img.shields.io/badge/Python-3.11-blue)
![CUDA](https://img.shields.io/badge/CUDA-11.8%2F12.4%2F13.0-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Features

- **Voice Clone** — clone any voice from a 3-15 second reference audio
- **Voice Design** — create a voice from text description (e.g. `"female, calm, british accent"`)
- **Longform** — auto-split long text into chunks, merge into one audio file
- **Voice Convert** — re-synthesize audio with a different voice
- Built-in mic recording (with AGC disabled for clean capture)
- Auto-loads model on first use, stays in VRAM until you unload
- Dark / Light mode toggle
- All output saved to `output/` folder

## Quick Start

### Option A: Download ready-to-run (.rar)

1. Download **[OmniVoice-TTS.rar](https://github.com/gasiaai/OmniVoice-TTS/releases/latest)** from Releases
2. Extract to a **short path** like `C:\OmniVoice-TTS\`
3. Double-click **`install.bat`** — installs Python + PyTorch + dependencies automatically
4. Double-click **`run.bat`** — browser opens, ready to use

> **Important:** Do NOT run from inside a zip or from a deep folder path like Desktop or Downloads.
> Windows has a 260-character path limit — deep paths will cause install errors.
> Extract to something short like `C:\OmniVoice-TTS\` or `D:\OmniVoice-TTS\`.

> No Python installation needed. Everything runs from a bundled `python_embeded/` folder.

### Option B: Clone from GitHub

```bash
git clone https://github.com/gasiaai/OmniVoice-TTS.git
cd OmniVoice-TTS
```

Then run `install.bat` and `run.bat` as above.

## Requirements

- **OS:** Windows 10/11 (64-bit)
- **GPU:** NVIDIA GPU recommended (CUDA 11.8+) — CPU mode available but slow
- **RAM:** 8 GB minimum, 16 GB recommended
- **Disk:** ~6 GB (Python + PyTorch + model)
- **Internet:** Required for first install and first model download

## How It Works

```
install.bat
  -> Downloads Python 3.11.9 embeddable (if not present)
  -> Patches Python for pip support (bootstrap.py)
  -> Installs PyTorch (auto-detects CUDA version)
  -> Installs OmniVoice + dependencies

run.bat
  -> Starts FastAPI server
  -> Opens browser at http://localhost:7862
```

## GPU Support

| GPU | CUDA Driver | PyTorch Build |
|-----|-------------|---------------|
| RTX 5000 series (Blackwell) | 13.x+ | cu130 |
| RTX 3000/4000 series | 12.x | cu124 |
| GTX 1000/RTX 2000 series | 11.x | cu118 |
| No NVIDIA GPU | — | CPU only |

CUDA version is detected automatically via `nvidia-smi`.

## Models

| Model | Size | Notes |
|-------|------|-------|
| `drbaph/OmniVoice-bf16` | ~2 GB | Default, recommended |
| `k2-fsa/OmniVoice` | ~4 GB | Full fp32 precision |

Models download from HuggingFace on first use and are cached locally.

## Updating

Double-click **`update.bat`** — pulls latest code from GitHub and re-runs installer.

## File Structure

```
OmniVoice-TTS/
├── install.bat          # One-click installer
├── run.bat              # Start the app
├── update.bat           # Pull updates from GitHub
├── bootstrap.py         # Sets up pip for embedded Python
├── install.py           # Installs PyTorch + dependencies
├── server.py            # FastAPI backend
├── omnivoice_core.py    # TTS engine (no UI dependency)
├── static/
│   ├── index.html       # Web UI
│   ├── style.css        # Pastel theme + dark mode
│   └── app.js           # Client-side logic + SSE
├── output/              # Generated audio files
└── python_embeded/      # Bundled Python (created by install.bat)
```

## Credits

- **OmniVoice model** — [k2-fsa/OmniVoice](https://github.com/k2-fsa/omnivoice)
- **ComfyUI node (inspiration)** — [Saganaki22/ComfyUI-OmniVoice-TTS](https://github.com/Saganaki22/ComfyUI-OmniVoice-TTS)

## License

MIT
