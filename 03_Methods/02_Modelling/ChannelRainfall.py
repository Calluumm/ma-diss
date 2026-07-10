from __future__ import annotations
import argparse
import csv
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from math import cos, pi, sqrt
from pathlib import Path
from statistics import mean
import fiona
import numpy as np
import rasterio
from rasterio.mask import mask as rastermask
from rasterio.warp import transform_geom

#file acquistion i could change it to something solid but it remains as this while i pass a lot of files through it
pairre = re.compile(r"change_class_clean_(\d{4}-\d{2}-\d{2})_to_(\d{4}-\d{2}-\d{2})\.tif$")
def getroot() -> Path:
    return Path(__file__).resolve().parents[2]
def parsedate(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


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


def loadshapes(path: Path, fallback_crs: str | None = None) -> tuple[list[dict], object]:
    with fiona.Env(SHAPE_RESTORE_SHX="YES"):
        with fiona.open(path) as src:
            shapes = [feature["geometry"] for feature in src]
            crs = src.crs_wkt or src.crs
            bounds = src.bounds

    if not crs:
        if fallback_crs:
            crs = fallback_crs
        elif max(abs(value) for value in bounds) > 1000:
            crs = "EPSG:3857"

    return shapes, crs


def parsepair(path: Path) -> tuple[date, date]:
    match = pairre.search(path.name)
    pre = parsedate(match.group(1))
    post = parsedate(match.group(2))
    return pre, post


def findpairs(root: Path) -> list[Path]:
    return sorted(root.glob("**/change_class_clean_*.tif"))


def pixelaream2(src: rasterio.io.DatasetReader) -> float:
    dx = abs(src.res[0])
    dy = abs(src.res[1])

    if src.crs and src.crs.is_geographic:
        midlat = (src.bounds.bottom + src.bounds.top) / 2.0
        mlat = 111132.92 #resolution thing
        mlon = 111320.0 * cos(midlat * pi / 180.0)
        return dx * mlon * dy * mlat

    return dx * dy


def clipcount(rasterpath: Path, shapes: list[dict] | None, shapecrs) -> dict:
    with rasterio.open(rasterpath) as src:
        if shapes:
            geom = shapes
            if shapecrs and src.crs and shapecrs != src.crs:
                geom = [transform_geom(shapecrs, src.crs, g, precision=6) for g in shapes]
            clipped, transform = rastermask(src, geom, crop=True, filled=True, nodata=255)
            values = clipped[0].astype(np.uint8)
        else:
            values = src.read(1).astype(np.uint8)

        unique, counts = np.unique(values, return_counts=True)
        countmap = {int(v): int(c) for v, c in zip(unique, counts)}

        validmask = values != 255
        validpixels = int(validmask.sum())
        gainpixels = int(countmap.get(1, 0))
        losspixels = int(countmap.get(2, 0))
        nochangepixels = int(countmap.get(0, 0))
        invalidpixels = int(countmap.get(255, 0))

        areapixelm2 = pixelaream2(src)

    return {
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

#change all these to match output files i would make it generic for github but this is simple enough to understand and i am lazy
def main() -> None:
    root = getroot()
    defaultchangeroot = root / "02_Data" / "02_Processed" / "Sentinel2_ChangeFramework" / "water_mask"
    defaultchirps = root / "02_Data" / "01_Raw" / "CHIRPS" / "palanan_chirps_2016-2026.csv"
    defaultmam = root / "02_Data" / "01_Raw" / "CHIRPS" / "yearly_MAM_rainfall.csv"
    defaultoutput = root / "04_Analysis" / "channel_rainfall_summary.csv"

    parser = argparse.ArgumentParser()
    parser.add_argument("--change-root", dest="changeroot", type=Path, default=defaultchangeroot)
    parser.add_argument("--chirps", dest="chirpspath", type=Path, default=defaultchirps)
    parser.add_argument("--mam", dest="mampath", type=Path, default=defaultmam)
    parser.add_argument(
        "--context-mode",
        dest="contextmode",
        choices=["yearlymam", "yearly_mam", "monthly"],
        default="yearlymam",
    )
    parser.add_argument("--shape", dest="shapepath", type=Path, default=None)
    parser.add_argument("--shape-crs", dest="shapecrs", default=None)
    parser.add_argument("--output", dest="outputpath", type=Path, default=defaultoutput)
    args = parser.parse_args()

    pairs = findpairs(args.changeroot)

    chirps = loadchirps(args.chirpspath)
    yearlymode = args.contextmode in {"yearlymam", "yearly_mam"}
    mam = loadmam(args.mampath) if yearlymode else {}
    monthly = loadmonthly(chirps) if args.contextmode == "monthly" else {}
    shapes = None
    shapecrs = None
    if args.shapepath:
        shapes, shapecrs = loadshapes(args.shapepath, args.shapecrs)

    records: list[dict] = []
    for rasterpath in pairs:
        pre, post = parsepair(rasterpath)
        counts = clipcount(rasterpath, shapes, shapecrs)

        raininterval = rainbetween(chirps, pre, post)
        rain30d = rain30(chirps, post)

        preyear = int(pre.year)
        postyear = int(post.year)

        if args.contextmode == "monthly":
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
                "mask": "water_mask",
                "pre_date": pre.isoformat(),
                "post_date": post.isoformat(),
                "interval_days": int((post - pre).days),
                "rain_mm_interval": raininterval,
                "rain_mm_30d_post": rain30d,
                "context_mode": args.contextmode,
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
        row["gain_area_ha"] = row["gain_area_m2"] / 10000.0
        row["loss_area_ha"] = row["loss_area_m2"] / 10000.0
        row["change_area_ha"] = row["change_area_m2"] / 10000.0
        row["net_change_area_ha"] = row["net_change_pixels"] * row["pixel_area_m2"] / 10000.0

    args.outputpath.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(records[0].keys()) if records else []
    with args.outputpath.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


if __name__ == "__main__":
    main()