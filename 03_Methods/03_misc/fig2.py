from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "05_Figures" / "fig2.png"

BG = (245, 240, 230)
PANEL_BG = (252, 250, 245)
PANEL_BORDER = (217, 210, 196)
TEXT_DARK = (32, 36, 40)
TEXT_MID = (94, 88, 78)


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates.extend([
            Path("C:/Windows/Fonts/georgiab.ttf"),
            Path("C:/Windows/Fonts/segoeuib.ttf"),
            Path("C:/Windows/Fonts/arialbd.ttf"),
        ])
    candidates.extend([
        Path("C:/Windows/Fonts/georgia.ttf"),
        Path("C:/Windows/Fonts/trebuc.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ])
    for p in candidates:
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                continue
    return ImageFont.load_default()


w, h = 2300, 1250
img = Image.new("RGB", (w, h), BG)
draw = ImageDraw.Draw(img)

f_title = font(54, bold=True)
f_head = font(30, bold=True)
f_text = font(23)

draw.text((70, 40), "Methods workflow for Palanan geomorphic change analysis", fill=TEXT_DARK, font=f_title)

boxes = [
    (130, 170, 580, 360, "1. Data acquisition", "Sentinel-2 L2A bands\nCHIRPS daily rainfall\nCatchment and trunk corridor"),
    (660, 170, 1110, 360, "2. Scene classification", "Indices: NDVI, NDWI, MNDWI, BSI\nRule based class assignment\nClass map per date"),
    (1190, 170, 1640, 360, "3. Date pair changes", "Adjacent date differencing\nGain, loss, no-change"),
    (1720, 170, 2170, 360, "4. Classification Clips", "Strict catchment clip\nTrunk intersection\nMask filtering"),
    (400, 540, 1000, 760, "5. Change tables", "Per interval: gain, loss, total change\nConversion to m2\nInterval duration"),
    (1070, 540, 1670, 760, "6. Rainfall assessment", "Join CHIRPS by interval dates\nStatistical tests\nCorrections"),
    (855, 920, 1445, 1130, "7. Method outputs", "Class masks\nChange rasters\nValidation matrices\nRainfall change tables"),
]

for bx in boxes:
    x1, y1, x2, y2, title, body = bx
    draw.rounded_rectangle((x1, y1, x2, y2), radius=18, fill=PANEL_BG, outline=PANEL_BORDER, width=3)
    draw.text((x1 + 18, y1 + 14), title, fill=TEXT_DARK, font=f_head)
    draw.multiline_text((x1 + 18, y1 + 62), body, spacing=8, fill=TEXT_MID, font=f_text)

for x1, y1, x2, y2 in [(580, 265, 660, 265), (1110, 265, 1190, 265), (1640, 265, 1720, 265), (870, 360, 760, 540), (1780, 360, 1580, 540), (1000, 650, 1070, 650), (1370, 760, 1150, 920)]:
    draw.line((x1, y1, x2, y2), fill=(72, 72, 72), width=5)
    ang = math.atan2(y2 - y1, x2 - x1)
    ah = 18
    left = (x2 - ah * math.cos(ang - 0.5), y2 - ah * math.sin(ang - 0.5))
    right = (x2 - ah * math.cos(ang + 0.5), y2 - ah * math.sin(ang + 0.5))
    draw.polygon([(x2, y2), left, right], fill=(72, 72, 72))

OUT.parent.mkdir(parents=True, exist_ok=True)
img.save(OUT, format="PNG")
print(f"wrote {OUT}")
