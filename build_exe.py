"""Create app icon and build .exe."""

import os
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
ICON_FILE = PROJECT_DIR / "assets" / "marketlens_logo.ico"

# 1. Create icon using PIL (optional)
print("1. Creating icon...")
try:
    from PIL import Image, ImageDraw, ImageFont

    size = 256
    img = Image.new("RGBA", (size, size), (30, 30, 30, 255))
    draw = ImageDraw.Draw(img)

    # Cart body
    draw.rectangle([60, 100, 200, 160], fill=(0, 150, 255, 255))
    # Cart handle
    draw.arc([40, 70, 100, 110], 180, 0, fill=(0, 150, 255, 255), width=8)
    # Cart wheels
    draw.ellipse([80, 165, 110, 195], fill=(255, 255, 255, 255))
    draw.ellipse([160, 165, 190, 195], fill=(255, 255, 255, 255))
    # Arrow up (growth)
    draw.polygon([(120, 120), (140, 90), (160, 120)], fill=(255, 200, 0, 255))
    draw.rectangle([132, 120, 148, 155], fill=(255, 200, 0, 255))

    # Text
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont  # type: ignore[assignment]
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except Exception:
        font = ImageFont.load_default()
    draw.text((50, 200), "AI AMAZON", fill=(255, 255, 255, 255), font=font)

    ico_path = PROJECT_DIR / "icon.ico"
    img.save(str(ico_path), format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print(f"   Icon created: {ico_path}")
except Exception as e:
    print(f"   Icon creation skipped: {e}")

# 2. Build .exe using the spec file
print("\n2. Building .exe via MarketLens.spec...")
spec_file = PROJECT_DIR / "MarketLens.spec"

if not spec_file.exists():
    print(f"   ERROR: {spec_file} not found")
    sys.exit(1)

# Prefer venv312 (Python 3.12) since PyInstaller 6.x doesn't support Python 3.14
venv312_python = PROJECT_DIR / "venv312" / "Scripts" / "python.exe"
if venv312_python.exists():
    build_python = str(venv312_python)
    print(f"   Using Python 3.12: {build_python}")
else:
    build_python = sys.executable
    print(f"   Using: {build_python}")

cmd = [
    build_python, "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    str(spec_file),
]

print(f"   Running: {' '.join(cmd)}")
print("   This may take 2-5 minutes...\n")

result = subprocess.run(cmd, cwd=str(PROJECT_DIR))

if result.returncode == 0:
    exe_path = PROJECT_DIR / "dist" / "MarketLens" / "MarketLens.exe"
    print(f"\n3. Build complete!")
    print(f"   .exe location: {exe_path}")
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"   Size: {size_mb:.1f} MB")
else:
    print(f"\n3. Build FAILED with exit code {result.returncode}")
    sys.exit(result.returncode)
