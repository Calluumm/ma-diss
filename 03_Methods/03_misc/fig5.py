from pathlib import Path
import json
import subprocess
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import fiona
from fiona.transform import transform_geom

root = Path("C:/Users/Student/Desktop/Masters/Dissertation")
predate = "2025-06-02"
postdate = "2025-08-01"
classroot = root / "02_Data" / "02_Processed" / "Sentinel2_Geomorphology_OTB_2025"
changeroot = root / "02_Data" / "02_Processed" / "Sentinel2_ChangeFramework_2025" / "active_channel_mask"
catchmentshp = root / "02_Data" / "01_Raw" / "shp_check" / "Palanan-catchment-unextended.shp"
catchmentcrs = "EPSG:3857"
catchmentpadpx = 110
displaybufferpx = 140
displayframepx = 4
riverlineshp = root / "02_Data" / "01_Raw" / "manual4326-extended.shp"
riverlinecrs = "EPSG:4326"
riverbufferm = 50.0
fallbackbbox = (1150, 900, 2940, 3560)
OUT = root / "05_Figures" / "2025" / "fig5.png"
titleyear = "2025"
figurelabel = "Non-event Monsoon Geomorphic Change"
classcolors = {
    1: (136, 204, 238),  # water
    2: (68, 170, 68),    # vegetation
    3: (255, 221, 85),   # bare
    4: (220, 50, 47),    # cloud
    5: (230, 126, 34),   # channel sediment
    255: (255, 0, 255),  # invalid
}
changecolors = {
    0: (45, 45, 45),      # no change
    1: (0, 166, 81),      # gain
    2: (204, 37, 41),     # loss
    255: (20, 20, 20),    # invalid
}
rivercolor = (70, 176, 232)
classlabels = {
    1: "Water",
    2: "Vegetation",
    3: "Bare sediment",
    4: "Cloud",
    5: "Channel sediment",
    255: "Invalid",
}
defaultcolor = (255, 0, 255)
outsidecolor = (235, 235, 235)
outlinehalocolor = (248, 248, 248)
outlinecolor = (210, 35, 45)
outlinehalopx = 2
outlinelinepx = 1


def loadSingleBand(path: Path) -> np.ndarray:
    arr = np.array(Image.open(path))
    if arr.ndim == 3:
        arr = arr[:, :, 0]
    return arr.astype(np.uint16)


def coloury(arr: np.ndarray, palette: dict[int, tuple[int, int, int]]) -> np.ndarray:
    h, w = arr.shape
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    uniquevals = np.unique(arr)
    for val in uniquevals:
        color = palette.get(int(val), defaultcolor)
        mask = arr == val
        rgb[mask, 0] = color[0]
        rgb[mask, 1] = color[1]
        rgb[mask, 2] = color[2]
    return rgb


def overlayChangeOnClass(classrgb: np.ndarray, change: np.ndarray, river: np.ndarray, change_domain: np.ndarray) -> np.ndarray:
    out = np.zeros((*change.shape, 3), dtype=np.uint8)
    out[river] = rivercolor
    for value in (1, 2):
        out[(change == value) & change_domain] = changecolors[value]
    return out


def classifiedRiverMask(pre: np.ndarray, post: np.ndarray, catchment: np.ndarray) -> np.ndarray:
    active = np.isin(pre, (1, 5)) | np.isin(post, (1, 5))
    return active & catchment


def findZoomBoxes(change: np.ndarray, river: np.ndarray, catchment: np.ndarray) -> list[tuple[int, int, int, int]]:
    height, width = change.shape
    ys, xs = np.where(catchment)
    if xs.size:
        catch_x1, catch_x2 = int(xs.min()), int(xs.max()) + 1
        catch_y1, catch_y2 = int(ys.min()), int(ys.max()) + 1
    else:
        catch_x1, catch_x2, catch_y1, catch_y2 = 0, width, 0, height
    catch_width = catch_x2 - catch_x1
    catch_height = catch_y2 - catch_y1
    return [
        (catch_x1 + int(catch_width * 0.75), catch_y1 + int(catch_height * 0.04), catch_x1 + int(catch_width * 0.88), catch_y1 + int(catch_height * 0.14)),
        (catch_x1 + int(catch_width * 0.60), catch_y1 + int(catch_height * 0.175), catch_x1 + int(catch_width * 0.73), catch_y1 + int(catch_height * 0.285)),
        (catch_x1 + int(catch_width * 0.54), catch_y1 + int(catch_height * 0.423), catch_x1 + int(catch_width * 0.66), catch_y1 + int(catch_height * 0.503)),
    ]


def crop(arr: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
    x1, y1, x2, y2 = bbox
    return arr[y1:y2, x1:x2]


def readGeorefWithGdalinfo(path: Path) -> tuple[tuple[float, float, float, float, float, float], tuple[int, int], str | None]:
    cmd = ["gdalinfo", "-json", str(path)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    meta = json.loads(result.stdout)

    geotransform = meta.get("geoTransform")
    if not geotransform or len(geotransform) != 6:
        raise RuntimeError(f"Could not read geoTransform from {path}")

    size = meta.get("size")
    if not size or len(size) != 2:
        raise RuntimeError(f"Could not read raster size from {path}")

    targetcrs = None
    stac = meta.get("stac")
    if isinstance(stac, dict):
        epsg = stac.get("proj:epsg")
        if isinstance(epsg, int):
            targetcrs = f"EPSG:{epsg}"

    coord = meta.get("coordinateSystem")
    if targetcrs is None and isinstance(coord, dict):
        targetcrs = coord.get("wkt")

    return tuple(float(v) for v in geotransform), (int(size[0]), int(size[1])), targetcrs


def worldToPixel(x: float, y: float, gt: tuple[float, float, float, float, float, float]) -> tuple[float, float]:
    gt0, gt1, gt2, gt3, gt4, gt5 = gt
    det = gt1 * gt5 - gt2 * gt4
    if abs(det) < 1e-15:
        raise RuntimeError("Invalid geotransform (determinant is zero)")

    dx = x - gt0
    dy = y - gt3
    px = (dx * gt5 - dy * gt2) / det
    py = (dy * gt1 - dx * gt4) / det
    return px, py


def buildCatchmentMask(
    shppath: Path,
    rastercrs: str | None,
    gt: tuple[float, float, float, float, float, float],
    rastersize: tuple[int, int],
    fallbackshapecrs: str | None,
) -> np.ndarray:
    width, height = rastersize
    maskimg = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(maskimg)

    with fiona.open(shppath) as src:
        srccrs = fallbackshapecrs or src.crs_wkt or src.crs
        srccrstext = str(srccrs).strip() if srccrs is not None else ""
        if srccrstext in {"", "{}"}:
            srccrs = None

        for feature in src:
            geom = feature.get("geometry")
            if not geom:
                continue

            geomtype = geom.get("type")

            if srccrs and rastercrs:
                geom = transform_geom(srccrs, rastercrs, geom, precision=6)
            gtype = geom.get("type") if hasattr(geom, "get") else None
            if not gtype and geomtype:
                gtype = geomtype
            coords = geom.get("coordinates") if hasattr(geom, "get") else None
            if not coords:
                continue

            if gtype == "Polygon":
                polygons = [coords]
            elif gtype == "MultiPolygon":
                polygons = coords
            else:
                continue

            for poly in polygons:
                if not poly:
                    continue

                exterior = [worldToPixel(float(x), float(y), gt) for x, y in poly[0]]
                if len(exterior) >= 3:
                    draw.polygon(exterior, fill=255)

                for hole in poly[1:]:
                    holepts = [worldToPixel(float(x), float(y), gt) for x, y in hole]
                    if len(holepts) >= 3:
                        draw.polygon(holepts, fill=0)
            break

    return np.array(maskimg, dtype=np.uint8)


def bboxFromMask(mask: np.ndarray, pad: int) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask > 0)
    if xs.size == 0 or ys.size == 0:
        raise RuntimeError("Catchment mask is empty")

    x1 = max(int(xs.min()) - pad, 0)
    y1 = max(int(ys.min()) - pad, 0)
    x2 = min(int(xs.max()) + pad + 1, mask.shape[1])
    y2 = min(int(ys.max()) + pad + 1, mask.shape[0])
    return x1, y1, x2, y2


def boundaryFromMask(mask: np.ndarray) -> np.ndarray:
    inside = mask > 0
    if inside.shape[0] < 3 or inside.shape[1] < 3:
        return inside

    eroded = np.zeros_like(inside)
    eroded[1:-1, 1:-1] = (
        inside[1:-1, 1:-1]
        & inside[:-2, 1:-1]
        & inside[2:, 1:-1]
        & inside[1:-1, :-2]
        & inside[1:-1, 2:]
    )
    return inside & (~eroded)


def applyOutsideTint(rgb: np.ndarray, insidemask: np.ndarray, outsidecolor: tuple[int, int, int]) -> np.ndarray:
    out = rgb.copy()
    outside = ~insidemask
    out[outside, 0] = outsidecolor[0]
    out[outside, 1] = outsidecolor[1]
    out[outside, 2] = outsidecolor[2]
    return out


def resizeRgb(rgb: np.ndarray, width: int, height: int) -> Image.Image:
    return Image.fromarray(rgb, mode="RGB").resize((width, height), Image.Resampling.NEAREST)


def dilateMask(mask: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0:
        return mask.copy()

    out = mask.copy()
    for _ in range(radius):
        expanded = out.copy()
        expanded[1:, :] |= out[:-1, :]
        expanded[:-1, :] |= out[1:, :]
        expanded[:, 1:] |= out[:, :-1]
        expanded[:, :-1] |= out[:, 1:]
        expanded[1:, 1:] |= out[:-1, :-1]
        expanded[1:, :-1] |= out[:-1, 1:]
        expanded[:-1, 1:] |= out[1:, :-1]
        expanded[:-1, :-1] |= out[1:, 1:]
        out = expanded
    return out


def overlayOutline(
    rgb: np.ndarray,
    boundarymask: np.ndarray,
    outw: int,
    outh: int,
    halocolor: tuple[int, int, int],
    linecolor: tuple[int, int, int],
    halopx: int,
    linepx: int,
) -> Image.Image:
    base = np.array(resizeRgb(rgb, outw, outh), dtype=np.uint8)
    bmask = np.array(
        Image.fromarray((boundarymask.astype(np.uint8) * 255), mode="L").resize((outw, outh), Image.Resampling.NEAREST)
    ) > 0

    halo = dilateMask(bmask, halopx)
    line = dilateMask(bmask, linepx)

    base[halo, 0] = halocolor[0]
    base[halo, 1] = halocolor[1]
    base[halo, 2] = halocolor[2]

    base[line, 0] = linecolor[0]
    base[line, 1] = linecolor[1]
    base[line, 2] = linecolor[2]
    return Image.fromarray(base, mode="RGB")


def smoothMask(mask: np.ndarray, outw: int, outh: int) -> np.ndarray:
    img = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
    return np.array(img.resize((outw, outh), Image.Resampling.LANCZOS), dtype=np.uint8)


def renderPanelImage(
    rgb: np.ndarray,
    catchmentmask: np.ndarray,
    displaymask: np.ndarray,
    outw: int,
    outh: int,
) -> Image.Image:
    base = np.array(resizeRgb(rgb, outw, outh), dtype=np.float32)

    displayalpha = smoothMask(displaymask, outw, outh).astype(np.float32) / 255.0
    displayalpha = np.clip(displayalpha, 0.0, 1.0)

    outside = np.zeros_like(base)
    outside[:, :, 0] = outsidecolor[0]
    outside[:, :, 1] = outsidecolor[1]
    outside[:, :, 2] = outsidecolor[2]

    comp = base * displayalpha[:, :, None] + outside * (1.0 - displayalpha[:, :, None])
    compu8 = np.clip(comp, 0, 255).astype(np.uint8)

    catchmentsoft = smoothMask(catchmentmask, outw, outh)
    catchmentbool = catchmentsoft > 127
    boundary = boundaryFromMask(catchmentbool)
    halo = dilateMask(boundary, outlinehalopx)
    line = dilateMask(boundary, outlinelinepx)

    compu8[halo, 0] = outlinehalocolor[0]
    compu8[halo, 1] = outlinehalocolor[1]
    compu8[halo, 2] = outlinehalocolor[2]

    compu8[line, 0] = outlinecolor[0]
    compu8[line, 1] = outlinecolor[1]
    compu8[line, 2] = outlinecolor[2]

    return Image.fromarray(compu8, mode="RGB")


def formatSignedM2(v: float) -> str:
    sign = "+" if v >= 0 else "-"
    return f"{sign}{abs(v):,.0f} m2"


def metersPerPixel(gt: tuple[float, float, float, float, float, float], h: int) -> float:
    centerlat = gt[3] + gt[5] * (h * 0.5)
    latrad = float(np.deg2rad(centerlat))
    mperdeglat = 111320.0
    mperdeglon = 111320.0 * float(np.cos(latrad))
    pxxm = abs(gt[1]) * mperdeglon
    pxym = abs(gt[5]) * mperdeglat
    pxm = max((pxxm + pxym) * 0.5, 0.1)
    return pxm


def pixelAreaM2(gt: tuple[float, float, float, float, float, float], h: int) -> float:
    centerlat = gt[3] + gt[5] * (h * 0.5)
    latrad = float(np.deg2rad(centerlat))
    mperdeglat = 111320.0
    mperdeglon = 111320.0 * float(np.cos(latrad))
    pxxm = abs(gt[1]) * mperdeglon
    pxym = abs(gt[5]) * mperdeglat
    return max(pxxm * pxym, 0.01)


def buildLineMask(
    shppath: Path,
    rastercrs: str | None,
    gt: tuple[float, float, float, float, float, float],
    rastersize: tuple[int, int],
    fallbackshapecrs: str | None,
) -> np.ndarray:
    width, height = rastersize
    maskimg = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(maskimg)

    with fiona.open(shppath) as src:
        srccrs = fallbackshapecrs or src.crs_wkt or src.crs
        srccrstext = str(srccrs).strip() if srccrs is not None else ""
        if srccrstext in {"", "{}"}:
            srccrs = None

        for feature in src:
            geom = feature.get("geometry")
            if not geom:
                continue

            geomtype = geom.get("type")
            if srccrs and rastercrs:
                geom = transform_geom(srccrs, rastercrs, geom, precision=6)

            gtype = geom.get("type") if hasattr(geom, "get") else None
            if not gtype and geomtype:
                gtype = geomtype
            coords = geom.get("coordinates") if hasattr(geom, "get") else None
            if not coords:
                continue

            if gtype == "LineString":
                lines = [coords]
            elif gtype == "MultiLineString":
                lines = coords
            else:
                continue

            for line in lines:
                pts = [worldToPixel(float(x), float(y), gt) for x, y in line]
                if len(pts) >= 2:
                    draw.line(pts, fill=255, width=1)

    return np.array(maskimg, dtype=np.uint8)


def deriveChangeFromClass(pre: np.ndarray, post: np.ndarray) -> np.ndarray:
    invalid = (pre == 255) | (post == 255) | (pre == 4) | (post == 4)
    preactive = (pre == 1) | (pre == 5)
    postactive = (post == 1) | (post == 5)

    change = np.zeros(pre.shape, dtype=np.uint16)
    change[(~invalid) & (~preactive) & postactive] = 1
    change[(~invalid) & preactive & (~postactive)] = 2
    change[invalid] = 255
    return change




preclasspath = classroot / predate / f"{predate}_class_map.tif"
postclasspath = classroot / postdate / f"{postdate}_class_map.tif"
changepath = changeroot / f"{predate}_to_{postdate}" / f"change_class_clean_{predate}_to_{postdate}.tif"

pre = loadSingleBand(preclasspath)
post = loadSingleBand(postclasspath)
if changepath.exists():
    change = loadSingleBand(changepath)
else:
    change = deriveChangeFromClass(pre, post)

if pre.shape != post.shape or pre.shape != change.shape:
    raise RuntimeError("Input rasters do not share the same shape; cannot make aligned panel extent")

bbox = fallbackbbox
fullinsidemask = np.ones_like(pre, dtype=bool)
fulldisplaymask = np.ones_like(pre, dtype=bool)
fullrivercorridor = np.ones_like(pre, dtype=bool)
pxaream2 = 100.0

gt, (w, h), rastercrs = readGeorefWithGdalinfo(preclasspath)
if (h, w) != pre.shape:
    raise RuntimeError("Raster size from GDAL metadata does not match loaded image array")

pxaream2 = pixelAreaM2(gt, h)

catchmentmask = buildCatchmentMask(catchmentshp, rastercrs, gt, (w, h), catchmentcrs)
fullinsidemask = catchmentmask > 0
fulldisplaymask = dilateMask(fullinsidemask, max(0, displaybufferpx))
bbox = bboxFromMask(fulldisplaymask.astype(np.uint8) * 255, max(0, displayframepx))

linemask = buildLineMask(riverlineshp, rastercrs, gt, (w, h), riverlinecrs)
if np.any(linemask > 0):
    pxm = metersPerPixel(gt, h)
    bufferpx = max(1, int(np.ceil(riverbufferm / pxm)))
    fullrivercorridor = dilateMask(linemask > 0, bufferpx)

precrop = crop(pre, bbox)
postcrop = crop(post, bbox)
changecrop = crop(change, bbox)
insidecrop = crop(fullinsidemask.astype(np.uint8), bbox) > 0
displaycrop = crop(fulldisplaymask.astype(np.uint8), bbox) > 0
rivercrop = crop(fullrivercorridor.astype(np.uint8), bbox) > 0
classifiedrivercrop = classifiedRiverMask(precrop, postcrop, insidecrop) & rivercrop

changeeval = changecrop.copy()
changeeval[~insidecrop] = 255
outsidecorridorchange = ((changeeval == 1) | (changeeval == 2)) & (~rivercrop)
changeeval[outsidecorridorchange] = 0

prergb = coloury(precrop, classcolors)
postrgb = coloury(postcrop, classcolors)
changergb = overlayChangeOnClass(postrgb, changeeval, classifiedrivercrop, rivercrop)

metricdomain = insidecrop & rivercrop
validcls = (precrop != 255) & (postcrop != 255) & (precrop != 4) & (postcrop != 4)
domain = metricdomain & validcls

watergainpx = int(np.sum(domain & (precrop != 1) & (postcrop == 1)))
waterlosspx = int(np.sum(domain & (precrop == 1) & (postcrop != 1)))
sedimentgainpx = int(np.sum(domain & (precrop != 5) & (postcrop == 5)))
sedimentlosspx = int(np.sum(domain & (precrop == 5) & (postcrop != 5)))

waternetm2 = (watergainpx - waterlosspx) * pxaream2
sedimentnetm2 = (sedimentgainpx - sedimentlosspx) * pxaream2
combinednetm2 = waternetm2 + sedimentnetm2

canvasw, canvash = 2600, 1400
bg = (245, 245, 245)
panelbg = (255, 255, 255)
text = (25, 25, 25)
muted = (90, 90, 90)

canvas = Image.new("RGB", (canvasw, canvash), bg)
draw = ImageDraw.Draw(canvas)

try:
    fonttitle = ImageFont.truetype("arial.ttf", 56)
    fontsub = ImageFont.truetype("arial.ttf", 34)
    fontbody = ImageFont.truetype("arial.ttf", 28)
except OSError:
    fonttitle = ImageFont.load_default()
    fontsub = ImageFont.load_default()
    fontbody = ImageFont.load_default()

draw.text((60, 30), f"{figurelabel} ({titleyear})", fill=text, font=fonttitle)
draw.text((60, 95), f"Window: {predate} to {postdate} | Focus: active channel (water + channel sediment)", fill=muted, font=fontsub)

panelw, panelh = 680, 980
y0 = 180
xpre = 60
xpost = xpre + panelw + 40
xchange = xpost + panelw + 40

for x, title, rgb, z in [
    (xpre, f"A. Pre-event classification ({predate})", prergb, None),
    (xpost, f"B. Post-event classification ({postdate})", postrgb, None),
    (xchange, "C. Active-channel change", changergb, findZoomBoxes(changeeval, rivercrop, insidecrop)),
]:
    draw.rounded_rectangle((x, y0, x + panelw, y0 + panelh), radius=18, fill=panelbg, outline=(210, 210, 210), width=2)
    draw.text((x + 20, y0 + 16), title, fill=text, font=fontsub)
    sourceheight, sourcewidth = rgb.shape[:2]
    mapw, maph = panelw - 40, panelh - 120
    im = renderPanelImage(rgb, insidecrop, displaycrop, mapw, maph)
    canvas.paste(im, (x + 20, y0 + 80))
    if z is not None:
        insetw, inseth = 220, 250
        insetx = x + panelw + 10
        for index, (zx1, zy1, zx2, zy2) in enumerate(z):
            sx1 = int(zx1 * mapw / sourcewidth)
            sy1 = int(zy1 * maph / sourceheight)
            sx2 = int(zx2 * mapw / sourcewidth)
            sy2 = int(zy2 * maph / sourceheight)
            boxleft, boxtop = x + 20 + sx1, y0 + 80 + sy1
            boxright, boxbottom = x + 20 + sx2, y0 + 80 + sy2
            insety = y0 + 95 + index * 285
            draw.rectangle((boxleft, boxtop, boxright, boxbottom), outline=(210, 35, 45), width=5)
            inset = im.crop((sx1, sy1, sx2, sy2)).resize((insetw, inseth), Image.Resampling.NEAREST)
            draw.line((boxright, (boxtop + boxbottom) // 2, insetx, insety + inseth // 2), fill=(210, 35, 45), width=5)
            draw.rectangle((insetx - 4, insety - 4, insetx + insetw + 4, insety + inseth + 4), fill=(255, 255, 255), outline=(210, 35, 45), width=5)
            canvas.paste(inset, (insetx, insety))

stripy = y0 + panelh + 20
striph = 180
draw.rounded_rectangle((60, stripy, canvasw - 60, stripy + striph), radius=14, fill=panelbg, outline=(210, 210, 210), width=2)

draw.text((90, stripy + 20), f"Water net change: {formatSignedM2(waternetm2)}", fill=(0, 120, 60), font=fontbody)
draw.text((90, stripy + 62), f"Sediment net change: {formatSignedM2(sedimentnetm2)}", fill=(170, 30, 30), font=fontbody)
draw.text((90, stripy + 104), f"Combined active-channel net change: {formatSignedM2(combinednetm2)}", fill=muted, font=fontbody)

legendx = 1200
draw.text((legendx, stripy + 12), "Class legend (Panels A and B):", fill=text, font=fontbody)

class_positions = [(1200, 1), (1480, 2), (1760, 3), (1200, 4), (1480, 5), (1760, 255)]
for class_x, value in class_positions:
    class_y = stripy + 52 if value <= 3 else stripy + 102
    draw.rectangle((class_x, class_y, class_x + 24, class_y + 24), fill=classcolors[value], outline=(30, 30, 30))
    draw.text((class_x + 32, class_y - 4), classlabels[value], fill=text, font=fontbody)

legendx = 2050
draw.text((legendx, stripy + 12), "Change legend (Panel C):", fill=text, font=fontbody)

legenditems = [
    ("Gain (0 -> 1)", changecolors[1]),
    ("Loss (1 -> 0)", changecolors[2]),
    ("River corridor", rivercolor),
]

lx, ly = legendx, stripy + 56
for label, col in legenditems:
    draw.rectangle((lx, ly, lx + 28, ly + 28), fill=col, outline=(30, 30, 30))
    draw.text((lx + 40, ly + 2), label, fill=text, font=fontbody)
    ly += 38

OUT.parent.mkdir(parents=True, exist_ok=True)
canvas.save(OUT, format="PNG")
print(f"Wrote figure: {OUT}")

