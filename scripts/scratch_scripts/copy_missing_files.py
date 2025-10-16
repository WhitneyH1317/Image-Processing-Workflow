import os
import sys
import shutil

# --- Get source and destination from command-line args ---
if len(sys.argv) != 3:
    print("Usage: python copy_missing_files.py <source_dir> <destination_dir>")
    sys.exit(1)

source_dir = sys.argv[1]
destination_dir = sys.argv[2]

# --- Gather all .jpg files from source and destination ---
def collect_images(base_dir):
    file_map = {}
    for root, _, files in os.walk(base_dir):
        for f in files:
            if f.lower().endswith(".jpg"):
                rel_path = os.path.relpath(os.path.join(root, f), base_dir)
                full_path = os.path.join(root, f)
                file_map[rel_path] = full_path
    return file_map

print(f"\n📂 Scanning:\n - Source: {source_dir}\n - Destination: {destination_dir}")

source_files = collect_images(source_dir)
dest_files = collect_images(destination_dir)

# --- Identify missing or mismatched files ---
to_copy = []

for rel_path, src_path in source_files.items():
    dst_path = os.path.join(destination_dir, rel_path)
    if not os.path.exists(dst_path):
        to_copy.append((src_path, dst_path))
    else:
        try:
            if os.path.getsize(src_path) != os.path.getsize(dst_path):
                to_copy.append((src_path, dst_path))
        except Exception as e:
            print(f"⚠️ Error comparing {rel_path}: {e}")
            to_copy.append((src_path, dst_path))

# --- Copy files ---
print(f"\n📤 Copying {len(to_copy)} file(s) to destination...\n")

copied_count = 0
for src, dst in to_copy:
    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        print(f"✅ Copied: {os.path.relpath(dst, destination_dir)}")
        copied_count += 1
    except Exception as e:
        print(f"❌ Failed to copy {src} → {dst}: {e}")

# --- Final report ---
print(f"\n✅ Done. {copied_count} file(s) copied.")