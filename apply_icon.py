"""Convert uploaded icon to .ico and apply to app."""

import os

from PIL import Image, ImageDraw, ImageFont

# Paths
PROJECT_DIR = r"C:\Users\royde\Documents\Codex\AI Amazon\amazon-product-ai"
ICON_PNG = os.path.join(PROJECT_DIR, "icon.png")
ICON_ICO = os.path.join(PROJECT_DIR, "icon.ico")
EXE_PATH = os.path.join(PROJECT_DIR, "dist", "AmazonProductAI.exe")
SHORTCUT_PATH = r"C:\Users\royde\Desktop\Amazon Product AI.lnk"

print("=" * 50)
print("SETTING UP APP ICON")
print("=" * 50)

img: Image.Image
# Check if user saved the image
if os.path.exists(ICON_PNG):
    print("\n[1] Found icon.png - converting to .ico...")
    img = Image.open(ICON_PNG)

    # Convert to RGBA if needed
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    # Resize to standard icon sizes
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save(ICON_ICO, format="ICO", sizes=sizes)
    print(f"    Saved: {ICON_ICO}")
else:
    print("\n[1] icon.png not found - creating icon from scratch...")

    # Create a nice icon programmatically
    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background circle
    draw.ellipse([20, 20, size-20, size-20], fill=(20, 25, 35, 255))

    # Circuit board pattern (golden)
    for i in range(8):
        x = 80 + i * 50
        draw.line([(x, 100), (x, 200)], fill=(255, 180, 0, 200), width=3)
        draw.ellipse([x-5, 195, x+5, 205], fill=(255, 180, 0, 200))

    # Robot head
    draw.rounded_rectangle([150, 180, 362, 380], radius=40, fill=(220, 220, 220, 255))

    # Robot eyes (orange)
    draw.ellipse([200, 260, 240, 300], fill=(255, 140, 0, 255))
    draw.ellipse([280, 260, 320, 300], fill=(255, 140, 0, 255))

    # Robot smile
    draw.arc([220, 290, 300, 350], 0, 180, fill=(255, 140, 0, 255), width=4)

    # Headband
    draw.rectangle([150, 210, 362, 240], fill=(255, 140, 0, 255))

    # Antenna
    draw.line([(256, 180), (256, 140)], fill=(255, 140, 0, 255), width=6)
    draw.ellipse([246, 125, 266, 145], fill=(255, 200, 0, 255))

    # Cloud with AI text
    draw.ellipse([320, 160, 430, 230], fill=(0, 150, 255, 255))
    draw.ellipse([350, 140, 400, 170], fill=(0, 150, 255, 255))
    draw.ellipse([380, 155, 420, 185], fill=(0, 150, 255, 255))

    # AI text
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont  # type: ignore[assignment]
    try:
        font = ImageFont.truetype("arial.ttf", 32)
    except Exception:
        font = ImageFont.load_default()
    draw.text((355, 170), "AI", fill=(255, 255, 255, 255), font=font)

    # Amazon smile arrow
    draw.arc([150, 350, 362, 450], 10, 170, fill=(255, 150, 0, 255), width=12)
    draw.polygon([(340, 390), (370, 380), (350, 410)], fill=(255, 150, 0, 255))

    # Growth chart
    draw.line([(370, 200), (390, 180), (410, 190), (440, 150)], fill=(255, 255, 255, 255), width=4)

    # Light bulb
    draw.ellipse([80, 120, 130, 170], fill=(255, 220, 0, 255))
    draw.rectangle([95, 165, 115, 185], fill=(200, 200, 200, 255))
    for angle in range(0, 360, 45):
        import math
        x1 = 105 + int(30 * math.cos(math.radians(angle)))
        y1 = 145 + int(30 * math.sin(math.radians(angle)))
        draw.line([(105, 145), (x1, y1)], fill=(255, 220, 0, 150), width=2)

    # Save as ICO
    img.save(ICON_ICO, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    # Also save as PNG for reference
    img.save(os.path.join(PROJECT_DIR, "icon.png"))
    print(f"    Saved: {ICON_ICO}")

# Update desktop shortcut
print("\n[2] Updating desktop shortcut...")
try:
    import win32com.client
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(SHORTCUT_PATH)
    shortcut.TargetPath = EXE_PATH
    shortcut.WorkingDirectory = os.path.dirname(EXE_PATH)
    shortcut.IconLocation = f"{ICON_ICO},0"
    shortcut.Description = "AI-Powered Amazon Product Idea Generator"
    shortcut.Save()
    print(f"    Updated: {SHORTCUT_PATH}")
except Exception as e:
    print(f"    Error: {e}")
    # Fallback: create shortcut via PowerShell
    ps_cmd = f'''
    $WshShell = New-Object -comObject WScript.Shell
    $Shortcut = $WshShell.CreateShortCut("{SHORTCUT_PATH}")
    $Shortcut.TargetPath = "{EXE_PATH}"
    $Shortcut.WorkingDirectory = "{os.path.dirname(EXE_PATH)}"
    $Shortcut.IconLocation = "{ICON_ICO},0"
    $Shortcut.Description = "AI-Powered Amazon Product Idea Generator"
    $Shortcut.Save()
    '''
    os.system('powershell -Command "{}"'.format(ps_cmd.replace('"', '\\"')))
    print(f"    Updated via PowerShell: {SHORTCUT_PATH}")

# Rebuild .exe with icon
print("\n[3] Rebuilding .exe with icon...")
os.chdir(PROJECT_DIR)
build_cmd = f'py -m PyInstaller --onefile --windowed --name "AmazonProductAI" --icon="{ICON_ICO}" run_gui.py --noconfirm'
os.system(build_cmd)

print("\n" + "=" * 50)
print("DONE!")
print("=" * 50)
print(f"\nIcon: {ICON_ICO}")
print(f"Shortcut: {SHORTCUT_PATH}")
print(f"EXE: {EXE_PATH}")
print("\nDouble-click the desktop icon to launch!")
