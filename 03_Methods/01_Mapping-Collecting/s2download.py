import ee
import os
from dotenv import load_dotenv

load_dotenv()

BBOX_WEST = float(os.getenv('BBOX_WEST', 122.22))
BBOX_SOUTH = float(os.getenv('BBOX_SOUTH', 16.694))
BBOX_EAST = float(os.getenv('BBOX_EAST', 122.562))
BBOX_NORTH = float(os.getenv('BBOX_NORTH', 17.168))

START_DATE = os.getenv('START_DATE', '2023-01-01')
END_DATE = os.getenv('END_DATE', '2024-12-31')
MAX_CLOUD_COVER = int(os.getenv('MAX_CLOUD_COVER', 10))
DRY_SEASON_MONTHS_STR = os.getenv('DRY_SEASON_MONTHS', '')
GEE_PROJECT = os.getenv('GEE_PROJECT', '')

if DRY_SEASON_MONTHS_STR:
    MONTHS = [int(m.strip()) for m in DRY_SEASON_MONTHS_STR.split(',')]
else:
    MONTHS = None

try:
    if GEE_PROJECT:
        ee.Initialize(project=GEE_PROJECT)
        print(f"GEE project: {GEE_PROJECT})")
    else:
        ee.Initialize()
        print("GEE connected")
except Exception as e:
    print(f"GEE connection failed {e}")
    exit(1)

print(f"\nSearching Sentinel 2:")
print(f"   Bounding Box: ({BBOX_WEST}°E, {BBOX_SOUTH}°N) to ({BBOX_EAST}°E, {BBOX_NORTH}°N)")
print(f"   Date range: {START_DATE} to {END_DATE}")
print(f"   Max cloud cover: {MAX_CLOUD_COVER}%")
if MONTHS:
    print(f"   Months: {MONTHS}")
print(f"   Resolution: 10m")

bbox = ee.Geometry.Rectangle([BBOX_WEST, BBOX_SOUTH, BBOX_EAST, BBOX_NORTH])

sentinel2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
    .filterBounds(bbox) \
    .filterDate(START_DATE, END_DATE) \
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', MAX_CLOUD_COVER))

if MONTHS:
    start_month = MONTHS[0]
    end_month = MONTHS[-1]
    
    if start_month == end_month:
        sentinel2 = sentinel2.filter(ee.Filter.calendarRange(start_month, start_month + 1, 'month'))
    else:
        sentinel2 = sentinel2.filter(ee.Filter.calendarRange(start_month, end_month + 1, 'month'))

size = sentinel2.size().getInfo()
print(f"\nFound {size} scenes")

if size == 0:
    print("No scenes match params")
    exit(0)

sorted_scenes = sentinel2.sort('CLOUDY_PIXEL_PERCENTAGE')

print(f"\nScenes (by cloud cover):")
print("-" * 100)

scene_list = []
dates_dict = {}
for i in range(min(size, 100)): #timeout prevention
    try:
        scene = ee.Image(sorted_scenes.toList(size).get(i))
        img_id = scene.id().getInfo()
        props = scene.toDictionary().getInfo()
        if props:
            scene_id = props.get('PRODUCT_ID', img_id if img_id else f'Scene_{i}')
            cloud = props.get('CLOUDY_PIXEL_PERCENTAGE', 'N/A')
            
            date = 'Unknown'
            if img_id and len(img_id) >= 8:
                date_str = img_id[:8] 
                if date_str.isdigit():
                    date = f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]}"
            
            try:
                tile = props.get('MGRS_TILE', 'Unknown')
            except:
                tile = 'Unknown'
            
            scene_list.append({
                'index': i,
                'scene_id': scene_id,
                'date': date,
                'cloud': cloud,
                'tile': tile,
                'image': scene
            })
            
            if date not in dates_dict:
                dates_dict[date] = {}
            if tile not in dates_dict[date]:
                dates_dict[date][tile] = []
            dates_dict[date][tile].append({'cloud': cloud, 'index': i})
    except Exception as e:
        print(f"Error with scene{i}: {e}")

print("\nScenes by date:")
for date in sorted(dates_dict.keys()):
    tiles_on_date = dates_dict[date]
    has_qvv = '51QVV' in tiles_on_date
    has_qvu = '51QVU' in tiles_on_date
    
    if has_qvv and has_qvu:
        qvv_cloud = min([float(t['cloud']) if isinstance(t['cloud'], (int, float)) else 99 for t in tiles_on_date['51QVV']])
        qvu_cloud = min([float(t['cloud']) if isinstance(t['cloud'], (int, float)) else 99 for t in tiles_on_date['51QVU']])
        max_cloud = max(qvv_cloud, qvu_cloud)
        print(f"{date}: 51QVV={qvv_cloud:.2f}% | 51QVU={qvu_cloud:.2f}% | Max={max_cloud:.2f}% BOTH VU and VV present")
    elif has_qvv:
        qvv_cloud = min([float(t['cloud']) if isinstance(t['cloud'], (int, float)) else 99 for t in tiles_on_date['51QVV']])
        print(f"{date}: 51QVV={qvv_cloud:.2f}% Missing 51QVU")
    elif has_qvu:
        qvu_cloud = min([float(t['cloud']) if isinstance(t['cloud'], (int, float)) else 99 for t in tiles_on_date['51QVU']])
        print(f"{date}: 51QVU={qvu_cloud:.2f}% Missing 51QVV")

if not scene_list:
    print("No valid scenes")
    exit(0)

print(f"\nLoaded {len(scene_list)} scenes")
print(f"\nIndividual scenes:")
for scene in scene_list:
    print(f"{scene['index']}: {scene['date']} | Cloud: {scene['cloud']}% | Tile: {scene['tile']}")

print("\n" + "=" * 100)
choice = input("Enter scene index or mosaic").strip()

if choice.lower() == 'skip':
    print("Skipping")
    exit(0)

try:
    if choice.lower() == 'mosaic':
        print(f"\n⬇Exporting mosaic ({len(scene_list)} scenes)")
        
        mosaicked = sentinel2.median()
        
        task = ee.batch.Export.image.toDrive(
            image=mosaicked.select(['B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B11', 'B12']),
            description=f'Sentinel2_Mosaic_{START_DATE.replace("-", "")}',
            folder='Sentinel2_Downloads',
            fileNamePrefix=f'Mosaic_{len(scene_list)}scenes_10m',
            scale=10,
            region=bbox,
            maxPixels=1e13
        )
        
        task.start()
        print(f"Mosaic export task started!")
        print(f"{len(scene_list)} scenes combined")
        print(f"Task ID: {task.id}")
    else:
        idx = int(choice.strip())
        if 0 <= idx < len(scene_list):
            scene = scene_list[idx]
            scene_id = scene['scene_id']
            img = scene['image']
            date = scene['date']
            
            print(f"\n⬇️  Exporting {scene_id}...")
            
            task = ee.batch.Export.image.toDrive(
                image=img.select(['B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B11', 'B12']),
                description=f'Sentinel2_{date.replace("-", "")}',
                folder='Sentinel2_Downloads',
                fileNamePrefix=f'{scene_id[:25]}',
                scale=10,
                region=bbox,
                maxPixels=1e13
            )
            
            task.start()
            print(f"Exporting")
            print(f"Task ID: {task.id}")
        else:
            print("Invalid scene index")
except ValueError:
    print("Invalid input")
except Exception as e:
    print(f"failed: {e}")
    import traceback
    traceback.print_exc()
