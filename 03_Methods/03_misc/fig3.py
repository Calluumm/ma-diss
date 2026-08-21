from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import pyproj
import shapefile
import tifffile

ROOT = Path(__file__).resolve().parents[2]
CLASS_MAP = ROOT / "02_Data" / "02_Processed" / "Sentinel2_Geomorphology_OTB" / "2021-05-02" / "2021-05-02_class_map.tif"
CATCHMENT_SHP = ROOT / "02_Data" / "01_Raw" / "Palanan-catchment-unextended.shp"
OUT = ROOT / "05_Figures" / "fig3.png"

CLASS_STYLE = {
    0: (240, 240, 240),  # unclassified/other
    1: (64, 130, 190),   # water
    2: (93, 156, 89),    # vegetation
    3: (201, 160, 93),   # bare sediment
    4: (170, 170, 170),  # cloud
    5: (214, 122, 63),   # channel sediment
}
CLASS_LABEL = {
    0: "Unclassified",
    1: "Water",
    2: "Vegetation",
    3: "Bare sediment",
    4: "Cloud",
    5: "Channel sediment",
}

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


def niceScaleLength(target_m: float) -> float:
    if target_m <= 0:
        return 1000.0
    exponent = math.floor(math.log10(target_m))
    base = 10 ** exponent
    for mult in (1, 2, 5, 10):
        length = mult * base
        if length >= target_m:
            return float(length)
    return float(10 * base)


def loadCatchmentRingsLonlat(path: Path) -> list[list[tuple[float, float]]]:
    if not path.exists():
        return []

    reader = shapefile.Reader(str(path))
    rings: list[list[tuple[float, float]]] = []
    for shp in reader.shapes():
        pts = shp.points
        parts = list(shp.parts) + [len(pts)]
        for i in range(len(parts) - 1):
            ring = [(float(x), float(y)) for x, y in pts[parts[i]:parts[i + 1]]]
            if len(ring) >= 3:
                rings.append(ring)

    if not rings:
        return []

    max_abs_x = max(abs(x) for ring in rings for x, _ in ring)
    max_abs_y = max(abs(y) for ring in rings for _, y in ring)
    if max_abs_x > 200.0 or max_abs_y > 100.0:
        transformer = pyproj.Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
        out: list[list[tuple[float, float]]] = []
        for ring in rings:
            converted = [transformer.transform(x, y) for x, y in ring]
            out.append([(float(x), float(y)) for x, y in converted])
        return out

    return rings


def drawCatchmentOutline(
    draw: ImageDraw.ImageDraw,
    rings_lonlat: list[list[tuple[float, float]]],
    lon0: float,
    lat0: float,
    px_deg_x: float,
    px_deg_y: float,
    scale: float,
    ox: int,
    oy: int,
) -> None:
    for ring in rings_lonlat:
        pts = []
        for lon, lat in ring:
            px = (lon - lon0) / px_deg_x
            py = (lat0 - lat) / px_deg_y
            x = ox + px * scale
            y = oy + py * scale
            pts.append((x, y))
        if len(pts) < 3:
            continue
        if pts[0] != pts[-1]:
            pts.append(pts[0])
        draw.line(pts, fill=(246, 244, 240), width=8)
        draw.line(pts, fill=(22, 22, 22), width=3)


arr = tifffile.imread(CLASS_MAP)
tf = tifffile.TiffFile(CLASS_MAP)
page = tf.pages[0]

px_scale = page.tags["ModelPixelScaleTag"].value
tie = page.tags["ModelTiepointTag"].value
px_deg_x = float(px_scale[0])
px_deg_y = float(px_scale[1])
lon0 = float(tie[3])
lat0 = float(tie[4])

h, w = arr.shape
lat_center = lat0 - (h * px_deg_y) / 2.0
m_per_deg_lon = 111320.0 * math.cos(math.radians(lat_center))
m_per_px_x = px_deg_x * m_per_deg_lon

rgba = np.zeros((h, w, 3), dtype=np.uint8)
for code, col in CLASS_STYLE.items():
    rgba[arr == code] = np.array(col, dtype=np.uint8)

map_img = Image.fromarray(rgba, mode="RGB")

page_w, page_h = 1750, 1550
panel = Image.new("RGB", (page_w, page_h), BG)
draw = ImageDraw.Draw(panel)
f_title = font(50, bold=True)
f_text = font(24)
f_small = font(21)

draw.text((58, 28), "Classified Sentinel-2 scene (2021-05-02)", fill=TEXT_DARK, font=f_title)

map_box = (30, 105, 1280, 1470)
mw = map_box[2] - map_box[0]
mh = map_box[3] - map_box[1]
scale = min(mw / w, mh / h)
dw, dh = int(w * scale), int(h * scale)
resized = map_img.resize((dw, dh), Image.NEAREST)
ox = map_box[0] + (mw - dw) // 2
oy = map_box[1] + (mh - dh) // 2

panel.paste(resized, (ox, oy))

catch_rings = loadCatchmentRingsLonlat(CATCHMENT_SHP)
drawCatchmentOutline(draw, catch_rings, lon0, lat0, px_deg_x, px_deg_y, scale, ox, oy)

nx, ny = ox + dw - 70, oy + dh - 260
draw.line((nx, ny + 120, nx, ny + 25), fill=(40, 40, 40), width=8)
draw.polygon([(nx, ny), (nx - 18, ny + 35), (nx + 18, ny + 35)], fill=(40, 40, 40))
draw.text((nx - 15, ny + 132), "N", fill=(40, 40, 40), font=font(30, bold=True))

bar_m = 10000.0
bar_px = max(60, int(bar_m / m_per_px_x * scale))
sx0 = ox + dw - bar_px - 70
sy0 = oy + dh - 64

draw.rounded_rectangle((sx0 - 14, sy0 - 24, sx0 + bar_px + 14, sy0 + 48), radius=6, fill=PANEL_BG, outline=(180, 173, 160), width=1)
half = bar_px // 2
draw.rectangle((sx0, sy0, sx0 + half, sy0 + 12), fill=(242, 242, 242), outline=(30, 30, 30), width=1)
draw.rectangle((sx0 + half, sy0, sx0 + bar_px, sy0 + 12), fill=(35, 35, 35), outline=(30, 30, 30), width=1)

f_scale = font(26, bold=True)
label = f"{int(bar_m):,} m" if bar_m < 1000 else f"{bar_m/1000:.1f} km"
draw.text((sx0, sy0 + 14), "0", fill=(35, 35, 35), font=f_scale)
draw.text((sx0 + bar_px, sy0 + 14), label, fill=(35, 35, 35), font=f_scale, anchor="ra")

leg = (1320, 250, 1690, 960)
draw.rounded_rectangle(leg, radius=14, fill=PANEL_BG, outline=PANEL_BORDER, width=2)
draw.text((leg[0] + 22, leg[1] + 16), "Legend", fill=TEXT_DARK, font=font(32, bold=True))

present = [int(v) for v in np.unique(arr)]
y = leg[1] + 78
for code in [1, 2, 3, 5, 4, 0]:
    if code not in present:
        continue
    col = CLASS_STYLE[code]
    draw.rectangle((leg[0] + 22, y, leg[0] + 62, y + 28), fill=col, outline=(90, 90, 90), width=1)
    draw.text((leg[0] + 74, y + 1), CLASS_LABEL[code], fill=TEXT_MID, font=f_text)
    y += 48

draw.line((leg[0] + 22, y + 12, leg[0] + 62, y + 12), fill=(246, 244, 240), width=8)
draw.line((leg[0] + 22, y + 12, leg[0] + 62, y + 12), fill=(22, 22, 22), width=3)
draw.text((leg[0] + 74, y), "Catchment boundary", fill=TEXT_MID, font=f_text)

lon_min = lon0
lon_max = lon0 + w * px_deg_x
lat_max = lat0
lat_min = lat0 - h * px_deg_y
draw.text((1320, 1010), "CRS: WGS 84 (EPSG:4326)", fill=TEXT_MID, font=f_small)
draw.text((1320, 1043), f"Extent: {lon_min:.3f} to {lon_max:.3f} E", fill=TEXT_MID, font=f_small)
draw.text((1320, 1076), f"        {lat_min:.3f} to {lat_max:.3f} N", fill=TEXT_MID, font=f_small)

draw.text(
    (40, 1470),
    "Map is an intermediate used in the classification workflow",
    fill=TEXT_MID,
    font=f_small,
)

OUT.parent.mkdir(parents=True, exist_ok=True)
panel.save(OUT, format="PNG")
print(f"wrote {OUT}")
