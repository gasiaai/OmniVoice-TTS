# OmniVoice TTS Standalone App

A standalone Gradio web app for [OmniVoice](https://github.com/k2-fsa/omnivoice) TTS — zero-shot multilingual text-to-speech supporting 600+ languages, without requiring ComfyUI.

## Features

- **Voice Clone** — clone any voice from a 3–15 second reference audio (upload or record with mic)
- **Voice Design** — create a voice from text description (e.g. `"female, calm, british accent"`)
- **Longform** — auto-split long text into chunks and merge into one audio file
- **Voice Convert** — transcribe source audio → re-synthesize with a different reference voice
- Auto-loads model on first generation, stays loaded in VRAM until you unload
- Built-in sample scripts for recording reference voice (~5 seconds, multiple languages)
- Saves all output to `output/` folder

## Requirements

- Python 3.10+
- NVIDIA GPU recommended (CUDA 11.8+)

## Installation

Double-click `install.bat` — it will automatically:
1. Create a virtual environment (`venv/`)
2. Detect your GPU and install the correct PyTorch version
3. Install OmniVoice and all dependencies

## Usage

1. Double-click `run.bat`
2. Browser opens at http://localhost:7861
3. Choose a tab and click "สร้างเสียง" — model loads automatically on first use

## Models

| Model | Size | Notes |
|-------|------|-------|
| `drbaph/OmniVoice-bf16` | ~2 GB | Recommended, default |
| `k2-fsa/OmniVoice` | ~4 GB | Full fp32 precision |

Models download automatically from HuggingFace on first use and are cached locally.

## Credits

- **OmniVoice model** — [k2-fsa/OmniVoice](https://github.com/k2-fsa/omnivoice)
- **ComfyUI node (inspiration)** — [Saganaki22/ComfyUI-OmniVoice-TTS](https://github.com/Saganaki22/ComfyUI-OmniVoice-TTS)

## License

MIT
