import os
from pathlib import Path

import ee
from dotenv import load_dotenv


SCRIPT_DIR = Path(__file__).resolve().parent

### standard box ###
def pathfix(pstr: str, bdir: Path) -> Path:
    path = Path(pstr).expanduser()
    if path.is_absolute():
        return path
    return (bdir / path).resolve()
def boolcheck(value: str, default: bool = False) -> bool: 
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}
#####################

def qabuild(image: ee.Image) -> ee.Image:
    scl = image.select("SCL")

    keepm = (
        scl.eq(4)  #veg
        .Or(scl.eq(5))  #bsoil
        .Or(scl.eq(6))  #waterr
        .Or(scl.eq(7))  #unclas
    )

    return keepm.rename("qa_mask").unmask(0).toUint8() 


def dateScenes(input: Path):
    dates = []
    for tif in sorted(input.rglob("*.tif")):
        dates.append(tif.stem)
    return dates


def fullqa():
    load_dotenv(SCRIPT_DIR / ".env")

    bbox_west = float(os.getenv("BBOX_WEST", 122.22))
    bbox_south = float(os.getenv("BBOX_SOUTH", 16.696))
    bbox_east = float(os.getenv("BBOX_EAST", 122.562))
    bbox_north = float(os.getenv("BBOX_NORTH", 17.168))
    gee_project = os.getenv("GEE_PROJECT", "")

    input_root = pathfix(
        os.getenv(
            "S2_LONGTIMESERIES_ROOT",
            "../../02_Data/01_Raw/Scenes/Sentinel2/longtimeseries",
        ),
        SCRIPT_DIR,
    )
    drive_folder = os.getenv("QA_DRIVE_FOLDER", "Sentinel2_QA_Masks")
    collection_name = os.getenv("S2_QA_COLLECTION", "COPERNICUS/S2_SR_HARMONIZED")
    overwrite_existing = boolcheck(os.getenv("QA_OVERWRITE_EXISTING", "false"))
    search_days = int(os.getenv("QA_SEARCH_DAYS", "5"))

    if gee_project:
        ee.Initialize(project=gee_project)
        print(f"gee proj {gee_project}")
    else:
        ee.Initialize()
        print("gee default")

    if not input_root.exists():
        raise SystemExit(f"input dir missing {input_root}")

    dates = dateScenes(input_root)
    if not dates:
        raise SystemExit(f"no tiff found in {input_root}")

    bbox = ee.Geometry.Rectangle([bbox_west, bbox_south, bbox_east, bbox_north])

    for date_str in dates:
        out_name = f"{date_str}_qa_mask"
        local_expected = (
            pathfix(os.getenv("QA_MASK_ROOT", ""), SCRIPT_DIR)
            if os.getenv("QA_MASK_ROOT")
            else None
        )
        if local_expected and not overwrite_existing:
            existing = local_expected / f"{out_name}.tif"
            if existing.exists():
                print(f"skipping existing")
                continue

        target = ee.Date(date_str)
        start = target.advance(-search_days, "day")
        end = target.advance(search_days + 1, "day")

        collection = (
            ee.ImageCollection(collection_name)
            .filterBounds(bbox)
            .filterDate(start, end)
            .map(
                lambda image: image.set(
                    "date_diff",
                    ee.Number(image.date().difference(target, "day")).abs(),
                )
            )
            .sort("date_diff")
            .sort("CLOUDY_PIXEL_PERCENTAGE")
        )

        count = collection.size().getInfo()
        if count == 0:
            print(f"no scene found for {date_str} within +/- {search_days} days")
            continue

        image = ee.Image(collection.first())
        matched_date = image.date().format("YYYY-MM-dd").getInfo()
        qa_mask = qabuild(image)

        task = ee.batch.Export.image.toDrive(
            image=qa_mask,
            description=out_name,
            folder=drive_folder,
            fileNamePrefix=out_name,
            scale=10,
            region=bbox,
            maxPixels=1e13,
        )
        task.start()
        print(f"started export(s)")


if __name__ == "__main__":
    fullqa()