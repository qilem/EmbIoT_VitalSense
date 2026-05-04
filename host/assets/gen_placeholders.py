"""
Run once to generate placeholder sprite PNGs for the four Vita states.
These are colored circles with a label — replace with real art for v2.

Usage:
    cd host/assets && python gen_placeholders.py
"""

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    raise SystemExit("pip install pillow")

SPRITES = {
    "vita_placeholder":  ("#a0c8f0", "?"),
    "vita_idle":         ("#a0f0b0", "idle"),
    "vita_concerned":    ("#f0e0a0", "stress"),
    "vita_alarmed":      ("#f0a0a0", "alert!"),
    "vita_calibration":  ("#c0a0f0", "aim~"),
    "tray_icon":         ("#50c878", "V"),
}

SIZE = 200

for name, (color, label) in SPRITES.items():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([10, 10, SIZE-10, SIZE-10], fill=color + "d0")
    draw.text((SIZE//2, SIZE//2), label, fill="#202020", anchor="mm")
    img.save(f"{name}.png")
    print(f"  {name}.png")

# Tray icon at 32x32
img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)
draw.ellipse([2, 2, 30, 30], fill="#50c878d0")
draw.text((16, 16), "V", fill="#ffffff", anchor="mm")
img.save("tray_icon.ico")
print("  tray_icon.ico")
print("Done.")
