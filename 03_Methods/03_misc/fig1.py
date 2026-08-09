import json
import subprocess
from pathlib import Path

import fiona
from fiona.transform import transform_geom
from PIL import Image, ImageDraw, ImageFont

root = Path("C:/Users/Student/Desktop/Masters/Dissertation")

nationalcatchments = root / "02_Data" / "03_External" / "Philippines_GIS_catchments_n128" / "Philippines_GIS_catchments_n128" / "Philippines_GIS_catchments_n128.shp"
palanancatchment = root / "02_Data" / "01_Raw" / "shp_check" / "Palanan-catchment-unextended.shp"
palanancatchmentcrs = "EPSG:3857"
streamlines = root / "02_Data" / "01_Raw" / "stream_lines.shp"
streamcrs = "EPSG:3857"
dem = root / "02_Data" / "01_Raw" / "DEM_30m" / "output_SRTMGL1.tif"
satscene = root / "02_Data" / "01_Raw" / "Scenes" / "Sentinel2" / "2025" / "2025-11-12.tif"
outpath = root / "05_Figures" / "figure1_palanan_context_v1.png"
OUT = outpath
tmpdir = root / "05_Figures" / "_tmp_fig1"
luzonbbox = (119.0, 14.0, 124.0, 20.1)
phbbox = (116.0, 4.0, 127.0, 21.5)


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates.extend([Path("C:/Windows/Fonts/arialbd.ttf"), Path("C:/Windows/Fonts/segoeuib.ttf")])
    candidates.extend([Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/segoeui.ttf")])
    for p in candidates:
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                continue
    return ImageFont.load_default()


def runCmd(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def readSceneBounds(tif: Path) -> tuple[float, float, float, float]:
    result = subprocess.run(["gdalinfo", "-json", str(tif)], check=True, capture_output=True, text=True)
    meta = json.loads(result.stdout)
    cc = meta["cornerCoordinates"]
    ul, lr = cc["upperLeft"], cc["lowerRight"]
    return float(ul[0]), float(lr[1]), float(lr[0]), float(ul[1])


def polyAreaAbs(ring: list[tuple[float, float]]) -> float:
    if len(ring) < 3:
        return 0.0
    s = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        s += (x1 * y2) - (x2 * y1)
    return abs(s) * 0.5
def loadPolygons4326(shp: Path, fallbackcrs: str | None = None) -> list[list[list[tuple[float, float]]]]:
    polys: list[list[list[tuple[float, float]]]] = []
    with fiona.open(shp) as src:
        srccrs = src.crs_wkt or src.crs
        srccrstext = str(srccrs).strip() if srccrs is not None else ""
        if srccrstext in {"", "{}"}:
            srccrs = fallbackcrs

        for feat in src:
            geom = feat["geometry"]
            if not geom:
                continue
            gtype = geom.get("type") if hasattr(geom, "get") else None
            if srccrs:
                geom = transform_geom(srccrs, "EPSG:4326", geom, precision=6)
                if hasattr(geom, "get") and not geom.get("type") and gtype:
                    geom["type"] = gtype
            gtype = geom.get("type") if hasattr(geom, "get") else gtype
            coords = geom.get("coordinates") if hasattr(geom, "get") else None
            if not coords:
                continue
            if gtype == "Polygon":
                polys.append([[(float(x), float(y)) for x, y in ring] for ring in coords])
            elif gtype == "MultiPolygon":
                for poly in coords:
                    polys.append([[(float(x), float(y)) for x, y in ring] for ring in poly])
    return polys
def loadLines4326(shp: Path, fallbackcrs: str | None = None) -> list[list[tuple[float, float]]]:
    lines: list[list[tuple[float, float]]] = []
    with fiona.open(shp) as src:
        srccrs = src.crs_wkt or src.crs
        srccrstext = str(srccrs).strip() if srccrs is not None else ""
        if srccrstext in {"", "{}"}:
            srccrs = fallbackcrs

        for feat in src:
            geom = feat["geometry"]
            if not geom:
                continue
            gtype = geom.get("type") if hasattr(geom, "get") else None
            if srccrs:
                geom = transform_geom(srccrs, "EPSG:4326", geom, precision=6)
                if hasattr(geom, "get") and not geom.get("type") and gtype:
                    geom["type"] = gtype
            gtype = geom.get("type") if hasattr(geom, "get") else gtype
            coords = geom.get("coordinates") if hasattr(geom, "get") else None
            if not coords:
                continue
            if gtype == "LineString":
                lines.append([(float(x), float(y)) for x, y in coords])
            elif gtype == "MultiLineString":
                for part in coords:
                    lines.append([(float(x), float(y)) for x, y in part])
    return lines


def getNamedPolygon(shp: Path, field: str, value: str) -> list[list[tuple[float, float]]]:
    with fiona.open(shp) as src:
        srccrs = src.crs_wkt or src.crs
        for feat in src:
            props = feat["properties"]
            if str(props.get(field, "")).strip().lower() != value.lower():
                continue
            geom = feat["geometry"]
            if not geom:
                continue
            gtype = geom.get("type") if hasattr(geom, "get") else None
            geom = transform_geom(srccrs, "EPSG:4326", geom, precision=6)
            if hasattr(geom, "get") and not geom.get("type") and gtype:
                geom["type"] = gtype
            if geom["type"] == "Polygon":
                return [[(float(x), float(y)) for x, y in ring] for ring in geom["coordinates"]]
            if geom["type"] == "MultiPolygon":
                cands = [[(float(x), float(y)) for x, y in poly[0]] for poly in geom["coordinates"] if poly and poly[0]]
                if cands:
                    largest = max(cands, key=polyAreaAbs)
                    return [largest]
    raise RuntimeError(f"Could not find {value} in {shp}")


def boundsOfRings(rings: list[list[tuple[float, float]]]) -> tuple[float, float, float, float]:
    xs = [x for ring in rings for x, _ in ring]
    ys = [y for ring in rings for _, y in ring]
    return min(xs), min(ys), max(xs), max(ys)


def clampBbox(b: tuple[float, float, float, float], lim: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = b
    lx1, ly1, lx2, ly2 = lim
    return max(x1, lx1), max(y1, ly1), min(x2, lx2), min(y2, ly2)


def lonlatToXy(lon: float, lat: float, bbox: tuple[float, float, float, float], x0: int, y0: int, w: int, h: int) -> tuple[float, float]:
    xmin, ymin, xmax, ymax = bbox
    fx = (lon - xmin) / (xmax - xmin)
    fy = (ymax - lat) / (ymax - ymin)
    return x0 + fx * w, y0 + fy * h
def drawPoly(draw: ImageDraw.ImageDraw, rings: list[list[tuple[float, float]]], bbox: tuple[float, float, float, float], x0: int, y0: int, w: int, h: int, fill=None, outline=None, width: int = 1) -> None:
    if not rings:
        return
    ext = [lonlatToXy(x, y, bbox, x0, y0, w, h) for x, y in rings[0]]
    if len(ext) < 3:
        return
    draw.polygon(ext, fill=fill, outline=outline)
    if outline and width > 1:
        draw.line(ext + [ext[0]], fill=outline, width=width)
def drawLines(draw: ImageDraw.ImageDraw, lines: list[list[tuple[float, float]]], bbox: tuple[float, float, float, float], x0: int, y0: int, w: int, h: int, color: tuple[int, int, int], width: int) -> None:
    xmin, ymin, xmax, ymax = bbox
    for line in lines:
        if len(line) < 2:
            continue
        lx = [p[0] for p in line]
        ly = [p[1] for p in line]
        if max(lx) < xmin or min(lx) > xmax or max(ly) < ymin or min(ly) > ymax:
            continue
        pts = [lonlatToXy(x, y, bbox, x0, y0, w, h) for x, y in line]
        draw.line(pts, fill=color, width=width)


def cropRgbPng(scene: Path, bbox: tuple[float, float, float, float], outpng: Path) -> None:
    ulx, uly, lrx, lry = bbox[0], bbox[3], bbox[2], bbox[1]
    runCmd([
        "gdal_translate",
        "-of",
        "PNG",
        "-b",
        "3",
        "-b",
        "2",
        "-b",
        "1",
        "-scale_1",
        "151",
        "1200",
        "0",
        "255",
        "-scale_2",
        "314",
        "1400",
        "0",
        "255",
        "-scale_3",
        "565",
        "1800",
        "0",
        "255",
        "-exponent",
        "0.75",
        "-projwin",
        f"{ulx}",
        f"{uly}",
        f"{lrx}",
        f"{lry}",
        str(scene),
        str(outpng),
    ])


def buildHillshadePng(dem: Path, bbox: tuple[float, float, float, float], outpng: Path, tmpdem: Path, tmphs: Path) -> None:
    ulx, uly, lrx, lry = bbox[0], bbox[3], bbox[2], bbox[1]
    runCmd([
        "gdal_translate",
        "-of",
        "GTiff",
        "-projwin",
        f"{ulx}",
        f"{uly}",
        f"{lrx}",
        f"{lry}",
        str(dem),
        str(tmpdem),
    ])
    runCmd([
        "gdaldem",
        "hillshade",
        str(tmpdem),
        str(tmphs),
        "-az",
        "315",
        "-alt",
        "45",
        "-z",
        "1.7",
    ])
    runCmd([
        "gdal_translate",
        "-of",
        "PNG",
        "-scale",
        str(tmphs),
        str(outpng),
    ])


def simpleScaleBar(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, label: str, textcolor: tuple[int, int, int], dark=(20, 20, 20), light=(240, 240, 240)) -> None:
    h = 10
    draw.rectangle((x, y, x + w, y + h), fill=dark, outline=(90, 90, 90), width=1)
    draw.rectangle((x, y, x + w // 2, y + h), fill=light)
    draw.text((x + w + 8, y - 4), label, fill=textcolor)


def drawHaloText(draw: ImageDraw.ImageDraw, x: float, y: float, text: str, font, fill: tuple[int, int, int], halo: tuple[int, int, int]) -> None:
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)]:
        draw.text((x + dx, y + dy), text, fill=halo, font=font)
    draw.text((x, y), text, fill=fill, font=font)


def drawNorthArrow(draw: ImageDraw.ImageDraw, x: int, y: int, size: int, color: tuple[int, int, int], font) -> None:
    stemh = int(size * 0.7)
    headh = int(size * 0.4)
    cx = x + size // 2
    draw.line((cx, y + stemh, cx, y + 6), fill=color, width=2)
    draw.polygon([(cx, y), (cx - headh // 2, y + headh), (cx + headh // 2, y + headh)], fill=color)
    draw.text((cx - int(size * 0.15), y + stemh + 6), "N", fill=color, font=font)


def main() -> None:
    tmpdir.mkdir(parents=True, exist_ok=True)
    satpng = tmpdir / "sat_main.png"
    trunkpng = tmpdir / "sat_trunk.png"
    demcrop = tmpdir / "demcrop.tif"
    demhs = tmpdir / "demhs.tif"
    dempng = tmpdir / "demhs.png"

    nationalpolys = loadPolygons4326(nationalcatchments)
    catchpolys = loadPolygons4326(palanancatchment, palanancatchmentcrs)
    catchrings = max(catchpolys, key=lambda r: polyAreaAbs(r[0] if r else []))
    streams = loadLines4326(streamlines, streamcrs)

    catchbbox = boundsOfRings(catchrings)
    scenebbox = readSceneBounds(satscene)

    cw = catchbbox[2] - catchbbox[0]
    ch = catchbbox[3] - catchbbox[1]

    satbbox = (
        catchbbox[0] - 0.42 * cw,
        catchbbox[1] - 0.32 * ch,
        catchbbox[2] + 0.42 * cw,
        catchbbox[3] + 0.30 * ch,
    )
    satbbox = clampBbox(satbbox, scenebbox)

    trunkbbox = (
        catchbbox[0] + 0.50 * cw,
        catchbbox[1] + 0.56 * ch,
        catchbbox[0] + 0.86 * cw,
        catchbbox[3],
    )
    trunkbbox = clampBbox(trunkbbox, satbbox)

    leftbbox = (
        catchbbox[0] - 0.12 * cw,
        catchbbox[1] - 0.10 * ch,
        catchbbox[2] + 0.12 * cw,
        catchbbox[3] + 0.10 * ch,
    )
    leftbbox = clampBbox(leftbbox, scenebbox)

    cropRgbPng(satscene, satbbox, satpng)
    cropRgbPng(satscene, trunkbbox, trunkpng)
    buildHillshadePng(dem, leftbbox, dempng, demcrop, demhs)

    satimg = Image.open(satpng).convert("RGB")
    trunkimg = Image.open(trunkpng).convert("RGB")
    hsimg = Image.open(dempng).convert("L")

    canvasw, canvash = 2300, 1320
    canvas = Image.new("RGB", (canvasw, canvash), (247, 247, 247))
    draw = ImageDraw.Draw(canvas)

    ftitle = font(50, bold=True)
    fsub = font(24)
    flbl = font(32, bold=True)
    fsmall = font(20)

    draw.text((52, 24), "Palanan Catchment Location and Trunk-River Context", fill=(20, 20, 20), font=ftitle)
    draw.text((52, 84), "Terrain locator (left) and satellite context with trunk zoom inset (right)", fill=(92, 92, 92), font=fsub)

    leftx, lefty, leftw, lefth = 52, 138, 960, 1130
    rightx, righty, rightw, righth = 1042, 138, 1206, 1130

    draw.rectangle((leftx, lefty, leftx + leftw, lefty + lefth), fill=(255, 255, 255), outline=(188, 188, 188), width=2)
    draw.rectangle((rightx, righty, rightx + rightw, righty + righth), fill=(255, 255, 255), outline=(188, 188, 188), width=2)

    lx0, ly0 = leftx + 34, lefty + 96
    lw, lh = leftw - 120, lefth - 152
    hsfit = hsimg.resize((lw, lh), Image.Resampling.BILINEAR)
    hsrgb = Image.merge("RGB", (hsfit, hsfit, hsfit))

    mask = Image.new("L", (lw, lh), 0)
    mdraw = ImageDraw.Draw(mask)
    ext = [lonlatToXy(x, y, leftbbox, 0, 0, lw, lh) for x, y in catchrings[0]]
    if len(ext) >= 3:
        mdraw.polygon(ext, fill=255)

    leftpanel = Image.new("RGB", (lw, lh), (255, 255, 255))
    leftpanel.paste(hsrgb, (0, 0), mask)

    streamoverlay = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
    streamdraw = ImageDraw.Draw(streamoverlay)
    drawLines(streamdraw, streams, leftbbox, 0, 0, lw, lh, color=(45, 140, 235, 255), width=2)
    streamoverlay.putalpha(mask)
    leftpanelrgba = leftpanel.convert("RGBA")
    leftpanelrgba.alpha_composite(streamoverlay)
    leftpanel = leftpanelrgba.convert("RGB")

    leftborder = ImageDraw.Draw(leftpanel)
    leftborder.line(ext + [ext[0]], fill=(95, 95, 95), width=3)

    canvas.paste(leftpanel, (lx0, ly0))

    draw.text((leftx + 18, lefty + 20), "Palanan terrain and drainage", fill=(45, 45, 45), font=flbl)

    pinw, pinh = 330, 430
    pinx = leftx + leftw - pinw - 18
    piny = lefty + 34

    for rings in nationalpolys:
        xs = [x for ring in rings for x, _ in ring]
        ys = [y for ring in rings for _, y in ring]
        if max(xs) < phbbox[0] or min(xs) > phbbox[2] or max(ys) < phbbox[1] or min(ys) > phbbox[3]:
            continue
        drawPoly(draw, rings, phbbox, pinx + 8, piny + 8, pinw - 16, pinh - 16, fill=(250, 250, 250), outline=(145, 145, 145), width=1)

    bx1, by1 = lonlatToXy(catchbbox[0], catchbbox[3], phbbox, pinx + 8, piny + 8, pinw - 16, pinh - 16)
    bx2, by2 = lonlatToXy(catchbbox[2], catchbbox[1], phbbox, pinx + 8, piny + 8, pinw - 16, pinh - 16)
    draw.rectangle((bx1, by1, bx2, by2), outline=(220, 35, 45), width=3)
    drawNorthArrow(draw, pinx + 6, piny + 6, 34, (55, 55, 55), fsmall)

    rx0, ry0 = rightx + 20, righty + 20
    rw, rh = rightw - 40, righth - 40
    satfit = satimg.resize((rw, rh), Image.Resampling.BILINEAR)
    canvas.paste(satfit, (rx0, ry0))

    satext = [lonlatToXy(x, y, satbbox, rx0, ry0, rw, rh) for x, y in catchrings[0]]
    if len(satext) >= 3:
        draw.line(satext + [satext[0]], fill=(235, 38, 46), width=3)

    insetw, inseth = 320, 400
    insetx = rx0 + rw - insetw - 28
    insety = ry0 + 24
    draw.rectangle((insetx - 8, insety - 8, insetx + insetw + 8, insety + inseth + 8), fill=(250, 250, 250), outline=(235, 235, 235), width=2)
    trunkfit = trunkimg.resize((insetw, inseth), Image.Resampling.BILINEAR)
    canvas.paste(trunkfit, (insetx, insety))
    draw.rectangle((insetx + 14, insety + 14, insetx + insetw - 14, insety + inseth - 14), outline=(235, 38, 46), width=3)

    draw.text((rightx + 20, righty + 20), "Satellite context + trunk zoom", fill=(255, 255, 255), font=flbl)
    draw.text((rx0 + 26, ry0 + rh - 64), "Palanan", fill=(255, 255, 255), font=flbl)

    riverlon = trunkbbox[0] + 0.58 * (trunkbbox[2] - trunkbbox[0])
    riverlat = trunkbbox[1] + 0.38 * (trunkbbox[3] - trunkbbox[1])
    rpx, rpy = lonlatToXy(riverlon, riverlat, satbbox, rx0, ry0, rw, rh)
    labelx = insetx - 225
    labely = insety + 130
    draw.line((labelx + 155, labely + 16, rpx, rpy), fill=(20, 20, 20), width=2)
    drawHaloText(draw, labelx, labely, "Palanan River", fsub, (20, 20, 20), (240, 240, 240))

    drawNorthArrow(draw, leftx + 24, lefty + 58, 54, (40, 40, 40), fsub)
    drawNorthArrow(draw, rx0 + 12, ry0 + 18, 54, (245, 245, 245), fsub)
    drawNorthArrow(draw, insetx + 10, insety + 12, 46, (245, 245, 245), fsmall)

    simpleScaleBar(draw, leftx + 56, lefty + lefth - 48, 170, "10 km", textcolor=(40, 40, 40))
    simpleScaleBar(draw, rightx + rightw - 250, righty + righth - 52, 170, "5 km", textcolor=(255, 255, 255))
    simpleScaleBar(draw, insetx + insetw - 155, insety + 16, 120, "1 km", textcolor=(255, 255, 255))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT, format="PNG")

    satpng.unlink(missing_ok=True)
    trunkpng.unlink(missing_ok=True)
    dempng.unlink(missing_ok=True)
    demcrop.unlink(missing_ok=True)
    demhs.unlink(missing_ok=True)
    try:
        tmpdir.rmdir()
    except OSError:
        pass

    print(f"Wrote figure: {outpath}")


if __name__ == "__main__":
    main()
