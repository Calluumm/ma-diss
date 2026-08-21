from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import tifffile


ROOT = Path(__file__).resolve().parents[2]
SUMMARY_CSV = ROOT / "04_Analysis" / "channelrainfallsum" / "channel_rainfall_summary_all.csv"
STATS_CSV = ROOT / "04_Analysis" / "channelrainfallsum" / "rainfall_change_stats.csv"
OUT_PNG = ROOT / "05_Figures" / "fig7.png"
OUT_SUPPLEMENTARY_PNG = ROOT / "05_Figures" / "suppl_bidirectional.png"

GEOM_ROOTS = {
    "2023": ROOT / "02_Data" / "02_Processed" / "Sentinel2_Geomorphology_OTB_2023",
    "2025": ROOT / "02_Data" / "02_Processed" / "Sentinel2_Geomorphology_OTB_2025",
    "long_series": ROOT / "02_Data" / "02_Processed" / "Sentinel2_Geomorphology_OTB",
}

TARGET_MASKS = ("active_channel_mask", "channel_sediment_mask")
MASK_LABEL = {
    "active_channel_mask": "Active channel",
    "channel_sediment_mask": "Channel sediment",
}
MASK_COLOR = {
    "active_channel_mask": (35, 122, 174),
    "channel_sediment_mask": (218, 127, 40),
}

SERIES_ORDER = ("2023", "2025", "long_series")
SERIES_LABEL = {
    "2023": "2023 context",
    "2025": "2025 context",
    "long_series": "Long context",
}

BG = (245, 240, 230)
PANEL_BG = (252, 250, 245)
PANEL_BORDER = (217, 210, 196)
TEXT_DARK = (32, 36, 40)
TEXT_MID = (94, 88, 78)
GRID = (224, 219, 208)


@dataclass
class Record:
    series_id: str
    mask: str
    pre_date: datetime
    post_date: datetime
    rain_mm_interval: float
    interval_days: float
    gain_m2: float
    loss_m2: float
    change_m2: float


@dataclass
class Rect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top



def to_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")



def parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")



def load_records(path: Path) -> list[Record]:
    rows: list[Record] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            mask = row.get("mask", "")
            if mask not in TARGET_MASKS:
                continue
            rows.append(
                Record(
                    series_id=row.get("series_id", ""),
                    mask=mask,
                    pre_date=parse_date(row["pre_date"]),
                    post_date=parse_date(row["post_date"]),
                    rain_mm_interval=to_float(row.get("rain_mm_interval", "nan")),
                    interval_days=to_float(row.get("interval_days", "nan")),
                    gain_m2=to_float(row.get("gain_area_m2", "nan")),
                    loss_m2=to_float(row.get("loss_area_m2", "nan")),
                    change_m2=to_float(row.get("change_area_m2", "nan")),
                )
            )
    rows.sort(key=lambda rec: (rec.series_id, rec.pre_date, rec.mask))
    return rows



def choose_area_unit(records: list[Record]) -> tuple[float, str]:
    values = []
    for rec in records:
        values.extend([abs(rec.gain_m2), abs(rec.loss_m2), abs(rec.change_m2)])
    if not values:
        return 1.0, "m2"
    return (1_000_000.0, "km2") if np.nanmedian(values) >= 2_000_000.0 else (1.0, "m2")



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
    for candidate in candidates:
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size)
            except Exception:
                continue
    return ImageFont.load_default()



def draw_panel_box(draw: ImageDraw.ImageDraw, rect: Rect) -> None:
    draw.rounded_rectangle((rect.left, rect.top, rect.right, rect.bottom), radius=18, fill=PANEL_BG, outline=PANEL_BORDER, width=2)



def map_linear(value: float, vmin: float, vmax: float, out_min: float, out_max: float) -> float:
    if vmax <= vmin:
        return (out_min + out_max) / 2.0
    t = (value - vmin) / (vmax - vmin)
    return out_min + t * (out_max - out_min)



def draw_grid(draw: ImageDraw.ImageDraw, plot: Rect, rows: int = 4) -> None:
    for i in range(rows + 1):
        y = int(plot.top + i * (plot.height / rows))
        draw.line((plot.left, y, plot.right, y), fill=GRID, width=1)



def permutation_pvalue_mean_diff(a: np.ndarray, b: np.ndarray, n_perm: int = 12000, seed: int = 7) -> float:
    rng = np.random.default_rng(seed)
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if a.size < 2 or b.size < 2:
        return float("nan")
    obs = float(np.mean(b) - np.mean(a))
    pool = np.concatenate([a, b])
    na = a.size
    count = 0
    for _ in range(n_perm):
        rng.shuffle(pool)
        d = float(np.mean(pool[na:]) - np.mean(pool[:na]))
        if abs(d) >= abs(obs):
            count += 1
    return float((count + 1) / (n_perm + 1))


def cliffs_delta(a: np.ndarray, b: np.ndarray) -> float:
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if a.size == 0 or b.size == 0:
        return float("nan")
    gt = np.sum(b[:, None] > a[None, :])
    lt = np.sum(b[:, None] < a[None, :])
    return float((gt - lt) / (a.size * b.size))


def benjamini_hochberg(pvals: list[float]) -> list[float]:
    m = len(pvals)
    qvals = [float("nan")] * m
    order = sorted(range(m), key=lambda i: pvals[i])
    ranked = [pvals[i] for i in order]

    adj = [0.0] * m
    prev = 1.0
    for i in range(m - 1, -1, -1):
        rank = i + 1
        value = min(prev, (ranked[i] * m) / rank)
        prev = value
        adj[i] = value

    for i, idx in enumerate(order):
        qvals[idx] = float(min(1.0, max(0.0, adj[i])))
    return qvals


def direction_label(value: float, tol: float = 0.03) -> str:
    if not np.isfinite(value):
        return "na"
    if value > 1.0 + tol:
        return "higher"
    if value < 1.0 - tol:
        return "lower"
    return "near"


def water_coverage_percent(mask_path: Path) -> float:
    arr = tifffile.imread(mask_path)
    valid = arr != 255
    n_valid = int(np.count_nonzero(valid))
    if n_valid == 0:
        return float("nan")
    n_water = int(np.count_nonzero(arr[valid] == 1))
    return (100.0 * n_water) / n_valid


def load_stats_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            parsed: dict[str, object] = {}
            for key, value in row.items():
                if key in {"metric", "tag"}:
                    parsed[key] = value
                else:
                    try:
                        parsed[key] = float(value) if value not in {None, ""} else float("nan")
                    except ValueError:
                        parsed[key] = value
            rows.append(parsed)
    return rows



def series_records(records: list[Record], series_id: str) -> list[Record]:
    return [r for r in records if r.series_id == series_id]



def panel_b_bidirectional_by_context(
    draw: ImageDraw.ImageDraw,
    panel: Rect,
    records: list[Record],
    area_factor: float,
    area_unit: str,
    f_title,
    f_text,
    f_small,
) -> None:
    draw_panel_box(draw, panel)
    draw.text((panel.left + 16, panel.top + 12), "B. Bidirectional response by context (gain up, loss down)", fill=TEXT_DARK, font=f_title)

    all_amp = []
    for rec in records:
        all_amp.append(max(rec.gain_m2, rec.loss_m2) / area_factor)
    asinh_scale = max(20.0, float(np.nanpercentile(np.array(all_amp, dtype=float), 75)))

    def t(value: float) -> float:
        return float(np.sign(value) * np.arcsinh(abs(value) / asinh_scale))

    tmax = max(0.2, float(np.nanmax(np.abs(np.array([t(v) for v in all_amp], dtype=float))))) * 1.08
    x_min = float(np.nanmin(np.array([r.rain_mm_interval for r in records], dtype=float)))
    x_max = float(np.nanmax(np.array([r.rain_mm_interval for r in records], dtype=float)))

    col_gap = 18
    usable_w = panel.width - 60
    col_w = (usable_w - 2 * col_gap) // 3

    for idx, series_id in enumerate(SERIES_ORDER):
        sub = Rect(
            panel.left + 24 + idx * (col_w + col_gap),
            panel.top + 54,
            panel.left + 24 + idx * (col_w + col_gap) + col_w,
            panel.bottom - 48,
        )
        draw.rectangle((sub.left, sub.top, sub.right, sub.bottom), outline=(168, 161, 149), width=2)
        draw_grid(draw, sub, rows=6)

        y_zero = int(map_linear(0.0, -tmax, tmax, sub.bottom - 2, sub.top + 2))
        draw.line((sub.left, y_zero, sub.right, y_zero), fill=(33, 33, 33), width=2)

        s_rows = series_records(records, series_id)
        for rec in s_rows:
            base_x = map_linear(rec.rain_mm_interval, x_min, x_max, sub.left + 10, sub.right - 10)
            jitter = -8.0 if rec.mask == "active_channel_mask" else 8.0
            x = int(base_x + jitter)

            gain_u = rec.gain_m2 / area_factor
            loss_u = rec.loss_m2 / area_factor
            y_gain = int(map_linear(t(gain_u), -tmax, tmax, sub.bottom - 2, sub.top + 2))
            y_loss = int(map_linear(t(-loss_u), -tmax, tmax, sub.bottom - 2, sub.top + 2))

            color = MASK_COLOR[rec.mask]
            draw.line((x, y_gain, x, y_loss), fill=color, width=2)
            draw.ellipse((x - 3, y_gain - 3, x + 3, y_gain + 3), fill=color)
            draw.ellipse((x - 3, y_loss - 3, x + 3, y_loss + 3), fill=color)

        title = f"{SERIES_LABEL.get(series_id, series_id)} (n={len(s_rows)//2})"
        draw.text((sub.left + 8, sub.top + 8), title, fill=TEXT_MID, font=f_small)
        draw.text((sub.right - 98, sub.bottom + 8), "rainfall (mm)", fill=TEXT_MID, font=f_small)

        for k in range(4):
            xv = x_min + (x_max - x_min) * (k / 3)
            x = int(map_linear(xv, x_min, x_max, sub.left + 10, sub.right - 10))
            draw.line((x, sub.bottom, x, sub.bottom + 4), fill=(120, 114, 104), width=1)
            draw.text((x - 12, sub.bottom + 6), f"{xv:.0f}", fill=TEXT_MID, font=f_small)

    draw.text((panel.left + 14, panel.top + 42), f"signed asinh scale ({area_unit})", fill=TEXT_MID, font=f_small)

    lx = panel.right - 310
    ly = panel.top + 16
    draw.rounded_rectangle((lx, ly, lx + 275, ly + 52), radius=8, fill=(248, 245, 238), outline=(208, 201, 188), width=1)
    draw.ellipse((lx + 12, ly + 10, lx + 22, ly + 20), fill=MASK_COLOR["active_channel_mask"])
    draw.text((lx + 30, ly + 8), MASK_LABEL["active_channel_mask"], fill=TEXT_DARK, font=f_small)
    draw.ellipse((lx + 12, ly + 30, lx + 22, ly + 40), fill=MASK_COLOR["channel_sediment_mask"])
    draw.text((lx + 30, ly + 28), MASK_LABEL["channel_sediment_mask"], fill=TEXT_DARK, font=f_small)



def panel_c_medians_by_context(
    draw: ImageDraw.ImageDraw,
    panel: Rect,
    records: list[Record],
    area_factor: float,
    area_unit: str,
    f_title,
    f_text,
    f_small,
) -> None:
    draw_panel_box(draw, panel)
    draw.text((panel.left + 16, panel.top + 12), "Median gain and loss by context", fill=TEXT_DARK, font=f_title)

    stats = []
    max_abs = 1.0
    for series_id in SERIES_ORDER:
        s_rows = series_records(records, series_id)
        for mask in TARGET_MASKS:
            rows = [r for r in s_rows if r.mask == mask]
            if not rows:
                continue
            gain = float(np.nanmedian(np.array([r.gain_m2 for r in rows], dtype=float)) / area_factor)
            loss = float(np.nanmedian(np.array([r.loss_m2 for r in rows], dtype=float)) / area_factor)
            stats.append((series_id, mask, len(rows), gain, loss))
            max_abs = max(max_abs, abs(gain), abs(loss))

    plot = Rect(panel.left + 220, panel.top + 56, panel.right - 30, panel.bottom - 34)
    draw_grid(draw, plot, rows=3)
    draw.rectangle((plot.left, plot.top, plot.right, plot.bottom), outline=(168, 161, 149), width=2)

    x_lim = max_abs * 1.35
    raw_step = (2 * x_lim) / 6
    magnitude = 10 ** int(np.floor(np.log10(raw_step)))
    step_options = [1, 2, 5, 10]
    step = next((candidate * magnitude for candidate in step_options if raw_step <= candidate * magnitude), 10 * magnitude)
    x_lim = 1000000
    x0 = int(map_linear(0.0, -x_lim, x_lim, plot.left + 4, plot.right - 4))
    draw.line((x0, plot.top, x0, plot.bottom), fill=(32, 32, 32), width=2)

    for i, sid in enumerate(SERIES_ORDER):
        y_center = int(map_linear(i, 0, 2, plot.top + 40, plot.bottom - 40))
        draw.text((panel.left + 18, y_center - 8), SERIES_LABEL.get(sid, sid), fill=TEXT_MID, font=f_text)

    bar_h = 16
    for sid, mask, n, gain, loss in stats:
        i = SERIES_ORDER.index(sid)
        y_center = int(map_linear(i, 0, 2, plot.top + 40, plot.bottom - 40))
        y = y_center - 10 if mask == "active_channel_mask" else y_center + 10

        color = MASK_COLOR[mask]
        x_gain = int(map_linear(gain, -x_lim, x_lim, plot.left + 4, plot.right - 4))
        x_loss = int(map_linear(-loss, -x_lim, x_lim, plot.left + 4, plot.right - 4))

        draw.rectangle((min(x0, x_gain), y - bar_h // 2, max(x0, x_gain), y + bar_h // 2), fill=color)
        draw.rectangle((min(x0, x_loss), y - bar_h // 2, max(x0, x_loss), y + bar_h // 2), fill=(color[0], color[1], color[2], 150))

        draw.text((plot.right - 260, y - 8), f"{MASK_LABEL[mask]} | n={n}", fill=TEXT_MID, font=f_small)

    for xv in [-1000000, -750000, -500000, -250000, 0, 250000, 500000, 750000, 1000000]:
        x = int(map_linear(xv, -x_lim, x_lim, plot.left + 4, plot.right - 4))
        draw.line((x, plot.bottom, x, plot.bottom + 5), fill=(120, 114, 104), width=1)
        draw.text((x, plot.bottom + 7), f"{xv:,.0f}", fill=TEXT_MID, font=f_small, anchor="ma")



def panel_d_comparison_table(
    draw: ImageDraw.ImageDraw,
    panel: Rect,
    f_title,
    f_text,
    f_small,
) -> None:
    draw_panel_box(draw, panel)
    draw.text((panel.left + 16, panel.top + 12), "D. Mechanism test: event-year pulse vs long-interval accumulation", fill=TEXT_DARK, font=f_title)

    if not STATS_CSV.exists():
        raise RuntimeError(f"Missing statistics CSV: {STATS_CSV}")

    rows = load_stats_rows(STATS_CSV)

    table = Rect(panel.left + 30, panel.top + 66, panel.right - 30, panel.bottom - 28)
    draw.rectangle((table.left, table.top, table.right, table.bottom), outline=(168, 161, 149), width=2)

    c_metric = table.left + 16
    c_long = table.left + 520
    c_2023 = table.left + 730
    c_2025 = table.left + 940
    c_fold = table.left + 1150
    c_p = table.left + 1360
    c_dir = table.left + 1530
    c_eff = table.left + 1700
    c_sig = table.left + 1880

    draw.text((c_metric, table.top + 8), "Metric", fill=TEXT_DARK, font=f_text)
    draw.text((c_long, table.top + 8), "Long median", fill=TEXT_DARK, font=f_text)
    draw.text((c_2023, table.top + 8), "2023 median", fill=TEXT_DARK, font=f_text)
    draw.text((c_2025, table.top + 8), "2025 median", fill=TEXT_DARK, font=f_text)
    draw.text((c_fold, table.top + 8), "Fold vs long", fill=TEXT_DARK, font=f_text)
    draw.text((c_p, table.top + 8), "p (2023 | 2025)", fill=TEXT_DARK, font=f_text)
    draw.text((c_dir, table.top + 8), "Direction", fill=TEXT_DARK, font=f_text)
    draw.text((c_eff, table.top + 8), "Cliff's delta", fill=TEXT_DARK, font=f_text)
    draw.text((c_sig, table.top + 8), "q<0.05", fill=TEXT_DARK, font=f_text)

    row_top = table.top + 44
    available = max(160, table.bottom - row_top - 36)
    row_h = max(44, int(available / max(len(rows), 1)))

    for i, row in enumerate(rows):
        metric_label = str(row["metric"])
        med_long = float(row["med_long"])
        med_2023 = float(row["med_2023"])
        med_2025 = float(row["med_2025"])
        fold_2023 = float(row["fold_2023"])
        fold_2025 = float(row["fold_2025"])
        p_2023 = float(row["p_2023"])
        p_2025 = float(row["p_2025"])
        eff_2023 = float(row["eff_2023"])
        eff_2025 = float(row["eff_2025"])
        q_2023 = float(row["q_2023"])
        q_2025 = float(row["q_2025"])
        nL = int(row["nL"])
        n23 = int(row["n23"])
        n25 = int(row["n25"])
        tag = str(row["tag"])

        y = row_top + i * row_h
        y_mid = y + row_h // 2
        draw.line((table.left, y + row_h, table.right, y + row_h), fill=GRID, width=1)

        if tag == "water":
            color = (70, 70, 70)
        elif tag in MASK_COLOR:
            color = MASK_COLOR[tag]
        else:
            color = (80, 80, 80)

        draw.text((c_metric, y_mid - 10), metric_label, fill=color, font=f_small)
        draw.text((c_long, y_mid - 10), f"{med_long:.1f} (n={nL})", fill=TEXT_MID, font=f_small)
        draw.text((c_2023, y_mid - 10), f"{med_2023:.1f} (n={n23})", fill=TEXT_MID, font=f_small)
        draw.text((c_2025, y_mid - 10), f"{med_2025:.1f} (n={n25})", fill=TEXT_MID, font=f_small)
        draw.text((c_fold, y_mid - 10), f"{fold_2023:.2f}x | {fold_2025:.2f}x", fill=color, font=f_small)
        draw.text((c_p, y_mid - 10), f"{p_2023:.3f} | {p_2025:.3f}", fill=TEXT_MID, font=f_small)

        d23 = direction_label(fold_2023)
        d25 = direction_label(fold_2025)
        draw.text((c_dir, y_mid - 10), f"{d23} | {d25}", fill=TEXT_MID, font=f_small)
        draw.text((c_eff, y_mid - 10), f"{eff_2023:+.2f} | {eff_2025:+.2f}", fill=TEXT_MID, font=f_small)

        sig23 = "yes" if np.isfinite(q_2023) and q_2023 < 0.05 else "no"
        sig25 = "yes" if np.isfinite(q_2025) and q_2025 < 0.05 else "no"
        s_color = (34, 120, 74) if (sig23 == "yes" or sig25 == "yes") else TEXT_MID
        draw.text((c_sig, y_mid - 10), f"{sig23} | {sig25}", fill=s_color, font=f_small)

    note = "Two-sided permutation tests are shown as p-values. q-values use Benjamini-Hochberg across all row-year comparisons; significance threshold q<0.05 (95% confidence level, FDR-controlled)."
    draw.text((table.left + 6, table.bottom + 6), note, fill=TEXT_MID, font=f_small)



records = load_records(SUMMARY_CSV)
if not records:
    raise RuntimeError("No records loaded from summary CSV.")

area_factor, area_unit = choose_area_unit(records)

f_h2 = font(36, bold=True)
f_body = font(27)
f_small = font(22)

W = 2500
main_canvas = Image.new("RGB", (W, 680), BG)
main_draw = ImageDraw.Draw(main_canvas)
panel_c_medians_by_context(
    main_draw,
    Rect(46, 34, 2454, 620),
    records,
    area_factor,
    area_unit,
    f_h2,
    f_body,
    f_small,
)
main_draw.text(
    (56, 638),
    f"All area values shown in {area_unit}; left bars show loss and right bars show gain.",
    fill=(72, 66, 58),
    font=f_small,
)
main_canvas.save(OUT_PNG, format="PNG")

supplementary_canvas = Image.new("RGB", (W, 620), BG)
supplementary_draw = ImageDraw.Draw(supplementary_canvas)
panel_b_bidirectional_by_context(
    supplementary_draw,
    Rect(46, 34, 2454, 570),
    records,
    area_factor,
    area_unit,
    f_h2,
    f_body,
    f_small,
)
supplementary_draw.text(
    (56, 582),
    f"Supplementary figure; all area values shown in {area_unit}.",
    fill=(72, 66, 58),
    font=f_small,
)
supplementary_canvas.save(OUT_SUPPLEMENTARY_PNG, format="PNG")
OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
print(f"wrote {OUT_PNG}")
print(f"wrote {OUT_SUPPLEMENTARY_PNG}")

