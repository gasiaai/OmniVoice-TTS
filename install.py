"""
OmniVoice TTS — Auto Installer
รันผ่าน install.bat เท่านั้น (ต้องอยู่ใน venv แล้ว)
"""
import sys
import os
import subprocess
import re

# ── ตั้งค่า encoding ──────────────────────────────────────────────────────────
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def run(cmd: list, check=True, quiet=False) -> subprocess.CompletedProcess:
    kwargs = dict(check=check)
    if quiet:
        kwargs.update(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return subprocess.run(cmd, **kwargs)


def pip(*args, quiet=False):
    return run([sys.executable, "-m", "pip", "install", *args], quiet=quiet)


def section(msg: str):
    print(f"\n{'='*52}")
    print(f"  {msg}")
    print('='*52)


# ── 1. อัปเกรด pip ────────────────────────────────────────────────────────────
section("1/5  อัปเกรด pip")
pip("--upgrade", "pip", quiet=True)
print("  pip OK")

# ── 2. ตรวจ / ติดตั้ง PyTorch ─────────────────────────────────────────────────
section("2/5  ตรวจสอบ PyTorch")

torch_ok = False
try:
    import torch
    print(f"  พบ PyTorch {torch.__version__}  |  CUDA: {torch.cuda.is_available()}")
    torch_ok = True
except ImportError:
    pass

if not torch_ok:
    # ตรวจ CUDA driver ผ่าน nvidia-smi
    cuda_major = 0
    try:
        smi = subprocess.check_output(
            ["nvidia-smi"], stderr=subprocess.DEVNULL, text=True, encoding="utf-8"
        )
        m = re.search(r"CUDA Version:\s*(\d+)\.(\d+)", smi)
        if m:
            cuda_major = int(m.group(1))
            cuda_minor = int(m.group(2))
            print(f"  พบ NVIDIA GPU  |  CUDA Driver: {cuda_major}.{cuda_minor}")
    except Exception:
        print("  ไม่พบ NVIDIA GPU — ติดตั้งแบบ CPU")

    # เลือก PyTorch build ตาม CUDA driver version
    if cuda_major >= 13:
        # Blackwell (RTX 5000 series) และ GPU ใหม่มาก — ต้องใช้ cu128+
        index_url = "https://download.pytorch.org/whl/cu128"
        label = "CUDA 12.8+ (Blackwell/RTX 5000 series)"
    elif cuda_major >= 12:
        index_url = "https://download.pytorch.org/whl/cu124"
        label = "CUDA 12.4"
    elif cuda_major >= 11:
        index_url = "https://download.pytorch.org/whl/cu118"
        label = "CUDA 11.8"
    else:
        index_url = "https://download.pytorch.org/whl/cpu"
        label = "CPU only"

    print(f"  ติดตั้ง PyTorch ({label})...")
    pip("torch", "torchaudio", "--index-url", index_url)

    import torch
    print(f"  PyTorch {torch.__version__}  |  CUDA: {torch.cuda.is_available()}")

# ── 3. ติดตั้ง omnivoice ─────────────────────────────────────────────────────
section("3/5  ติดตั้ง OmniVoice (--no-deps)")
print("  ใช้ --no-deps เพื่อไม่ให้ทับ PyTorch...")
pip("omnivoice", "--no-deps")

try:
    import omnivoice  # noqa: F401
    print("  OmniVoice OK")
except ImportError as e:
    print(f"  [WARNING] import omnivoice ล้มเหลว: {e}")

# ── 4. ติดตั้ง dependencies อื่น ─────────────────────────────────────────────
section("4/5  ติดตั้ง dependencies")
deps = [
    "fastapi>=0.110",
    "uvicorn[standard]",
    "python-multipart",
    "accelerate",
    "soundfile",
    "scipy",
    "pydub",
    "sentencepiece",
    "jieba",
    "soxr",
    "transformers>=4.57",
]
for pkg in deps:
    print(f"  {pkg}...")
    pip(pkg, quiet=True)
print("  dependencies OK")

# ── 5. สรุป ───────────────────────────────────────────────────────────────────
section("5/5  เสร็จสมบูรณ์!")
print("""
  ติดตั้งเสร็จแล้ว!

  วิธีใช้:
    - ดับเบิลคลิก run.bat เพื่อเปิดแอป
    - เบราว์เซอร์จะเปิดที่ http://localhost:7861
    - กด "สร้างเสียง" ครั้งแรก โมเดลจะโหลดอัตโนมัติ (~2-4 GB)

  หมายเหตุ:
    - ต้องใช้อินเทอร์เน็ตตอนโหลดโมเดลครั้งแรก
    - โมเดลจะ cache ไว้ใน HuggingFace local cache
""")
