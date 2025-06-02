import os
import re
import shutil
import string
import ctypes
from PIL import Image
import pytesseract
from datetime import datetime
from multiprocessing import Pool, cpu_count, freeze_support
from tqdm import tqdm
from collections import Counter

pytesseract.pytesseract.tesseract_cmd = r"C:\\Users\\kukwh001\\AppData\\Local\\Programs\\Tesseract-OCR\\tesseract.exe"
output_root = r"Z:\\East\\Camera Trap Images (raw)"
threshold_date = datetime(2024, 11, 1)

# Get list of removable drives
def get_removable_drives():
    drives = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for i, letter in enumerate(string.ascii_uppercase):
        if bitmask & (1 << i):
            drive = f"{letter}:/"
            if ctypes.windll.kernel32.GetDriveTypeW(drive) == 2:
                drives.append(drive)
    return drives

# Extract the most frequent camera ID from images
def detect_camera_id(folder_100):
    images = [f for f in os.listdir(folder_100) if f.lower().endswith('.jpg')][:10]
    cam_ids = []
    for img in images:
        try:
            img_path = os.path.join(folder_100, img)
            img_obj = Image.open(img_path).convert("RGB")
            text = pytesseract.image_to_string(img_obj)
            match = re.search(r'CAMERA\s*\d{1,3}', text, re.IGNORECASE)
            if match:
                cam_id = match.group(0).replace(" ", "").lower()  # e.g., "camera7"
                cam_ids.append(cam_id)
        except Exception:
            continue
    if not cam_ids:
        return None
    return Counter(cam_ids).most_common(1)[0][0]  # Return the most common

# Check if any BTCF folder contains images older than the threshold date
def check_timestamp_warning(dcim_path):
    flagged = []
    for btc_folder in os.listdir(dcim_path):
        if "BTCF" not in btc_folder:
            continue
        folder_path = os.path.join(dcim_path, btc_folder)
        for f in os.listdir(folder_path):
            if f.lower().endswith(".jpg"):
                try:
                    img = Image.open(os.path.join(folder_path, f))
                    exif = img._getexif()
                    date_str = exif.get(36867) or exif.get(306)
                    if date_str:
                        img_date = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                        if img_date < threshold_date:
                            flagged.append(btc_folder)
                            break
                except:
                    continue
    return flagged

# Copy and verify all BTCF folders for a drive
def copy_and_verify(task):
    drive, cam_id = task
    site_folder = cam_id.replace("camera", "site")
    dest_root = os.path.join(output_root, site_folder)
    if os.path.exists(dest_root):
        print(f"⚠️ Folder {dest_root} already exists — skipping copy/verification for {drive}")
        return
    os.makedirs(dest_root, exist_ok=True)
    log_path = os.path.join(dest_root, f"{site_folder}_copy_log.txt")
    copied, verified, failed = 0, 0, 0
    failures = []

    dcim_path = os.path.join(drive, "DCIM")
    for btc_folder in os.listdir(dcim_path):
        if "BTCF" not in btc_folder:
            continue
        src_folder = os.path.join(dcim_path, btc_folder)
        rel_path = os.path.relpath(src_folder, dcim_path)
        dest_folder = os.path.join(dest_root, rel_path)
        os.makedirs(dest_folder, exist_ok=True)

        for root, _, files in os.walk(src_folder):
            rel_subfolder = os.path.relpath(root, dcim_path)
            dst_subfolder = os.path.join(dest_root, rel_subfolder)
            os.makedirs(dst_subfolder, exist_ok=True)

            for file in tqdm(files, desc=f"Copying {site_folder}", position=0, leave=True):
                if not file.lower().endswith('.jpg'):
                    continue
                src_file = os.path.join(root, file)
                dst_file = os.path.join(dst_subfolder, file)
                try:
                    shutil.copy2(src_file, dst_file)
                    copied += 1
                    if os.path.getsize(src_file) == os.path.getsize(dst_file):
                        verified += 1
                    else:
                        failures.append(f"❌ Size mismatch: {dst_file}")
                        failed += 1
                except Exception as e:
                    failures.append(f"❌ Failed to copy {src_file}: {e}")
                    failed += 1
# save log
    with open(log_path, "w") as log_file:
        log_file.write(f"Camera ID: {cam_id}\n")
        log_file.write(f"Source Drive: {drive}\n")
        log_file.write(f"Total Copied: {copied}\n")
        log_file.write(f"Verified: {verified}\n")
        log_file.write(f"Failed: {failed}\n\n")
        if failures:
            log_file.write("Failures:\n")
            log_file.write("\n".join(failures))
    
        # Get image date range and add to log
        start_date, end_date = get_image_date_range(dest_root)
        if start_date and end_date:
            print(f"📅 Image date range for {cam_id}: {start_date.date()} to {end_date.date()}")
            log_file.write(f"Date Range: {start_date.date()} to {end_date.date()}\n")
        else:
            print(f"⚠️ No valid timestamps found in images for {cam_id}")
            log_file.write("Date Range: Not found or unreadable\n")

    print(f"✅ {site_folder}: {copied} copied, {verified} verified, {failed} failed.")

if __name__ == '__main__':
    freeze_support()
    print("✅ Script started successfully")

    drive_cam_map = {}
    for drive in get_removable_drives():
        print(f"\n📁 Scanning drive: {drive}")
        folder_100 = os.path.join(drive, "DCIM", "100_BTCF")
        if not os.path.exists(folder_100):
            print(f"⚠️ No 100_BTCF found on {drive}, skipping.")
            continue

        cam_id = detect_camera_id(folder_100)
        if not cam_id:
            print(f"❌ No camera ID found on {drive}. Skipping.")
            continue

        print(f"✔ Found camera ID: {cam_id}")
        site_folder = cam_id.replace("camera", "site")
        if os.path.exists(os.path.join(output_root, site_folder)):
            print(f"❗ Potential overwrite risk: {site_folder} already exists. Remove drive and rerun.")
            continue

        # Check timestamp issue
        flagged_folders = check_timestamp_warning(os.path.join(drive, "DCIM"))
        if flagged_folders:
            print(f"⏰ WARNING: {cam_id.upper()} has images older than Nov 1, 2024 in: {flagged_folders}")
            with open(os.path.join(output_root, site_folder + "_copy_log.txt"), "a") as f:
                f.write(f"WARNING: Detected images older than Nov 1, 2024 in: {flagged_folders}\n")

        drive_cam_map[drive] = cam_id

    tasks = list(drive_cam_map.items())
    if not tasks:
        print("❌ No drives to process.")
    else:
        print("\n🚀 Starting parallel copy/verify operations...")
        with Pool(min(len(tasks), cpu_count())) as pool:
            pool.map(copy_and_verify, tasks)

    print("\n🎉 All tasks completed.")
