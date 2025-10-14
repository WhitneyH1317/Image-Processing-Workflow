import psycopg2
from concurrent.futures import ProcessPoolExecutor
from PIL import Image
from PIL.ExifTags import TAGS
import os
from datetime import datetime, timezone

# Configuration
root_dir = r"Z:\East\Camera Trap Images (raw)"
# Connect to database
conn = psycopg2.connect(
    dbname="East Camera Template", user="postgres", password="postgres", host="localhost", port=5432
)
cursor = conn.cursor()

# 1. Get all already-processed directories
cursor.execute("SELECT directory FROM main.photos")
existing_dirs = set(row for row in cursor.fetchall())
print(f"Loaded {len(existing_dirs)} existing directories from database")

# function for extracting datetime from image
def get_exif_datetime(img_path):
    try:
        img = Image.open(img_path)
        exif_data = img._getexif()
        if exif_data is not None:
            for tag_id, val in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == "DateTimeOriginal":
                    return datetime.strptime(val, '%Y:%m:%d %H:%M:%S')
    except Exception as e:
        print(f"Warning: Failed to extract EXIF from {img_path}: {e}")
    return None

# 2. Function to process a single image, returns tuple for DB insert
def extract_photo_metadata(full_path, root_dir):
    # Extract id_site from path: find 'siteX' folder and parse number
    parts = full_path.split(os.sep)
    site_folder = None
    for part in parts:
        if part.lower().startswith("site"):
            site_folder = part
            break
    if site_folder is None:
        print(f"Skipping {full_path}: 'site' folder not found")
        return None

    try:
        id_site = int(site_folder.lower().replace("site", ""))
    except ValueError:
        print(f"Skipping {full_path}: invalid site folder name '{site_folder}'")
        return None

 # Build relative directory from site folder on (same as in DB)
    site_idx = parts.index(site_folder)
    directory = os.sep.join(parts[site_idx:])

 # Skip if already processed
    if directory in existing_dirs:
        print(f"Skipping already processed {directory}")
        return None
    
# Extract acquisition time
    acq_time = get_exif_datetime(full_path)
    if acq_time is None:
        # Fallback: file modification time
        acq_time = datetime.fromtimestamp(os.path.getmtime(full_path))
    
    now_utc = datetime.now(timezone.utc)

    print(f"Processed {directory} Acquisition time: {acq_time}")

    return (id_site, acq_time, directory, '', now_utc, now_utc)

# 3. Walk all files and get list of files to process (skipping those already present)
all_files = []
for dirpath, _, filenames in os.walk(root_dir):
    for filename in filenames:
        if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            continue
        full_path = os.path.join(dirpath, filename)
        # We will filter already-processed in extract_photo_metadata, so include all here
        all_files.append(full_path)

print(f"Found {len(all_files)} files to process in total")

# 4. Process in parallel to speed up metadata extraction
with ProcessPoolExecutor() as executor:
    results = list(executor.map(lambda f: extract_photo_metadata(f, root_dir), all_files))

# Remove None results (skipped files)
photo_records = [r for r in results if r is not None]
print(f"Prepared {len(photo_records)} records for database insertion")

# 5. Bulk insert all at once
insert_query = """
    INSERT INTO main.photos (id_site, acquisition_timestamp, directory, notes, created_at_utc, updated_at_utc)
    VALUES %s
"""
execute_values(cursor, insert_query, photo_records)
conn.commit()
print("Insertion complete and committed")

cursor.close()
conn.close()
