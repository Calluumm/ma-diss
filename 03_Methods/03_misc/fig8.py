from __future__ import annotations

import json
import subprocess
from pathlib import Path

import fiona
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from fiona.transform import transform_geom


ROOT = Path("C:/Users/Student/Desktop/Masters/Dissertation")
LINEATION = ROOT / "02_Data" / "01_Raw" / "manual4326-extended.shp"
CATCHMENT = ROOT / "02_Data" / "01_Raw" / "shp_check" / "Palanan-catchment-unextended.shp"
OUT = ROOT / "05_Figures" / "fig8.png"

SERIES = {
    "2023": {
        "label": "2023 event year",
        "cartography": True,
        "root": ROOT / "02_Data" / "02_Processed" / "Sentinel2_ChangeFramework_2023",
        "class_root": ROOT / "02_Data" / "02_Processed" / "Sentinel2_Geomorphology_OTB_2023",
        "post_date": "2024-04-21",
        "intervals": [
            "2023-05-07_to_2023-08-05",
            "2023-08-05_to_2023-09-09",
            "2023-09-09_to_2024-02-21",
            "2024-02-21_to_2024-04-21",
        ],
    },
    "2025": {
        "label": "2025 non-event year",
        "root": ROOT / "02_Data" / "02_Processed" / "Sentinel2_ChangeFramework_2025",
        "class_root": ROOT / "02_Data" / "02_Processed" / "Sentinel2_Geomorphology_OTB_2025",
        "post_date": "2026-04-16",
        "intervals": [
            "2025-04-21_to_2025-06-02",
            "2025-06-02_to_2025-08-01",
            "2025-08-01_to_2025-11-12",
            "2025-11-12_to_2026-04-16",
        ],
    },
    "long": {
        "label": "2017-2026 long context",
        "root": ROOT / "02_Data" / "02_Processed" / "Sentinel2_ChangeFramework",
        "class_root": ROOT / "02_Data" / "02_Processed" / "Sentinel2_Geomorphology_OTB",
        "post_date": "2026-04-16",
        "intervals": [
            "2017-04-13_to_2018-05-28",
            "2018-05-28_to_2019-04-23",
            "2019-04-23_to_2020-03-13",
            "2020-03-13_to_2021-05-02",
            "2021-05-02_to_2022-03-18",
            "2022-03-18_to_2023-03-21",
            "2023-03-21_to_2024-04-21",
            "2024-04-21_to_2025-04-21",
            "2025-04-21_to_2026-04-16",
        ],
    },
}

MASKS = {
    "water_mask": (94, 190, 230),
    "channel_sediment_mask": (237, 157, 63),
}
CLASS_COLORS = {
    1: (112, 208, 240),
    2: (70, 165, 75),
    3: (225, 199, 75),
    4: (215, 55, 55),
    5: (235, 139, 45),
}
BLACK = (20, 20, 24)
BASE_GRAY = (48, 48, 52)
WHITE = (244, 244, 244)
MUTED = (170, 172, 180)
RED = (210, 35, 45)


def font(size: int, bold: bool = False):
    names = ["arialbd.ttf", "segoeuib.ttf"] if bold else ["arial.ttf", "segoeui.ttf"]
    for name in names:
        path = Path("C:/Windows/Fonts") / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def load_band(path: Path) -> np.ndarray:
    arr = np.asarray(Image.open(path))
    if arr.ndim == 3:
        arr = arr[:, :, 0]
    return arr.astype(np.uint16)


def gdal_metadata(path: Path):
    result = subprocess.run(["gdalinfo", "-json", str(path)], capture_output=True, text=True, check=True)
    meta = json.loads(result.stdout)
    return tuple(float(value) for value in meta["geoTransform"]), tuple(int(value) for value in meta["size"]), meta.get("coordinateSystem", {}).get("wkt")


def world_to_pixel(x: float, y: float, gt) -> tuple[float, float]:
    gt0, gt1, gt2, gt3, gt4, gt5 = gt
    det = gt1 * gt5 - gt2 * gt4
    dx, dy = x - gt0, y - gt3
    return (dx * gt5 - dy * gt2) / det, (dy * gt1 - dx * gt2) / det


def draw_geometry_mask(path: Path, raster_crs: str | None, gt, size: tuple[int, int], fallback_crs: str) -> np.ndarray:
    width, height = size
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    with fiona.open(path) as source:
        source_crs = source.crs_wkt or source.crs or fallback_crs
        for feature in source:
            geometry = feature.get("geometry")
            if not geometry:
                continue
            geometry = transform_geom(source_crs, raster_crs, geometry) if raster_crs else geometry
            kind = geometry.get("type")
            coordinates = geometry.get("coordinates")
            if kind == "Polygon":
                polygons = [coordinates]
            elif kind == "MultiPolygon":
                polygons = coordinates
            else:
                polygons = []
            for polygon in polygons:
                points = [world_to_pixel(float(x), float(y), gt) for x, y in polygon[0]]
                if len(points) >= 3:
                    draw.polygon(points, fill=255)
            break
    return np.asarray(mask, dtype=np.uint8) > 0


def draw_line_mask(path: Path, raster_crs: str | None, gt, size: tuple[int, int], fallback_crs: str) -> np.ndarray:
    width, height = size
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    with fiona.open(path) as source:
        source_crs = source.crs_wkt or source.crs or fallback_crs
        for feature in source:
            geometry = feature.get("geometry")
            if not geometry:
                continue
            geometry = transform_geom(source_crs, raster_crs, geometry) if raster_crs else geometry
            kind = geometry.get("type")
            coordinates = geometry.get("coordinates")
            lines = [coordinates] if kind == "LineString" else coordinates if kind == "MultiLineString" else []
            for line in lines:
                points = [world_to_pixel(float(x), float(y), gt) for x, y in line]
                if len(points) >= 2:
                    draw.line(points, fill=255, width=1)
    return np.asarray(mask, dtype=np.uint8) > 0


def dilate(mask: np.ndarray, radius: int) -> np.ndarray:
    result = mask.copy()
    for _ in range(max(0, radius)):
        expanded = result.copy()
        expanded[1:, :] |= result[:-1, :]
        expanded[:-1, :] |= result[1:, :]
        expanded[:, 1:] |= result[:, :-1]
        expanded[:, :-1] |= result[:, 1:]
        result = expanded
    return result


def crop(arr: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
    x1, y1, x2, y2 = bbox
    return arr[y1:y2, x1:x2]


def meters_per_pixel(gt, height: int) -> float:
    center_lat = gt[3] + gt[5] * (height * 0.5)
    latitude_radians = float(np.deg2rad(center_lat))
    meters_lat = 111320.0
    meters_lon = 111320.0 * float(np.cos(latitude_radians))
    return (abs(gt[1]) * meters_lon + abs(gt[5]) * meters_lat) * 0.5


def bbox_from_mask(mask: np.ndarray, pad: int = 20) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask)
    return max(xs.min() - pad, 0), max(ys.min() - pad, 0), min(xs.max() + pad + 1, mask.shape[1]), min(ys.max() + pad + 1, mask.shape[0])


def class_rgb(class_map: np.ndarray, river: np.ndarray) -> np.ndarray:
    rgb = np.zeros((*class_map.shape, 3), dtype=np.uint8)
    for value, color in CLASS_COLORS.items():
        rgb[(class_map == value) & river] = color
    return rgb


def interval_path(root: Path, mask: str, interval: str) -> Path:
    return root / mask / interval / f"change_class_clean_{interval}.tif"


def segment_metrics(config: dict, river: np.ndarray, bbox: tuple[int, int, int, int], bins: int = 10) -> dict[str, np.ndarray]:
    river_crop = crop(river, bbox)
    height = river_crop.shape[0]
    metrics = {mask: [] for mask in MASKS}
    for mask in MASKS:
        interval_values = []
        for interval in config["intervals"]:
            path = interval_path(config["root"], mask, interval)
            array = crop(load_band(path), bbox)
            values = []
            for index in range(bins):
                y1 = int(index * height / bins)
                y2 = int((index + 1) * height / bins)
                domain = river_crop[y1:y2]
                current = array[y1:y2]
                valid = domain & (current != 255)
                changed = valid & ((current == 1) | (current == 2))
                values.append(100.0 * np.count_nonzero(changed) / max(np.count_nonzero(valid), 1))
            interval_values.append(values)
        metrics[mask] = np.nanmean(np.asarray(interval_values, dtype=float), axis=0)
    return metrics


def build_panel(config: dict, bbox, gt, raster_crs, size, global_max: float, panel_size=(920, 1120)) -> Image.Image:
    panelw, panelh = panel_size
    image = Image.new("RGB", (panelw, panelh), BLACK)
    draw = ImageDraw.Draw(image)
    title_font = font(36, True)
    small_font = font(22)
    body_font = font(24)
    draw.text((22, 20), config["label"], fill=WHITE, font=title_font)

    post_path = config["class_root"] / config["post_date"] / f"{config['post_date']}_class_map.tif"
    class_map = crop(load_band(post_path), bbox)
    river_line = crop(river_mask_global, bbox)
    river_corridor = dilate(river_line, max(1, int(50.0 / 30.0)))
    catchment_crop = crop(catchment_mask_global, bbox)
    map_rgb = np.zeros((*class_map.shape, 3), dtype=np.uint8)
    map_rgb[catchment_crop] = BASE_GRAY
    class_layer = class_rgb(class_map, river_corridor)
    map_rgb[river_corridor] = class_layer[river_corridor]
    map_image = Image.fromarray(map_rgb, mode="RGB").resize((760, 930), Image.Resampling.NEAREST)
    image.paste(map_image, (22, 90))

    if config.get("cartography"):
        mapw, maph = 760, 930
        map_x, map_y = 22, 90
        segment_font = font(16, True)
        for segment in range(1, 10):
            source_y = int(segment * river_corridor.shape[0] / 10)
            band = max(4, int(river_corridor.shape[0] * 0.008))
            y1 = max(0, source_y - band)
            y2 = min(river_corridor.shape[0], source_y + band + 1)
            ys, xs = np.where(river_corridor[y1:y2])
            if xs.size == 0:
                continue
            line_x1 = max(map_x + int(xs.min() * mapw / river_corridor.shape[1]) - 14, map_x)
            line_x2 = min(map_x + int(xs.max() * mapw / river_corridor.shape[1]) + 14, map_x + mapw)
            boundary_y = int(map_y + segment * maph / 10)
            for dash_start in range(line_x1, line_x2, 24):
                draw.line((dash_start, boundary_y, min(dash_start + 12, line_x2), boundary_y), fill=(190, 190, 195), width=2)
            label = "Section 1" if segment == 1 else f"S{segment}"
            draw.text((line_x2 + 5, boundary_y - 20), label, fill=(230, 230, 235), font=segment_font)

        source_width = max(bbox[2] - bbox[0], 1)
        scale_bar_m = 5000.0
        scale_bar_px = int(scale_bar_m / meters_per_pixel(gt, size[1]) * mapw / source_width)
        scale_bar_px = max(80, min(scale_bar_px, 180))
        bar_x = map_x + mapw - scale_bar_px - 28
        bar_y = map_y + maph - 48
        draw.line((bar_x, bar_y, bar_x + scale_bar_px, bar_y), fill=WHITE, width=5)
        draw.line((bar_x, bar_y - 7, bar_x, bar_y + 7), fill=WHITE, width=3)
        draw.line((bar_x + scale_bar_px, bar_y - 7, bar_x + scale_bar_px, bar_y + 7), fill=WHITE, width=3)
        draw.text((bar_x + scale_bar_px // 2 - 20, bar_y - 27), "5 km", fill=WHITE, font=font(16, True))

        arrow_x = map_x + mapw - 45
        arrow_bottom = map_y + maph - 88
        arrow_top = arrow_bottom - 62
        draw.line((arrow_x, arrow_bottom, arrow_x, arrow_top), fill=WHITE, width=4)
        draw.polygon([(arrow_x, arrow_top - 10), (arrow_x - 9, arrow_top + 10), (arrow_x + 9, arrow_top + 10)], fill=WHITE)
        draw.text((arrow_x - 7, arrow_top - 32), "N", fill=WHITE, font=font(18, True))

    metrics = segment_metrics(config, river_mask_global, bbox)
    bins = len(next(iter(metrics.values())))
    mapw, maph = 760, 930
    scale = 230.0 / max(global_max, 1.0)
    label_font = font(17, True)

    def draw_labeled_bar(value: float, color: tuple[int, int, int], y1: int, y2: int) -> None:
        length = max(2, int(value * scale))
        x2 = min(anchor + length, panelw - 8)
        draw.rectangle((anchor, y1, x2, y2), fill=color)
        label = f"{value:.1f}%"
        text_box = draw.textbbox((0, 0), label, font=label_font)
        text_width = text_box[2] - text_box[0]
        if x2 - anchor >= text_width + 8:
            text_x = anchor + 4
            text_color = (20, 25, 28)
        else:
            text_x = min(x2 + 5, panelw - text_width - 8)
            text_color = color
        draw.text((text_x, y1 - 3), label, fill=text_color, font=label_font)

    for index in range(bins):
        y = int(90 + (index + 0.5) * maph / bins)
        source_y1 = int(index * river_corridor.shape[0] / bins)
        source_y2 = int((index + 1) * river_corridor.shape[0] / bins)
        ys, xs = np.where(river_corridor[source_y1:source_y2])
        if xs.size == 0:
            continue
        anchor = int(np.median(xs) * mapw / river_corridor.shape[1]) + 22
        water = float(metrics["water_mask"][index])
        sediment = float(metrics["channel_sediment_mask"][index])
        draw_labeled_bar(water, MASKS["water_mask"], y - 12, y - 3)
        draw_labeled_bar(sediment, MASKS["channel_sediment_mask"], y + 3, y + 12)

    draw.text((22, 1030), "Mean interval gross change density", fill=MUTED, font=small_font)
    draw.text((22, 1060), "blue: water change density", fill=MASKS["water_mask"], font=body_font)
    draw.text((340, 1060), "orange: sediment change density", fill=MASKS["channel_sediment_mask"], font=body_font)
    return image


global river_mask_global, catchment_mask_global
representative = interval_path(SERIES["2023"]["root"], "water_mask", SERIES["2023"]["intervals"][0])
gt, size, raster_crs = gdal_metadata(representative)
width, height = size
target_crs = "EPSG:4326"
catchment = draw_geometry_mask(CATCHMENT, target_crs, gt, size, "EPSG:3857")
river_line = draw_line_mask(LINEATION, target_crs, gt, size, "EPSG:4326") & catchment
river_mask_global = river_line
catchment_mask_global = catchment
river_display = dilate(river_line, max(1, int(50.0 / 30.0)))
bbox = bbox_from_mask(catchment | river_display, 30)

all_metrics = []
for config in SERIES.values():
    metrics = segment_metrics(config, river_line, bbox)
    all_metrics.extend(metrics[mask] for mask in MASKS)
global_max = max(float(np.nanmax(values)) for values in all_metrics if values.size)

canvas = Image.new("RGB", (2860, 1220), (245, 245, 245))
draw = ImageDraw.Draw(canvas)
draw.text((50, 25), "Spatial distribution of mean interval water and sediment change", fill=(25, 25, 25), font=font(50, True))

x_positions = [40, 970, 1900]
for x, config in zip(x_positions, SERIES.values()):
    panel = build_panel(config, bbox, gt, raster_crs, size, global_max)
    canvas.paste(panel, (x, 110))

canvas.save(OUT, format="PNG")
print(f"Wrote figure: {OUT}")
