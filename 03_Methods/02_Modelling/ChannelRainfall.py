from __future__ import annotations
import csv
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from math import cos, pi, sqrt
from pathlib import Path
from statistics import mean
from typing import Iterable
import numpy as np
from pyproj import CRS, Transformer
import shapefile
from shapely import contains_xy
from shapely.geometry import Polygon, box
from shapely.ops import transform as shapely_transform
import tifffile

#file acquistion i could change it to something solid but it remains as this while i pass a lot of files through it
pairre = re.compile(r"change_class_clean_(\d{4}-\d{2}-\d{2})_to_(\d{4}-\d{2}-\d{2})\.tif$")
TARGET_MASKS = {"active_channel_mask", "channel_sediment_mask"}


def getroot() -> Path:
    return Path(__file__).resolve().parents[2]
def parsedate(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()

def inferseriesid(changeroot: Path, explicit: str | None = None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    name = changeroot.name
    lowered = name.lower()
    if lowered == "sentinel2_changeframework":
        return "long_series"
    suffix_match = re.search(r"(19|20)\d{2}$", name)
    if suffix_match:
        return suffix_match.group(0)
    return name


def loadchirps(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            rows.append(
                {
                    "id": row["id"],
                    "lon": float(row["lon"]),
                    "lat": float(row["lat"]),
                    "date": parsedate(row["date"]),
                    "chirps": float(row["chirps"]),
                }
            )
    return rows

def loadmonthly(chirps: list[dict]) -> dict[tuple[int, int], float]:
    totals: dict[tuple[int, int], float] = defaultdict(float)
    for row in chirps:
        totals[(row["date"].year, row["date"].month)] += row["chirps"]
    return dict(totals)
def loadmam(path: Path) -> dict[int, float]:
    result: dict[int, float] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            result[int(row["year"])] = float(row["total_mm_MAM"])
    return result


def shapeToPolygon(shape: shapefile.Shape) -> Polygon:
    points = shape.points
    if not points:
        raise ValueError("empty catchment geometry")

    parts = list(shape.parts) + [len(points)]
    rings = [points[start:end] for start, end in zip(parts[:-1], parts[1:]) if end - start >= 3]
    if not rings:
        raise ValueError("catchment geometry does not contain a valid polygon ring")

    shell = rings[0]
    holes = rings[1:] if len(rings) > 1 else []
    return Polygon(shell, holes)

def loadshapes(path: Path) -> tuple[list[Polygon], CRS | None]:
    reader = shapefile.Reader(str(path))
    shapes = [shapeToPolygon(shape) for shape in reader.shapes()]

    crs = None
    prjpath = path.with_suffix(".prj")
    if prjpath.exists():
        prjtext = prjpath.read_text(encoding="utf-8", errors="ignore").strip()
        if prjtext:
            crs = CRS.from_wkt(prjtext)
    elif shapes:
        bounds = geometryUnion(shapes).bounds
        if max(abs(value) for value in bounds) > 1000:
            crs = CRS.from_epsg(3857)

    return shapes, crs

def readRaster(path: Path) -> tuple[np.ndarray, dict]:
    with tifffile.TiffFile(path) as tif:
        page = tif.pages[0]
        data = page.asarray()
        if data.ndim == 3:
            data = data[0]

        scale_tag = page.tags.get(33550)
        tie_tag = page.tags.get(33922)
        geokey_tag = page.tags.get(34735)

        if scale_tag is None or tie_tag is None or geokey_tag is None:
            raise ValueError(f"missing GeoTIFF georeference tags in {path.name}")

        meta = {
            "scale": tuple(float(value) for value in scale_tag.value),
            "tie": tuple(float(value) for value in tie_tag.value),
            "geokeys": tuple(int(value) for value in geokey_tag.value),
        }

    return data.astype(np.uint8), meta

def parseGeotiffCrs(geokeys: tuple[int, ...]) -> CRS | None:
    if len(geokeys) < 4:
        return None

    keycount = geokeys[3]
    entries = geokeys[4 : 4 + keycount * 4]
    keymap: dict[int, tuple[int, int, int]] = {}

    for index in range(0, len(entries), 4):
        keyid, tifftag, count, value = entries[index : index + 4]
        keymap[int(keyid)] = (int(tifftag), int(count), int(value))
    for keyid in (2048, 3072):
        entry = keymap.get(keyid)
        if entry and entry[1] == 1:
            try:
                return CRS.from_epsg(entry[2])
            except Exception:
                return None
    return None

def rasterAffine(meta: dict) -> tuple[float, float, float, float, float, float]:
    scale_x, scale_y, _ = meta["scale"]
    tie_col, tie_row, _tie_z, tie_x, tie_y, _tie_z2 = meta["tie"]
    return tie_col, tie_row, tie_x, tie_y, scale_x, scale_y

#CRS specific remember to fix later
def rasterPixelAreaM2(meta: dict, raster_crs: CRS | None, center_lat: float | None = None) -> float:
    scale_x = meta["scale"][0]
    scale_y = meta["scale"][1]

    if raster_crs is not None and raster_crs.is_geographic:
        lat = 0.0 if center_lat is None else center_lat
        meters_per_deg_lat = 111132.92
        meters_per_deg_lon = 111320.0 * cos(lat * pi / 180.0)
        return abs(scale_x) * meters_per_deg_lon * abs(scale_y) * meters_per_deg_lat

    return abs(scale_x) * abs(scale_y)

def transformGeometry(geometry: Polygon, source_crs: CRS | None, target_crs: CRS | None) -> Polygon:
    if source_crs is None or target_crs is None or source_crs == target_crs:
        return geometry

    transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    return shapely_transform(lambda x, y, z=None: transformer.transform(x, y), geometry)

def geometryUnion(shapes: Iterable[Polygon]) -> Polygon:
    iterator = iter(shapes)
    geometry = next(iterator)
    for candidate in iterator:
        geometry = geometry.union(candidate)
    return geometry

def explodePolygons(geometry) -> list[Polygon]:
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Polygon":
        return [geometry]
    if geometry.geom_type in {"MultiPolygon", "GeometryCollection"}:
        result: list[Polygon] = []
        for part in geometry.geoms:
            result.extend(explodePolygons(part))
        return result
    return []

def buildTrunkcorridor(shapes: list[Polygon], sourcecrs: CRS | None) -> list[Polygon]:
    catchment = geometryUnion(shapes)
    targetcrs = CRS.from_epsg(4326)
    catchment4326 = transformGeometry(catchment, sourcecrs, targetcrs)
    xmin, ymin, xmax, ymax = catchment4326.bounds
    width = xmax - xmin
    height = ymax - ymin
    trunkwindow = box(
        xmin + 0.50 * width,
        ymin + 0.56 * height,
        xmin + 0.86 * width,
        ymax,
    )
    corridor = catchment4326.intersection(trunkwindow)
    corridorpolys = explodePolygons(corridor)
    if not corridorpolys:
        raise RuntimeError("trunk corridor does not intersect the catchment")
    return corridorpolys

def parsepair(path: Path) -> tuple[date, date]:
    match = pairre.search(path.name)
    if not match:
        raise ValueError(f"unable to parse date pair from filename: {path.name}")
    pre = parsedate(match.group(1))
    post = parsedate(match.group(2))
    return pre, post

def findpairs(root: Path) -> list[Path]:
    return sorted(root.glob("**/change_class_clean_*.tif"))

def clipcount(rasterpath: Path, shapes: list[Polygon] | None, shapecrs) -> dict:
    values, meta = readRaster(rasterpath)
    rastercrs = parseGeotiffCrs(meta["geokeys"])

    if shapes:
        geometry = geometryUnion(shapes)
        geometry = transformGeometry(geometry, shapecrs, rastercrs)

        _, _, tie_x, tie_y, scale_x, scale_y = rasterAffine(meta)
        height, width = values.shape
        blocksize = 512
        countmap: dict[int, int] = defaultdict(int)

        for row_start in range(0, height, blocksize):
            row_stop = min(height, row_start + blocksize)
            block = values[row_start:row_stop, :]
            rows = np.arange(row_start, row_stop, dtype=float)
            cols = np.arange(width, dtype=float)
            xs = tie_x + (cols + 0.5) * scale_x
            ys = tie_y - (rows + 0.5) * scale_y
            xx, yy = np.meshgrid(xs, ys)
            mask = contains_xy(geometry, xx, yy)
            if not np.any(mask):
                continue

            selected = block[mask]
            unique, counts = np.unique(selected, return_counts=True)
            for value, count in zip(unique, counts):
                countmap[int(value)] += int(count)
    else:
        unique, counts = np.unique(values, return_counts=True)
        countmap = {int(v): int(c) for v, c in zip(unique, counts)}

    totalpixels = int(sum(countmap.values()))
    validpixels = totalpixels - int(countmap.get(255, 0))
    gainpixels = int(countmap.get(1, 0))
    losspixels = int(countmap.get(2, 0))
    nochangepixels = int(countmap.get(0, 0))
    invalidpixels = int(countmap.get(255, 0))

    center_lat = None
    if rastercrs is not None and rastercrs.is_geographic:
        _, _, tie_x, tie_y, scale_x, scale_y = rasterAffine(meta)
        center_lat = tie_y - (values.shape[0] * scale_y) / 2.0

    areapixelm2 = rasterPixelAreaM2(meta, rastercrs, center_lat=center_lat)

    return {
        "total_pixels": totalpixels,
        "valid_pixels": validpixels,
        "nochange_pixels": nochangepixels,
        "gain_pixels": gainpixels,
        "loss_pixels": losspixels,
        "invalid_pixels": invalidpixels,
        "change_pixels": gainpixels + losspixels,
        "net_change_pixels": gainpixels - losspixels,
        "gain_area_m2": gainpixels * areapixelm2,
        "loss_area_m2": losspixels * areapixelm2,
        "change_area_m2": (gainpixels + losspixels) * areapixelm2,
        "pixel_area_m2": areapixelm2,
    }

#note to self to recheck the chirps outputs
def rainbetween(chirps: list[dict], start: date, end: date) -> float:
    return float(sum(row["chirps"] for row in chirps if start <= row["date"] <= end))
def rain30(chirps: list[dict], end: date) -> float:
    start = end - timedelta(days=29)
    return float(sum(row["chirps"] for row in chirps if start <= row["date"] <= end))

#statisticccccals
def pearson(xs: list[float], ys: list[float]) -> tuple[float, float]:
    if len(xs) != len(ys) or len(xs) < 2:
        return float("nan"), float("nan")

    mx = mean(xs)
    my = mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denx = sqrt(sum((x - mx) ** 2 for x in xs))
    deny = sqrt(sum((y - my) ** 2 for y in ys))
    if denx == 0 or deny == 0:
        return float("nan"), float("nan")

    return num / (denx * deny), float("nan")
#spearmans ctrl F rank
def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda idx: values[idx])
    result = [0.0] * len(values)
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[order[j + 1]] == values[order[i]]:
            j += 1
        rank = (i + j + 2) / 2.0
        for k in range(i, j + 1):
            result[order[k]] = rank
        i = j + 1
    return result
def spearman(xs: list[float], ys: list[float]) -> tuple[float, float]:
    if len(xs) != len(ys) or len(xs) < 2:
        return float("nan"), float("nan")
    return pearson(ranks(xs), ranks(ys))

############################################################## 
#above func keep as is refactor below when free
def writerows(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(records[0].keys()) if records else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

def buildrecords(
    changepath: Path,
    seriesid: str,
    masklabel: str,
    chirps: list[dict],
    mam: dict[int, float],
    monthly: dict[tuple[int, int], float],
    contextmode: str,
    shapes: list[Polygon] | None,
    shapecrs: CRS | None,
) -> list[dict]:
    pairs = findpairs(changepath)
    if not pairs:
        return []

    records: list[dict] = []
    for rasterpath in pairs:
        pre, post = parsepair(rasterpath)
        counts = clipcount(rasterpath, shapes, shapecrs)

        raininterval = rainbetween(chirps, pre, post)
        rain30d = rain30(chirps, post)

        preyear = int(pre.year)
        postyear = int(post.year)

        if contextmode == "monthly":
            precontextperiod = f"{preyear:04d}-{pre.month:02d}"
            postcontextperiod = f"{postyear:04d}-{post.month:02d}"
            precontextmm = monthly.get((preyear, pre.month), float("nan"))
            postcontextmm = monthly.get((postyear, post.month), float("nan"))
            mampre = float("nan")
            mampost = float("nan")
        else:
            precontextperiod = str(preyear)
            postcontextperiod = str(postyear)
            precontextmm = mam.get(preyear, float("nan"))
            postcontextmm = mam.get(postyear, float("nan"))
            mampre = precontextmm
            mampost = postcontextmm

        records.append(
            {
                "series_id": seriesid,
                "mask": masklabel,
                "pre_date": pre.isoformat(),
                "post_date": post.isoformat(),
                "interval_days": int((post - pre).days),
                "rain_mm_interval": raininterval,
                "rain_mm_30d_post": rain30d,
                "context_mode": contextmode,
                "context_period_pre": precontextperiod,
                "context_period_post": postcontextperiod,
                "context_mm_pre": precontextmm,
                "context_mm_post": postcontextmm,
                "mam_mm_pre_year": mampre,
                "mam_mm_post_year": mampost,
                **counts,
            }
        )

    for row in records:
        valid = row["valid_pixels"]
        total = row["total_pixels"]
        interval_days = max(int(row["interval_days"]), 1)

        row["gain_area_ha"] = row["gain_area_m2"] / 10000.0
        row["loss_area_ha"] = row["loss_area_m2"] / 10000.0
        row["change_area_ha"] = row["change_area_m2"] / 10000.0
        row["net_change_area_ha"] = row["net_change_pixels"] * row["pixel_area_m2"] / 10000.0
        row["invalid_fraction_total"] = (row["invalid_pixels"] / total) if total > 0 else float("nan")
        row["change_fraction_valid"] = (row["change_pixels"] / valid) if valid > 0 else float("nan")
        row["net_fraction_valid"] = (row["net_change_pixels"] / valid) if valid > 0 else float("nan")
        row["abs_net_fraction_valid"] = (abs(row["net_change_pixels"]) / valid) if valid > 0 else float("nan")
        row["rain_intensity_mm_day"] = row["rain_mm_interval"] / interval_days
        row["change_rate_ha_day"] = row["change_area_ha"] / interval_days
        row["net_rate_ha_day"] = row["net_change_area_ha"] / interval_days

    return records

def tofloat(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")
def isfinite(value: float) -> bool:
    return not np.isnan(value) and not np.isinf(value)

def buildstats(records: list[dict], maxinvalidfraction: float, minsamples: int) -> list[dict]:
    predictor_cols = [
        "rain_mm_interval",
        "rain_intensity_mm_day",
        "rain_mm_30d_post",
        "context_mm_pre",
        "context_mm_post",
    ]
    response_cols = [
        "change_area_ha",
        "net_change_area_ha",
        "change_rate_ha_day",
        "net_rate_ha_day",
        "change_fraction_valid",
        "abs_net_fraction_valid",
    ]

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in records:
        grouped[(str(row.get("series_id", "")), str(row.get("mask", "")))].append(row)
    stats_rows: list[dict] = []
    for (series_id, mask), group_rows in sorted(grouped.items()):
        qc_rows = [
            row for row in group_rows
            if isfinite(tofloat(row.get("invalid_fraction_total")))
            and tofloat(row.get("invalid_fraction_total")) <= maxinvalidfraction
        ]
        for predictor in predictor_cols:
            for response in response_cols:
                xs: list[float] = []
                ys: list[float] = []
                for row in qc_rows:
                    x = tofloat(row.get(predictor))
                    y = tofloat(row.get(response))
                    if isfinite(x) and isfinite(y):
                        xs.append(x)
                        ys.append(y)
                n = len(xs)
                if n >= minsamples:
                    rho, _ = spearman(xs, ys)
                    r, _ = pearson(xs, ys)
                else:
                    rho = float("nan")
                    r = float("nan")
                stats_rows.append(
                    {
                        "series_id": series_id,
                        "mask": mask,
                        "predictor": predictor,
                        "response": response,
                        "n": n,
                        "min_samples_required": minsamples,
                        "max_invalid_fraction": maxinvalidfraction,
                        "spearman_rho": rho,
                        "pearson_r": r,
                    }
                )
    return stats_rows

def collectrecordsforroot(
    changeroot: Path,
    seriesid: str,
    chirps: list[dict],
    mam: dict[int, float],
    monthly: dict[tuple[int, int], float],
    contextmode: str,
    shapes: list[Polygon] | None,
    shapecrs: CRS | None,
    maxinvalidfraction: float,
) -> list[dict]:
    changerootismask = changeroot.name.endswith("_mask")
    if changerootismask:
        masks = [changeroot.name] if changeroot.name in TARGET_MASKS else []
    else:
        if not changeroot.exists():
            print(f"missing change root: {changeroot}; skipping")
            return []
        masks = sorted(
            [child.name for child in changeroot.iterdir() if child.is_dir() and child.name in TARGET_MASKS]
        )

    combinedrecords: list[dict] = []
    for maskname in masks:
        if changerootismask:
            if maskname != changeroot.name:
                continue
            changepath = changeroot
        else:
            changepath = changeroot / maskname
            if not changepath.exists():
                continue
        masklabel = changepath.name if changepath.name.endswith("_mask") else maskname
        records = buildrecords(changepath, seriesid, masklabel, chirps, mam, monthly, contextmode, shapes, shapecrs)
        if not records:
            print(f"no change rasters found under {changepath}; skipping")
            continue
        for row in records:
            invalid_fraction = tofloat(row.get("invalid_fraction_total"))
            row["excluded_by_invalid_qc"] = int(isfinite(invalid_fraction) and invalid_fraction > maxinvalidfraction)
        combinedrecords.extend(records)
    return combinedrecords
#git generic-ify the paths
#all these are my paths there is probably a good way to set this upppp on git but ive got these all like this id usually generic C:/bla/bla but there are so many
def main() -> None:
    root = getroot()
    outputdir = root / "04_Analysis" / "channelrainfallsum"
    chirpspath = root / "02_Data" / "01_Raw" / "CHIRPS" / "palanan_chirps_2016-2026.csv"
    mampath = root / "02_Data" / "01_Raw" / "CHIRPS" / "yearly_MAM_rainfall.csv"
    shapepath = root / "02_Data" / "01_Raw" / "palanan-rough.shp"
    contextmode = "yearlymam"
    maxinvalidfraction = 0.30
    minsamples = 4
    seriesconfigs = [
        {
            "series_id": "long_series",
            "change_root": root / "02_Data" / "02_Processed" / "Sentinel2_ChangeFramework",
            "output": outputdir / "channel_rainfall_summary_long.csv",
            "stats_output": outputdir / "channel_rainfall_summary_long_stats.csv",
        },
        {
            "series_id": "2023",
            "change_root": root / "02_Data" / "02_Processed" / "Sentinel2_ChangeFramework_2023",
            "output": outputdir / "channel_rainfall_summary_2023.csv",
            "stats_output": outputdir / "channel_rainfall_summary_2023_stats.csv",
        },
        {
            "series_id": "2025",
            "change_root": root / "02_Data" / "02_Processed" / "Sentinel2_ChangeFramework_2025",
            "output": outputdir / "channel_rainfall_summary_2025.csv",
            "stats_output": outputdir / "channel_rainfall_summary_2025_stats.csv",
        },
    ]
#end paths here
    chirps = loadchirps(chirpspath)
    yearlymode = contextmode in {"yearlymam", "yearly_mam"}
    mam = loadmam(mampath) if yearlymode else {}
    monthly = loadmonthly(chirps) if contextmode == "monthly" else {}

    if not shapepath.exists():
        raise SystemExit(f"shape not found at {shapepath}")

    shapes, shapecrs = loadshapes(shapepath)
    shapes = buildTrunkcorridor(shapes, shapecrs)
    shapecrs = CRS.from_epsg(4326)

    allrecords: list[dict] = []

    for cfg in seriesconfigs:
        seriesid = str(cfg["series_id"])
        changeroot = Path(cfg["change_root"])
        outputpath = Path(cfg["output"])
        statsoutputpath = Path(cfg["stats_output"])

        records = collectrecordsforroot(
            changeroot=changeroot,
            seriesid=seriesid,
            chirps=chirps,
            mam=mam,
            monthly=monthly,
            contextmode=contextmode,
            shapes=shapes,
            shapecrs=shapecrs,
            maxinvalidfraction=maxinvalidfraction,
        )

        if not records:
            print(f"no records produced for series {seriesid}; skipping output")
            continue

        records = sorted(
            records,
            key=lambda row: (
                row.get("series_id", ""),
                row.get("mask", ""),
                row.get("pre_date", ""),
                row.get("post_date", ""),
            ),
        )
        writerows(outputpath, records)
        print(f"wrote {outputpath}")

        statsrows = buildstats(records, maxinvalidfraction, max(minsamples, 2))
        if statsrows:
            writerows(statsoutputpath, statsrows)
            print(f"wrote {statsoutputpath}")

        allrecords.extend(records)

    allrecords = sorted(
        allrecords,
        key=lambda row: (
            row.get("series_id", ""),
            row.get("mask", ""),
            row.get("pre_date", ""),
            row.get("post_date", ""),
        ),
    )
    combinedoutput = outputdir / "channel_rainfall_summary_all.csv"
    combinedstatsoutput = outputdir / "channel_rainfall_summary_all_stats.csv"
    writerows(combinedoutput, allrecords)
    print(f"wrote {combinedoutput}")

    combinedstats = buildstats(allrecords, maxinvalidfraction, max(minsamples, 2))
    if combinedstats:
        writerows(combinedstatsoutput, combinedstats)
        print(f"wrote {combinedstatsoutput}")
#run from execute
if __name__ == "__main__":
    main()
