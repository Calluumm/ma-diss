from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SUMMARY_CSV = ROOT / "04_Analysis" / "channelrainfallsum" / "channel_rainfall_summary_long.csv"
STATS_CSV = ROOT / "04_Analysis" / "channelrainfallsum" / "rainfall_change_stats.csv"
OUT_PNG = ROOT / "05_Figures" / "fig6.png"

MASKS = ("active_channel_mask", "channel_sediment_mask")
MASK_LABELS = {
    "active_channel_mask": "Active channel",
    "channel_sediment_mask": "Channel sediment",
}
MASK_COLORS = {
    "active_channel_mask": (23, 108, 121),
    "channel_sediment_mask": (122, 139, 58),
}


@dataclass
class Row:
    mask: str
    pre_date: str
    post_date: str
    rain_mm_interval: float
    gain_ha: float
    loss_ha: float
    net_change_ha: float
    change_ha: float


def read_rows(path: Path) -> list[Row]:
    rows: list[Row] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for rec in reader:
            mask = (rec.get("mask") or "").strip()
            if mask not in MASKS:
                continue
            rows.append(
                Row(
                    mask=mask,
                    pre_date=(rec.get("pre_date") or "").strip(),
                    post_date=(rec.get("post_date") or "").strip(),
                    rain_mm_interval=float(rec.get("rain_mm_interval") or 0.0),
                    gain_ha=float(rec.get("gain_area_ha") or 0.0),
                    loss_ha=float(rec.get("loss_area_ha") or 0.0),
                    net_change_ha=float(rec.get("net_change_area_ha") or 0.0),
                    change_ha=float(rec.get("change_area_ha") or 0.0),
                )
            )
    rows.sort(key=lambda r: datetime.strptime(r.post_date, "%Y-%m-%d"))
    return rows


def load_active_context_refs_ha(path: Path) -> tuple[float | None, float | None, float | None]:
    if not path.exists():
        return None, None, None
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for rec in reader:
            metric = (rec.get("metric") or "").strip().lower()
            if metric == "active channel mask total change (m2)":
                try:
                    med_long = float(rec.get("med_long") or "nan") / 10000.0
                    med_2023 = float(rec.get("med_2023") or "nan") / 10000.0
                    med_2025 = float(rec.get("med_2025") or "nan") / 10000.0
                except ValueError:
                    return None, None, None
                return med_long, med_2023, med_2025
    return None, None, None


def font(size: int, bold: bool = False):
    candidates = []
    if bold:
        candidates.extend(["C:/Windows/Fonts/cambriaz.ttf", "C:/Windows/Fonts/arialbd.ttf"])
    candidates.extend(["C:/Windows/Fonts/cambria.ttf", "C:/Windows/Fonts/arial.ttf"])
    for p in candidates:
        fp = Path(p)
        if fp.exists():
            try:
                return ImageFont.truetype(str(fp), size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def map_linear(v: float, vmin: float, vmax: float, out_min: float, out_max: float) -> float:
    if vmax == vmin:
        return (out_min + out_max) * 0.5
    t = (v - vmin) / (vmax - vmin)
    return out_min + t * (out_max - out_min)


def draw_axes(draw: ImageDraw.ImageDraw, left: int, top: int, right: int, bottom: int) -> None:
    draw.line((left, bottom, right, bottom), fill=(80, 80, 80), width=2)
    draw.line((left, top, left, bottom), fill=(80, 80, 80), width=2)


def draw_ticks_y(draw: ImageDraw.ImageDraw, left: int, top: int, bottom: int, ticks: list[tuple[float, str]], vmin: float, vmax: float, font_obj) -> None:
    if vmax == vmin:
        return
    lo = min(vmin, vmax)
    hi = max(vmin, vmax)
    for value, label in ticks:
        if value < lo or value > hi:
            continue
        y = map_linear(value, vmin, vmax, bottom, top)
        draw.line((left - 6, y, left, y), fill=(95, 95, 95), width=1)
        tb = draw.textbbox((0, 0), label, font=font_obj)
        tx = left - 10 - (tb[2] - tb[0])
        tx = max(8, tx)
        draw.text((tx, y - (tb[3] - tb[1]) / 2), label, fill=(88, 84, 76), font=font_obj)


def year_positions(left: int, right: int, years: list[str]) -> dict[str, float]:
    n = len(years)
    if n == 1:
        return {years[0]: (left + right) * 0.5}
    return {
        year: left + 35 + i * ((right - left - 70) / (n - 1))
        for i, year in enumerate(years)
    }


def draw_year_labels(draw: ImageDraw.ImageDraw, positions: dict[str, float], bottom: int, font_obj) -> None:
    for year, x in positions.items():
        tb = draw.textbbox((0, 0), year, font=font_obj)
        draw.text((x - (tb[2] - tb[0]) * 0.5, bottom + 8), year, fill=(88, 84, 76), font=font_obj)


def fmt_millions(value: float) -> str:
    if value <= 0:
        return "0"
    m = value / 1_000_000.0
    if abs(m - round(m)) < 1e-9:
        return f"{int(round(m))}M"
    return f"{m:.1f}M"


rows = read_rows(SUMMARY_CSV)
if not rows:
    raise RuntimeError("No long-series rows found")

active = [r for r in rows if r.mask == "active_channel_mask"]
if not active:
    raise RuntimeError("No active-channel rows found")

dates = [r.post_date for r in active]
n = len(dates)

rain_vals = [r.rain_mm_interval for r in active]
net_vals = [r.net_change_ha for r in rows]
change_vals = [r.change_ha * 10000.0 for r in rows]
med_long_ha, med_2023_ha, med_2025_ha = load_active_context_refs_ha(STATS_CSV)
if med_long_ha is None:
    med_long_ha = float(np.median([r.change_ha for r in active]))
med_2023_m2 = med_2023_ha * 10000.0 if med_2023_ha is not None else None
med_2025_m2 = med_2025_ha * 10000.0 if med_2025_ha is not None else None

w, h = 2500, 1560
canvas = Image.new("RGB", (w, h), (246, 243, 236))
draw = ImageDraw.Draw(canvas)

f_title = font(52, bold=True)
f_h = font(36, bold=True)
f_b = font(26)
f_s = font(22)

draw.text((60, 38), "Long-Term Geomorphic Trend Summary (2017-2026)", fill=(28, 28, 28), font=f_title)

a_left, a_top, a_right, a_bottom = 170, 190, 1210, 730
draw.rounded_rectangle((a_left - 90, a_top - 20, a_right + 20, a_bottom + 64), radius=18, fill=(252, 250, 245), outline=(215, 210, 200), width=2)
draw.text((a_left, a_top - 58), "A. Interval rainfall between scenes", fill=(35, 35, 35), font=f_h)
draw_axes(draw, a_left, a_top, a_right, a_bottom)

max_rain = max(rain_vals) * 1.08
col_w = (a_right - a_left - 50) / max(1, n)
years = [d[:4] for d in dates]
for i, row in enumerate(active):
    x0 = a_left + 25 + i * col_w
    x1 = x0 + col_w * 0.62
    y1 = a_bottom
    y0 = map_linear(row.rain_mm_interval, 0.0, max_rain, a_bottom, a_top + 20)
    draw.rectangle((x0, y0, x1, y1), fill=(73, 130, 180), outline=(60, 102, 140))

    yr = row.post_date[:4]
    tb = draw.textbbox((0, 0), yr, font=f_s)
    tw = tb[2] - tb[0]
    draw.text((x0 + (x1 - x0 - tw) * 0.5, a_bottom + 8), yr, fill=(88, 84, 76), font=f_s)

rain_ticks = [0, 1000, 2000, 3000, 4000, 5000]
draw_ticks_y(
    draw,
    a_left,
    a_top,
    a_bottom,
    [(float(t), str(t)) for t in rain_ticks if t <= max_rain],
    0.0,
    max_rain,
    f_s,
)

draw.text((a_left, a_bottom + 30), "Post-scene year", fill=(70, 68, 62), font=f_s)
rainfall_label = Image.new("RGBA", (180, 34), (255, 255, 255, 0))
rainfall_draw = ImageDraw.Draw(rainfall_label)
rainfall_draw.text((0, 0), "Rainfall (mm)", fill=(60, 90, 120), font=f_s)
rainfall_label = rainfall_label.rotate(90, expand=True)
draw.bitmap((a_left - 90, a_top + 145), rainfall_label, fill=(60, 90, 120))

b_left, b_top, b_right, b_bottom = 1360, 190, 2410, 730
draw.rounded_rectangle((b_left - 80, b_top - 20, b_right + 20, b_bottom + 64), radius=18, fill=(252, 250, 245), outline=(215, 210, 200), width=2)
draw.text((b_left, b_top - 58), "B. Total mapped change (log10 scale)", fill=(35, 35, 35), font=f_h)
draw_axes(draw, b_left, b_top, b_right, b_bottom)

xpos_b = year_positions(b_left, b_right, years)

log_vals = [math.log10(v + 1.0) for v in change_vals]
lg_min = math.log10(100000.0)
lg_max = max(log_vals) * 1.06

for mask in MASKS:
    series = [r for r in rows if r.mask == mask]
    pts = []
    clipped_low = []
    for r in series:
        year = r.post_date[:4]
        x = xpos_b[year]
        clamped_m2 = max(0.0, r.change_ha * 10000.0)
        yv = math.log10(clamped_m2 + 1.0)
        y = map_linear(yv, lg_min, lg_max, b_bottom, b_top)
        pts.append((x, y))
        if r.change_ha * 10000.0 <= 0.0:
            clipped_low.append((x, b_bottom))
    if len(pts) > 1:
        draw.line(pts, fill=MASK_COLORS[mask], width=4)
    for x, y in pts:
        draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=MASK_COLORS[mask], outline=(255, 255, 255), width=1)
    for x, y in clipped_low:
        draw.polygon([(x, y + 2), (x - 6, y + 12), (x + 6, y + 12)], fill=MASK_COLORS[mask])

draw_year_labels(draw, xpos_b, b_bottom, f_s)

tick_values = [100000, 250000, 500000, 1000000, 2500000, 5000000, 10000000, 25000000]
b_ticks = []
for tv in tick_values:
    lv = math.log10(tv + 1.0)
    if lv <= lg_max:
        b_ticks.append((lv, f"{tv / 1000000:.1f}" if tv >= 1000000 else f"{tv / 1000000:.2f}"))
draw_ticks_y(draw, b_left, b_top, b_bottom, b_ticks, lg_min, lg_max, f_s)

lx, ly = b_right - 210, b_top + 68
for mask in MASKS:
    draw.rectangle((lx, ly, lx + 22, ly + 16), fill=MASK_COLORS[mask], outline=(255, 255, 255))
    draw.text((lx + 32, ly - 3), MASK_LABELS[mask], fill=(55, 55, 55), font=f_s)
    ly += 28

ylabel = Image.new("RGBA", (300, 34), (255, 255, 255, 0))
ylabel_draw = ImageDraw.Draw(ylabel)
ylabel_draw.text((0, 0), "Total mapped change (km2)", fill=(70, 68, 62), font=f_s)
ylabel = ylabel.rotate(90, expand=True)
draw.bitmap((b_left - 82, b_top + 110), ylabel, fill=(70, 68, 62))

draw.text((b_left, b_bottom + 30), "Post-scene year", fill=(70, 68, 62), font=f_s)

c_left, c_top, c_right, c_bottom = 120, 870, 1210, 1450
draw.rounded_rectangle((c_left - 40, c_top - 20, c_right + 20, c_bottom + 64), radius=18, fill=(252, 250, 245), outline=(215, 210, 200), width=2)
draw.text((c_left, c_top - 58), "C. Directional balance index", fill=(35, 35, 35), font=f_h)
draw_axes(draw, c_left, c_top, c_right, c_bottom)

xpos_c = year_positions(c_left, c_right, years)
bi_min, bi_max = -1.0, 1.0
c_zero = map_linear(0.0, bi_min, bi_max, c_bottom, c_top)
draw.line((c_left, c_zero, c_right, c_zero), fill=(140, 140, 140), width=1)

for mask in MASKS:
    series = [r for r in rows if r.mask == mask]
    pts = []
    for r in series:
        year = r.post_date[:4]
        x = xpos_c[year]
        denom = r.gain_ha + r.loss_ha
        balance = 0.0 if denom <= 0 else (r.gain_ha - r.loss_ha) / denom
        y = map_linear(balance, bi_min, bi_max, c_bottom, c_top)
        pts.append((x, y))
    if len(pts) > 1:
        draw.line(pts, fill=MASK_COLORS[mask], width=4)
    for x, y in pts:
        draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=MASK_COLORS[mask], outline=(255, 255, 255), width=1)

draw_year_labels(draw, xpos_c, c_bottom, f_s)
draw_ticks_y(
    draw,
    c_left,
    c_top,
    c_bottom,
    [(-1.0, "-1.0"), (-0.5, "-0.5"), (0.0, "0"), (0.5, "0.5"), (1.0, "1.0")],
    bi_min,
    bi_max,
    f_s,
)
draw.text((c_right - 360, c_top + 8), "(gain-loss)/(gain+loss)", fill=(92, 88, 78), font=f_s)
draw.text((c_right - 360, c_top + 34), "+1 gain, 0 balanced, -1 loss", fill=(92, 88, 78), font=f_s)

draw.text((c_left, c_bottom + 30), "Post-scene year", fill=(70, 68, 62), font=f_s)

d_left, d_top, d_right, d_bottom = 1360, 870, 2410, 1450
draw.rounded_rectangle((d_left - 80, d_top - 20, d_right + 20, d_bottom + 64), radius=18, fill=(252, 250, 245), outline=(215, 210, 200), width=2)
draw.text((d_left, d_top - 58), "D. 2023 and 2025 in long-context envelope", fill=(35, 35, 35), font=f_h)

d_series = [r for r in rows if r.mask == "active_channel_mask"]
d_vals = [r.change_ha * 10000.0 for r in d_series]
if not d_vals:
    raise RuntimeError("No active-channel total-change values for Panel D")

year_to_val: dict[str, float] = {}
for r in d_series:
    year_to_val[r.post_date[:4]] = r.change_ha * 10000.0

v_min = float(np.min(d_vals))
v_q1 = float(np.percentile(d_vals, 25))
v_med = float(np.percentile(d_vals, 50))
v_q3 = float(np.percentile(d_vals, 75))
v_max = float(np.max(d_vals))

lg_min = math.log10(max(1.0, v_min) + 1.0)
lg_max = math.log10(v_max + 1.0)

def map_context_x(value_m2: float) -> float:
    return map_linear(math.log10(max(1.0, value_m2) + 1.0), lg_min, lg_max, track_left, track_right)

track_left = d_left + 170
track_right = d_right - 80
row1_y = d_top + 200
row2_y = d_top + 390
row_h = 34

def draw_focus_row(row_y: int, year_label: str, value_m2: float | None, col: tuple[int, int, int]) -> None:
    x_min = map_context_x(v_min)
    x_q1 = map_context_x(v_q1)
    x_med = map_context_x(v_med)
    x_q3 = map_context_x(v_q3)
    x_max = map_context_x(v_max)

    draw.line((x_min, row_y, x_max, row_y), fill=(170, 165, 154), width=3)
    draw.rectangle((x_q1, row_y - row_h // 2, x_q3, row_y + row_h // 2), fill=(224, 218, 205), outline=(178, 170, 154), width=1)
    draw.line((x_med, row_y - row_h // 2 - 6, x_med, row_y + row_h // 2 + 6), fill=(130, 122, 108), width=2)

    draw.text((d_left + 12, row_y - 18), year_label, fill=(55, 55, 55), font=f_h)

    if value_m2 is None:
        draw.text((track_left, row_y + 28), "No value", fill=(110, 104, 92), font=f_s)
        return

    x_val = map_context_x(value_m2)
    draw.line((x_val, row_y - 46, x_val, row_y + 46), fill=col, width=3)
    draw.ellipse((x_val - 9, row_y - 9, x_val + 9, row_y + 9), fill=col, outline=(255, 255, 255), width=1)

    pct = 100.0 * sum(1 for v in d_vals if v <= value_m2) / len(d_vals)
    label = f"{fmt_millions(value_m2)} m2 ({pct:.0f}th pct)"
    tb = draw.textbbox((0, 0), label, font=f_s)
    lx = min(max(track_left, x_val - (tb[2] - tb[0]) / 2), track_right - (tb[2] - tb[0]))
    draw.rounded_rectangle((lx - 8, row_y - 72, lx + (tb[2] - tb[0]) + 8, row_y - 42), radius=7, fill=(248, 244, 236), outline=(213, 206, 192), width=1)
    draw.text((lx, row_y - 67), label, fill=(68, 64, 56), font=f_s)

draw_focus_row(row1_y, "2023", year_to_val.get("2023"), (176, 118, 56))
draw_focus_row(row2_y, "2025", year_to_val.get("2025"), (95, 95, 95))

draw.text((track_left, d_bottom - 97), "Lower change", fill=(92, 88, 78), font=f_s)
t_hi = "Higher change"
t_hi_box = draw.textbbox((0, 0), t_hi, font=f_s)
draw.text((track_right - (t_hi_box[2] - t_hi_box[0]), d_bottom - 97), t_hi, fill=(92, 88, 78), font=f_s)

ctx_x, ctx_y = d_right - 405, d_top + 26
draw.rounded_rectangle((ctx_x, ctx_y, ctx_x + 395, ctx_y + 96), radius=8, fill=(248, 244, 236), outline=(213, 206, 192), width=1)
draw.text((ctx_x + 10, ctx_y + 8), "Context (all years, active channel)", fill=(80, 70, 60), font=f_s)
draw.text((ctx_x + 10, ctx_y + 34), f"Min {fmt_millions(v_min)}   Median {fmt_millions(v_med)}", fill=(96, 90, 78), font=f_s)
draw.text((ctx_x + 10, ctx_y + 58), f"Q1 {fmt_millions(v_q1)}   Q3 {fmt_millions(v_q3)}   Max {fmt_millions(v_max)}", fill=(96, 90, 78), font=f_s)

OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
canvas.save(OUT_PNG, format="PNG")
print(f"wrote {OUT_PNG}")

