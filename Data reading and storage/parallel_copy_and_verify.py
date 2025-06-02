import os
import re
import shutil
import string
import ctypes
import win32com.client
from PIL import Image
import pytesseract
from datetime import datetime
from multiprocessing import Pool, cpu_count, freeze_support
from collections import Counter, defaultdict

# CONFIGURATION
pytesseract.pytesseract.tesseract_cmd = r"C:\\Users\\kukwh001\\AppData\\Local\\Programs\\Tesseract-OCR\\tesseract.exe"
output_root = r"Z:\\East\\Camera Trap Images (raw)"
threshold_date = datetime(2024, 11, 1)
skipped_drives = []

# UTILITIES

def get_removable_drives():
    drives = []
    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    for i, letter in enumerate(string.ascii_uppercase):
        if bitmask & (1 << i):
            drive = f"{letter}:/"
            if ctypes.windll.kernel32.GetDriveTypeW(drive) == 2:
                drives.append(drive)
    return drives

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
                cam_id = match.group(0).replace(" ", "").lower()
                cam_ids.append(cam_id)
        except Exception:
            continue
    if not cam_ids:
        return None
    return Counter(cam_ids).most_common(1)[0][0]

def get_image_date_range(dcim_path):
    btc_folders = sorted([f for f in os.listdir(dcim_path) if "BTCF" in f])
    if not btc_folders:
        return None, None

    first_folder = os.path.join(dcim_path, btc_folders[0])
    last_folder = os.path.join(dcim_path, btc_folders[-1])

    def get_image_date(folder, first=True):
        try:
            images = sorted([f for f in os.listdir(folder) if f.lower().endswith('.jpg')])
            if not images:
                return None
            img_file = images[0] if first else images[-1]
            img = Image.open(os.path.join(folder, img_file))
            exif = img._getexif()
            date_str = exif.get(36867) or exif.get(306)
            return datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S') if date_str else None
        except:
            return None

    return get_image_date(first_folder, True), get_image_date(last_folder, False)

def overlaps(new_range, existing_ranges):
    new_start, new_end = new_range
    for existing_start, existing_end in existing_ranges:
        if new_start <= existing_end and new_end >= existing_start:
            return True
    return False

def eject_drive_windows(drive_letter):
    try:
        import win32com.client
        wmi = win32com.client.Dispatch("WbemScripting.SWbemLocator")
        service = wmi.ConnectServer(".", "root\\cimv2")
        volumes = service.ExecQuery(f"SELECT * FROM Win32_Volume WHERE DriveLetter = '{drive_letter}'")
        for volume in volumes:
            result = volume.Dismount(True, False)
            if result == 0:
                print(f"💾 Successfully ejected drive {drive_letter}")
                return
        print(f"⚠️ Attempted eject of {drive_letter}, but it may still be in use.")
    except Exception as e:
        print(f"⚠️ Could not eject drive {drive_letter}: {e}")
        print(f"💡 You can now safely eject drive {drive_letter}")

# MAIN COPY AND VERIFY FUNCTION

def copy_and_verify(task):
    drive, cam_id, start_date, end_date = task
    # find folder holding BTCF folders (NOT the INF folder)
    valid_folders = [f for f in os.listdir(drive) if os.path.isdir(os.path.join(drive, f)) and f.upper() != "INF"]
    if not valid_folders:
        print(f"❌ No valid folder found on {drive}. Skipping.")
        skipped_drives.append((drive, "no_folder", "no_date"))
        return
    camera_folder = os.path.join(drive, valid_folders[0])

    site_folder = cam_id.replace("camera", "site")
    date_folder = f"{start_date.date()}_{end_date.date()}"
    dest_root = os.path.join(output_root, site_folder)
    full_dest = os.path.join(dest_root, date_folder)

    # ✅ Collect expected BTCF folders and JPG counts
    expected_structure = {}
    for btc_folder in os.listdir(camera_folder):
        if "BTCF" not in btc_folder:
            continue
        btc_path = os.path.join(camera_folder, btc_folder)
        if not os.path.isdir(btc_path):
            continue
        jpg_count = sum(1 for f in os.listdir(btc_path) if f.lower().endswith(".jpg"))
        expected_structure[btc_folder] = jpg_count

    existing = os.path.exists(full_dest)

    if existing:
        partial = False
        for btc_folder in expected_structure:
            dst_folder = os.path.join(full_dest, btc_folder)
            if not os.path.exists(dst_folder):
                partial = True
                break
            actual_count = sum(
                len(files) for _, _, files in os.walk(dst_folder)
                if any(f.lower().endswith('.jpg') for f in files)
            )
            if actual_count < expected_structure[btc_folder]:
                partial = True
                break

        if not partial:
            print(f"⚠️ Folder already exists: {full_dest} — skipping {drive}")
            skipped_drives.append((drive, site_folder, date_folder))
            return
        else:
            print(f"♻️ Resuming partial copy to: {full_dest}")
    else:
        print(f"♻️ Starting new copy to: {full_dest}")


    os.makedirs(full_dest, exist_ok=True)
    log_path = os.path.join(dest_root, f"{site_folder}_copy_log.txt")

    copied = verified = failed = 0
    failures = []

    dcim_path = camera_folder
    for btc_folder in os.listdir(dcim_path):
            if "BTCF" not in btc_folder:
                continue
            src_folder = os.path.join(dcim_path, btc_folder)
            rel_path = os.path.relpath(src_folder, dcim_path)
            dest_folder = os.path.join(full_dest, rel_path)
            os.makedirs(dest_folder, exist_ok=True)

            for root, _, files in os.walk(src_folder):
                rel_subfolder = os.path.relpath(root, dcim_path)
                dst_subfolder = os.path.join(full_dest, rel_subfolder)
                os.makedirs(dst_subfolder, exist_ok=True)

                for file in files:
                    #print(f"🔍 Found file: {file} in {root}")
                    if not file.lower().endswith('.jpg'):
                        continue
                    src_file = os.path.join(root, file)
                    dst_file = os.path.join(dst_subfolder, file)

                    if os.path.exists(dst_file):
                        src_size = os.path.getsize(src_file)
                        dst_size = os.path.getsize(dst_file)
                       # print(f"📄 Exists: {dst_file} (src: {src_size}, dst: {dst_size})")

                        if dst_size >= src_size:
                            continue  # skip identical or larger file
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

    print(f"✅ {site_folder} {date_folder}: {copied} copied, {verified} verified, {failed} failed.")

    eject_drive_windows(drive)

# MAIN SCRIPT
if __name__ == '__main__':
    freeze_support()
    print("✅ Script started successfully")

    drive_cam_map = {}
    existing_ranges = defaultdict(list)

    for drive in get_removable_drives():
        print(f"\n📁 Scanning drive: {drive}")
        try:
            folder_candidates = [f for f in os.listdir(drive) if f.lower().startswith("dcim") or f.lower().startswith("site") or f.isdigit()]
        except (PermissionError, OSError):
            print(f"⚠️ Drive {drive} is not ready. Skipping.")
            continue

        # First check for a siteXX folder
        site_foldername = next((f for f in folder_candidates if f.lower().startswith("site") or f.isdigit()), None)
        if site_foldername:
            number = re.sub("\\D", "", site_foldername)
            cam_id = f"camera{number.zfill(2)}"
            full_path = os.path.join(drive, site_foldername)
            print(f"✔ Found site folder: {site_foldername} -> camera ID: {cam_id}")
        else:
            folder_100 = None
            for f in folder_candidates:
                candidate = os.path.join(drive, f, "100_BTCF")
                if os.path.exists(candidate):
                    folder_100 = candidate
                    break
            if not folder_100 or not os.path.exists(folder_100):
                print(f"⚠️ No 100_BTCF folder found on {drive}, skipping.")
                continue

            cam_id = detect_camera_id(folder_100)
            if not cam_id:
                print(f"❌ Could not detect camera ID on {drive}, skipping.")
                continue

            print(f"✔ Detected camera ID: {cam_id}")

        site_folder = cam_id.replace("camera", "site").strip()

# collision check
        start_date, end_date = get_image_date_range(os.path.join(drive, folder_candidates[0]))
        if not start_date or not end_date:
            print(f"❌ Could not read image dates on {drive}, skipping.")
            continue

        overlapping_ranges = overlaps((start_date, end_date), existing_ranges[site_folder])
        if overlapping_ranges:
            print(f"❌ COLLISION: {drive} overlaps with existing data in {site_folder}")
            print(f"➤ SD card date range: {start_date.date()} to {end_date.date()}")
            for s, e in overlapping_ranges:
                print(f"➤ Existing folder date range: {s.date()} to {e.date()}")
            skipped_drives.append((
                drive,
                site_folder,
                f"{start_date.date()}_{end_date.date()}",
                [f"{s.date()}_{e.date()}" for s, e in overlapping_ranges]
            ))
            continue

        drive_cam_map[drive] = (cam_id, start_date, end_date)

    tasks = [(d, cam_id, s, e) for d, (cam_id, s, e) in drive_cam_map.items()]
    if tasks:
        print("\n🚀 Starting parallel copy/verify operations...")
        with Pool(min(len(tasks), cpu_count())) as pool:
            pool.map(copy_and_verify, tasks)
    else:
        print("❌ No drives to process.")

    if skipped_drives:
        print("\n⚠️ Skipped Drives Due to Collisions:")
        for drive, site, date in skipped_drives:
            print(f" - {drive} -> {site}/{date}")

    print("\n🎉 All tasks completed.")