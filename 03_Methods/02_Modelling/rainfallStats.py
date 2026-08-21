from __future__ import annotations
from pathlib import Path
import csv
import numpy as np
import tifffile
from dataclasses import dataclass
from datetime import datetime

#Paths, it relies on CRsummary.csv made by ChannelRainfall.py; creates CRstats.csv
#Also relies on having the classified imagery this is to be ran after dualrun.ps1 (or the individuak ones) and ChannelRainfall.py

rootdir = Path(__file__).resolve().parents[2]
inputsummarycsv = rootdir / "04_Analysis" / "channelrainfallsum" / "CRsummary.csv"
outputstatscsv = rootdir / "04_Analysis" / "channelrainfallsum" / "CRstats.csv"

GEOMROOTS = {
    "2023": rootdir / "02_Data" / "02_Processed" / "Sentinel2_Geomorphology_OTB_2023",
    "2025": rootdir / "02_Data" / "02_Processed" / "Sentinel2_Geomorphology_OTB_2025",
    "long_series": rootdir / "02_Data" / "02_Processed" / "Sentinel2_Geomorphology_OTB",
}
TARGETMASKS = ("active_channel_mask", "channel_sediment_mask")


#the class to hold the inputs rows
#the function reads the input csv and converts values appropriately also filters out unused stuff

@dataclass
class Record:
    seriesid: str
    mask: str
    predate: datetime
    postdate: datetime
    rainmminterval: float
    intervaldays: float
    gainm2: float
    lossm2: float
    changem2: float

def loadRecords(path: Path) -> list[Record]:
    rows: list[Record] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            mask = row.get("mask", "")
            if mask not in TARGETMASKS:
                continue

            def toFloat(value: str) -> float:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return float("nan")

            rows.append(
                Record(
                    seriesid=row.get("series_id", ""),
                    mask=mask,
                    predate=datetime.strptime(row["pre_date"], "%Y-%m-%d"),
                    postdate=datetime.strptime(row["post_date"], "%Y-%m-%d"),
                    rainmminterval=toFloat(row.get("rain_mm_interval", "nan")),
                    intervaldays=toFloat(row.get("interval_days", "nan")),
                    gainm2=toFloat(row.get("gain_area_m2", "nan")),
                    lossm2=toFloat(row.get("loss_area_m2", "nan")),
                    changem2=toFloat(row.get("change_area_m2", "nan")),
                )
            )
    rows.sort(key=lambda rec: (rec.seriesid, rec.predate, rec.mask))
    return rows

#These 3 following functions are just statistical analysis functions
#permutation testing, cliff's delta and benjamini hochberg correction

def permutationPvalueMeanDiff(a: np.ndarray, b: np.ndarray, nperm: int = 12000, seed: int = 7) -> float:
    rng = np.random.default_rng(seed)
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if a.size < 2 or b.size < 2:
        return float("nan")
    observed = float(np.mean(b) - np.mean(a))
    pool = np.concatenate([a, b])
    asize = a.size
    count = 0
    for _ in range(nperm):
        rng.shuffle(pool)
        diff = float(np.mean(pool[asize:]) - np.mean(pool[:asize]))
        if abs(diff) >= abs(observed):
            count += 1
    return float((count + 1) / (nperm + 1))

def cliffsDelta(a: np.ndarray, b: np.ndarray) -> float:
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if a.size == 0 or b.size == 0:
        return float("nan")
    gt = np.sum(b[:, None] > a[None, :])
    lt = np.sum(b[:, None] < a[None, :])
    return float((gt - lt) / (a.size * b.size))

def benjaminiHochberg(pvals: list[float]) -> list[float]:
    m = len(pvals)
    qvals = [float("nan")] * m
    order = sorted(range(m), key=lambda i: pvals[i])
    ranked = [pvals[i] for i in order]
    adjusted = [0.0] * m
    prev = 1.0
    for i in range(m - 1, -1, -1):
        rank = i + 1
        value = min(prev, (ranked[i] * m) / rank)
        prev = value
        adjusted[i] = value
    for i, idx in enumerate(order):
        qvals[idx] = float(min(1.0, max(0.0, adjusted[i])))
    return qvals

#function specifically to convert water coverage tifs to float arrays

def loadWaterCoverages() -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    for seriesid, root in GEOMROOTS.items():
        values: list[float] = []
        for path in sorted(root.glob("**/*_water_mask.tif")):
            arr = tifffile.imread(path)
            valid = arr != 255
            nvalid = int(np.count_nonzero(valid))
            if nvalid == 0:
                values.append(float("nan"))
                continue
            nwater = int(np.count_nonzero(arr[valid] == 1))
            values.append((100.0 * nwater) / nvalid)
        out[seriesid] = np.array(values, dtype=float)
    return out


#per row this function will calc medians, folds, pvalues, stat tests whatever and return them as dicts for the csv

def rowiter(records: list[Record]) -> list[dict[str, object]]:
    values = []
    for rec in records:
        values.extend([abs(rec.gainm2), abs(rec.lossm2), abs(rec.changem2)])
    areafactor = 1_000_000.0 if values and np.nanmedian(values) >= 2_000_000.0 else 1.0
    areaunit = "km2" if areafactor == 1_000_000.0 else "m2"
    rows: list[dict[str, object]] = []
    longrows = [record for record in records if record.seriesid == "long_series"]
    rows2023 = [record for record in records if record.seriesid == "2023"]
    rows2025 = [record for record in records if record.seriesid == "2025"]

    cover = loadWaterCoverages()
    covlong = cover.get("long_series", np.array([], dtype=float))
    cov2023 = cover.get("2023", np.array([], dtype=float))
    cov2025 = cover.get("2025", np.array([], dtype=float))

    medlong = float(np.nanmedian(covlong)) if covlong.size else float("nan")
    med2023 = float(np.nanmedian(cov2023)) if cov2023.size else float("nan")
    med2025 = float(np.nanmedian(cov2025)) if cov2025.size else float("nan")
    fold2023 = float((med2023 + 1e-6) / (medlong + 1e-6)) if np.isfinite(medlong) and np.isfinite(med2023) else float("nan")
    fold2025 = float((med2025 + 1e-6) / (medlong + 1e-6)) if np.isfinite(medlong) and np.isfinite(med2025) else float("nan")

    rows.append(
        {
            "metric": "Water mask coverage (%)",
            "med_long": medlong,
            "med_2023": med2023,
            "med_2025": med2025,
            "fold_2023": fold2023,
            "fold_2025": fold2025,
            "p_2023": permutationPvalueMeanDiff(covlong, cov2023, nperm=10000, seed=501),
            "p_2025": permutationPvalueMeanDiff(covlong, cov2025, nperm=10000, seed=502),
            "nL": int(covlong.size),
            "n23": int(cov2023.size),
            "n25": int(cov2025.size),
            "tag": "water",
            "eff_2023": cliffsDelta(covlong, cov2023),
            "eff_2025": cliffsDelta(covlong, cov2025),
            "q_2023": float("nan"),
            "q_2025": float("nan"),
        }
    )
    # repeats it for both the two masks 
    for mask in TARGETMASKS:
        def valuesForMode(source: list[Record], mode: str) -> np.ndarray:
            values = []
            for record in source:
                if record.mask != mask:
                    continue
                if mode == "magnitude":
                    values.append((record.gainm2 + record.lossm2) / areafactor)
                elif record.intervaldays > 0 and np.isfinite(record.intervaldays):
                    values.append(((record.gainm2 + record.lossm2) / areafactor) / record.intervaldays)
            return np.array(values, dtype=float)

        for mode, label in (
            ("magnitude", f"{mask.replace('_', ' ').title()} total change ({areaunit})"),
            ("rate", f"{mask.replace('_', ' ').title()} change rate ({areaunit}/day)"),
        ):
            vlong = valuesForMode(longrows, mode)
            v2023 = valuesForMode(rows2023, mode)
            v2025 = valuesForMode(rows2025, mode)

            medlong = float(np.nanmedian(vlong)) if vlong.size else float("nan")
            med2023 = float(np.nanmedian(v2023)) if v2023.size else float("nan")
            med2025 = float(np.nanmedian(v2025)) if v2025.size else float("nan")

            fold2023 = float((med2023 + 1e-6) / (medlong + 1e-6)) if np.isfinite(medlong) and np.isfinite(med2023) else float("nan")
            fold2025 = float((med2025 + 1e-6) / (medlong + 1e-6)) if np.isfinite(medlong) and np.isfinite(med2025) else float("nan")

            rows.append(
                {
                    "metric": label,
                    "med_long": medlong,
                    "med_2023": med2023,
                    "med_2025": med2025,
                    "fold_2023": fold2023,
                    "fold_2025": fold2025,
                    "p_2023": permutationPvalueMeanDiff(vlong, v2023, nperm=10000, seed=701 + len(rows)),
                    "p_2025": permutationPvalueMeanDiff(vlong, v2025, nperm=10000, seed=801 + len(rows)),
                    "nL": int(vlong.size),
                    "n23": int(v2023.size),
                    "n25": int(v2025.size),
                    "tag": mask,
                    "eff_2023": cliffsDelta(vlong, v2023),
                    "eff_2025": cliffsDelta(vlong, v2025),
                    "q_2023": float("nan"),
                    "q_2025": float("nan"),
                }
            )

    pindex: list[tuple[int, str]] = []
    pvalues: list[float] = []
    for rowindex, row in enumerate(rows):
        p23 = float(row.get("p_2023", float("nan")))
        p25 = float(row.get("p_2025", float("nan")))
        if np.isfinite(p23):
            pindex.append((rowindex, "q_2023"))
            pvalues.append(p23)
        if np.isfinite(p25):
            pindex.append((rowindex, "q_2025"))
            pvalues.append(p25)

    qvalues = benjaminiHochberg(pvalues)
    for (rowindex, key), qvalue in zip(pindex, qvalues):
        rows[rowindex][key] = qvalue
    return rows

#the output writer

def writeCsv(rows: list[dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "metric",
        "med_long",
        "med_2023",
        "med_2025",
        "fold_2023",
        "fold_2025",
        "p_2023",
        "p_2025",
        "nL",
        "n23",
        "n25",
        "tag",
        "eff_2023",
        "eff_2025",
        "q_2023",
        "q_2025",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

#just runs the functions above
records = loadRecords(inputsummarycsv)
rows = rowiter(records)
writeCsv(rows, outputstatscsv)
print(f"wrote {outputstatscsv}")
