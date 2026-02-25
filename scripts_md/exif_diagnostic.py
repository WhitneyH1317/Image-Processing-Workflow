from pathlib import Path
from PIL import Image, ExifTags
from datetime import datetime

# CHANGE THIS to a single image OR a folder
TEST_PATH = Path(r"Z:\East\Camera Trap Images (raw)\site01")

# Build EXIF tag lookup
EXIF_TAGS = {v: k for k, v in ExifTags.TAGS.items()}

def inspect_image(p: Path):
    print("=" * 80)
    print(f"FILE: {p}")
    print("Exists:", p.exists())

    if not p.exists():
        return

    # File system times
    stat = p.stat()
    print("Filesystem created:", datetime.fromtimestamp(stat.st_ctime))
    print("Filesystem modified:", datetime.fromtimestamp(stat.st_mtime))

    try:
        with Image.open(p) as img:
            exif = img.getexif()

            if not exif:
                print("No EXIF data found.")
                return

            print(f"EXIF entries found: {len(exif)}")

            # Look specifically for date fields
            for tag_name in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
                tag_id = EXIF_TAGS.get(tag_name)
                if tag_id in exif:
                    print(f"{tag_name}: {exif[tag_id]}")

            # Uncomment this if you want to see ALL EXIF fields
            # print("\nAll EXIF fields:")
            # for k, v in exif.items():
            #     tag = ExifTags.TAGS.get(k, k)
            #     print(f"{tag}: {v}")

    except Exception as e:
        print("Error reading EXIF:", e)


def run():
    if TEST_PATH.is_file():
        inspect_image(TEST_PATH)
    elif TEST_PATH.is_dir():
        images = list(TEST_PATH.rglob("*.JPG"))[:10]  # first 10 JPGs
        print(f"Testing first {len(images)} images...\n")
        for p in images:
            inspect_image(p)
    else:
        print("Path not found.")


if __name__ == "__main__":
    run()