"""
bootstrap.py — run by install.bat using freshly extracted python_embeded\python.exe
Does two things before install.py can run:
  1. Patches ._pth file to enable site-packages  (adds path + import site)
  2. Installs pip by extracting its wheel directly into site-packages
"""
import glob
import json
import os
import sys
import subprocess
import urllib.request
import zipfile

pydir = os.path.dirname(os.path.abspath(sys.executable))
print(f"  Python dir: {pydir}")

# ── 1. Patch ._pth: add Lib\site-packages path + uncomment import site ────
patched = False
for pth_file in glob.glob(os.path.join(pydir, "*._pth")):
    with open(pth_file, "r", encoding="utf-8") as f:
        content = f.read()
    lines = content.splitlines()
    changed = False

    # Uncomment import site
    new_lines = []
    for line in lines:
        if line.strip() == "#import site":
            new_lines.append("import site")
            changed = True
        else:
            new_lines.append(line)

    # Add Lib\site-packages if not already present
    sp_entry = r"Lib\site-packages"
    if not any(l.strip() in (sp_entry, "Lib/site-packages") for l in new_lines):
        # Insert before "import site"
        idx = next((i for i, l in enumerate(new_lines) if l.strip() == "import site"), len(new_lines))
        new_lines.insert(idx, sp_entry)
        changed = True

    if changed:
        with open(pth_file, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines) + "\n")
        print(f"  Patched: {os.path.basename(pth_file)}")
        patched = True
    else:
        print(f"  {os.path.basename(pth_file)} already patched")

    # Show contents for debugging
    with open(pth_file, "r", encoding="utf-8") as f:
        print(f"  ._pth contents:")
        for line in f.read().splitlines():
            print(f"    | {line}")

if not patched:
    # Also check .pth (some builds use .pth instead of ._pth)
    for pth_file in glob.glob(os.path.join(pydir, "*.pth")):
        if pth_file.endswith("._pth"):
            continue
        print(f"  (found extra .pth: {os.path.basename(pth_file)})")

# ── 2. Ensure Lib\site-packages exists ────────────────────────────────────
site_pkgs = os.path.join(pydir, "Lib", "site-packages")
os.makedirs(site_pkgs, exist_ok=True)
print(f"  site-packages: {site_pkgs}")

# ── 3. Check pip (spawn new process so patched ._pth takes effect) ────────
check = subprocess.run(
    [sys.executable, "-m", "pip", "--version"],
    capture_output=True,
)
if check.returncode == 0:
    print(f"  pip already available: {check.stdout.decode(errors='replace').strip()}")
    sys.exit(0)

# Debug: show sys.path in subprocess to understand path issues
debug = subprocess.run(
    [sys.executable, "-c",
     "import sys; print('  sys.path:'); [print(f'    {p}') for p in sys.path]"],
    capture_output=True,
)
print(debug.stdout.decode(errors="replace"), end="")

# ── 4. Download pip wheel from PyPI and extract into site-packages ─────────
print("  Fetching pip version from PyPI...")
try:
    with urllib.request.urlopen("https://pypi.org/pypi/pip/json", timeout=30) as resp:
        data = json.loads(resp.read())
    version = data["info"]["version"]
    wheel_url = None
    for f in data["urls"]:
        if f["filename"].endswith("-py3-none-any.whl"):
            wheel_url = f["url"]
            break
    if not wheel_url:
        raise RuntimeError("No universal wheel found for pip")
    print(f"  pip {version} wheel: {wheel_url.split('/')[-1]}")
except Exception as e:
    print(f"  [ERROR] Could not fetch pip info from PyPI: {e}")
    sys.exit(1)

whl_path = os.path.join(pydir, "_pip_tmp.whl")
try:
    urllib.request.urlretrieve(wheel_url, whl_path)
except Exception as e:
    print(f"  [ERROR] Could not download pip wheel: {e}")
    sys.exit(1)

print("  Extracting pip into site-packages...")
try:
    with zipfile.ZipFile(whl_path, "r") as zf:
        zf.extractall(site_pkgs)
except Exception as e:
    print(f"  [ERROR] Wheel extraction failed: {e}")
    sys.exit(1)
finally:
    try:
        os.remove(whl_path)
    except OSError:
        pass

# Verify pip directory exists
pip_dir = os.path.join(site_pkgs, "pip")
if os.path.isdir(pip_dir):
    print(f"  pip package extracted OK ({len(os.listdir(pip_dir))} files)")
else:
    print(f"  [ERROR] pip/ directory not found in {site_pkgs}")
    print(f"  Contents: {os.listdir(site_pkgs)}")
    sys.exit(1)

# ── 5. Verify ─────────────────────────────────────────────────────────────
verify = subprocess.run(
    [sys.executable, "-m", "pip", "--version"],
    capture_output=True,
)
if verify.returncode != 0:
    print("  [ERROR] pip not working after wheel extraction")
    print("  stderr:", verify.stderr.decode(errors="replace"))
    # Debug again
    debug2 = subprocess.run(
        [sys.executable, "-c",
         "import sys; print('  sys.path:'); [print(f'    {p}') for p in sys.path]"],
        capture_output=True,
    )
    print(debug2.stdout.decode(errors="replace"), end="")
    sys.exit(1)

print(f"  pip OK: {verify.stdout.decode(errors='replace').strip()}")
