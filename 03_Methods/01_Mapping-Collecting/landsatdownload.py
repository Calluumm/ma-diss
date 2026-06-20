import ee
import os
from dotenv import load_dotenv

load_dotenv()

BBOX_WEST = float(os.getenv('BBOX_WEST', 122.22))
BBOX_SOUTH = float(os.getenv('BBOX_SOUTH', 16.694))
BBOX_EAST = float(os.getenv('BBOX_EAST', 122.562))
BBOX_NORTH = float(os.getenv('BBOX_NORTH', 17.168))

START_DATE = os.getenv('START_DATE', '2023-01-01')
END_DATE = os.getenv('END_DATE', '2024-01-01')
MAX_CLOUD_COVER = int(os.getenv('MAX_CLOUD_COVER', 20))
DRY_SEASON_MONTHS_STR = os.getenv('DRY_SEASON_MONTHS', '')
GEE_PROJECT = os.getenv('GEE_PROJECT', '')

if DRY_SEASON_MONTHS_STR:
    MONTHS = [int(m.strip()) for m in DRY_SEASON_MONTHS_STR.split(',')]
else:
    MONTHS = None

try:
    if GEE_PROJECT:
        ee.Initialize(project=GEE_PROJECT)
        print(f"Connected to: {GEE_PROJECT})")
    else:
        ee.Initialize()
        print("GEE connection succesful")
except Exception as e:
    print(f"GEE connection failed: {e}")
    exit(1)

print(f"\n Searching Landsat 8/9:")
print(f"   Bounding Box: ({BBOX_WEST}°E, {BBOX_SOUTH}°N) to ({BBOX_EAST}°E, {BBOX_NORTH}°N)")
print(f"   Date range: {START_DATE} to {END_DATE}")
print(f"   Max cloud cover: {MAX_CLOUD_COVER}%")
if MONTHS:
    print(f"   Months: {MONTHS}")

bbox = ee.Geometry.Rectangle([BBOX_WEST, BBOX_SOUTH, BBOX_EAST, BBOX_NORTH])

landsat8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2') \
    .filterBounds(bbox) \
    .filterDate(START_DATE, END_DATE) \
    .filter(ee.Filter.lt('CLOUD_COVER', MAX_CLOUD_COVER))

landsat9 = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2') \
    .filterBounds(bbox) \
    .filterDate(START_DATE, END_DATE) \
    .filter(ee.Filter.lt('CLOUD_COVER', MAX_CLOUD_COVER))

landsat = landsat8.merge(landsat9)

if MONTHS:
    start_month = MONTHS[0]
    end_month = MONTHS[-1]
    
    if start_month == end_month:
        landsat = landsat.filter(ee.Filter.calendarRange(start_month, start_month + 1, 'month'))
    else:
        landsat = landsat.filter(ee.Filter.calendarRange(start_month, end_month + 1, 'month'))

size = landsat.size().getInfo()
print(f"\n Found {size} scenes")

if size == 0:
    print("No scenes match the params")
    exit(0)

sorted_scenes = landsat.sort('CLOUD_COVER')

print(f"\nScenes by cc:")
print("-" * 100)

scene_list = []
for i in range(size):
    try:
        scene = ee.Image(sorted_scenes.toList(size).get(i))
        props = scene.toDictionary().getInfo()
        
        if props:
            scene_id = props.get('LANDSAT_PRODUCT_ID', scene.id().getInfo())
            cloud = props.get('CLOUD_COVER', 'N/A')
            
            parts = scene_id.split('_')
            if len(parts) >= 4:
                date_str = parts[3]
                date = f"{date_str[0:4]}-{date_str[4:6]}-{date_str[6:8]}"
            else:
                date = 'Unknown'
            
            scene_list.append({
                'index': i,
                'scene_id': scene_id,
                'date': date,
                'cloud': cloud,
                'image': scene
            })
            print(f"{i}: {date} | Cloud: {cloud}% | {scene_id}")
    except Exception as e:
        print(f"Error loading scene {i}: {e}")

if not scene_list:
    print("No valid scenes")
    exit(0)

print("\n" + "=" * 100)
choice = input("scene index or mosaic").strip()

if choice.lower() == 'skip':
    print("Skipping")
    exit(0)

try:
    if choice.lower() == 'mosaic':
        print(f"\nExporting mosaic ({size} scenes)")
        mosaicked = landsat.median()
        
        task = ee.batch.Export.image.toDrive(
            image=mosaicked.select(['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7']),
            description=f'Landsat8_Mosaic_{START_DATE.replace("-", "")}_{END_DATE.replace("-", "")}',
            folder='Landsat_Downloads',
            fileNamePrefix=f'Mosaic_{size}scenes',
            scale=30,
            region=bbox,
            maxPixels=1e13
        )
        
        task.start()
        print(f"Mosaic task")
        print(f"{size} scenes combined")
        print(f"Task ID: {task.id}")
    else:
        idx = int(choice.strip())
        if 0 <= idx < len(scene_list):
            scene = scene_list[idx]
            scene_id = scene['scene_id']
            img = scene['image']
            
            print(f"\n⬇️  Exporting {scene_id}...")
            
            task = ee.batch.Export.image.toDrive(
                image=img.select(['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7']),
                description=f'Landsat8_{scene_id.split("_")[3]}',
                folder='Landsat_Downloads',
                fileNamePrefix=scene_id,
                scale=30,
                region=bbox,
                maxPixels=1e13
            )
            
            task.start()
            print(f"Exporting")
            print(f"   Task ID: {task.id}")
        else:
            print("Invalid scene index")
except ValueError:
    print("Invalid input")
except Exception as e:
    print(f"Export failed: {e}")
    import traceback
    traceback.print_exc()
