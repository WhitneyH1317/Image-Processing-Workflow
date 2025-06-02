import os
from PIL import Image
from datetime import datetime

# Set your path here
site_root = r"Z:\East\Camera Trap Images (raw)"

def extract_date_from_image(image_path):
    try:
        img = Image.open(image_path)
        exif = img._getexif()
        if not exif:
            return None
        date_str = exif.get(36867) or exif.get(306)
        if date_str:
            return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
    except:
        return None

def get_first_and_last_image_dates(site_path):
    btc_folders = sorted([f for f in os.listdir(site_path) if "BTCF" in f])
    if not btc_folders or "100_BTCF" not in btc_folders:
        return None, None

    # First image from 100_BTCF
    first_imgs = sorted([
        f for f in os.listdir(os.path.join(site_path, "100_BTCF"))
        if f.lower().endswith(".jpg")
    ])
    if not first_imgs:
        return None, None
    first_date = extract_date_from_image(os.path.join(site_path, "100_BTCF", first_imgs[0]))

    # Last image from the LAST BTCF folder
    last_folder = btc_folders[-1]
    last_imgs = sorted([
        f for f in os.listdir(os.path.join(site_path, last_folder))
        if f.lower().endswith(".jpg")
    ])
    if not last_imgs:
        return first_date, None
    last_date = extract_date_from_image(os.path.join(site_path, last_folder, last_imgs[-1]))

    return first_date, last_date

# Loop through each site folder
for site_folder in os.listdir(site_root):
    site_path = os.path.join(site_root, site_folder)
    if not os.path.isdir(site_path):
        continue

    start_date, end_date = get_first_and_last_image_dates(site_path)
    if start_date and end_date:
        date_folder_name = f"{start_date.strftime('%Y-%m-%d')}_{end_date.strftime('%Y-%m-%d')}"
        new_path = os.path.join(site_path, date_folder_name)
        os.makedirs(new_path, exist_ok=True)
        print(f"✅ Created: {new_path}")
    else:
        print(f"⚠️ Skipped {site_folder}: could not read date range")
