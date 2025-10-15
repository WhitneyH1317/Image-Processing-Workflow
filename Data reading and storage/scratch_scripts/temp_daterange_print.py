import os
from PIL import Image
from PIL.ExifTags import TAGS
from datetime import datetime

# Path to top-level folder
INPUT_DIR = r"Z:\East\Camera Trap Images (raw)"

# Helper: extract EXIF datetime from image
def get_image_datetime(img_path):
    try:
        img = Image.open(img_path)
        exif_data = img._getexif()
        if not exif_data:
            return None
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag in ("DateTimeOriginal", "DateTime"):
                return datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
    except:
        return None

# Collect all image dates
image_dates = []

print(f"📂 Scanning images in: {INPUT_DIR}")

for root, _, files in os.walk(INPUT_DIR):
    for file in files:
        if file.lower().endswith((".jpg", ".jpeg")):
            img_path = os.path.join(root, file)
            dt = get_image_datetime(img_path)
            if dt:
                image_dates.append(dt)

# Print result
if not image_dates:
    print("❌ No valid image timestamps found.")
else:
    image_dates.sort()
    first = image_dates[0]
    last = image_dates[-1]
    print(f"\n✅ Earliest image date: {first.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"✅ Latest image date:   {last.strftime('%Y-%m-%d %H:%M:%S')}")