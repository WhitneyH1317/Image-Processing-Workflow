import os
import sys

# --- Get source and destination from command-line args ---
if len(sys.argv) != 3:
    print("Usage: python verify_manual.py <source_dir> <destination_dir>")
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

print(f"\n🔍 Comparing:\n - Source: {source_dir}\n - Destination: {destination_dir}")

source_files = collect_images(source_dir)
dest_files = collect_images(destination_dir)

matched = 0
mismatched = []
missing_in_dest = []

for rel_path, src_path in source_files.items():
    if rel_path in dest_files:
        dst_path = dest_files[rel_path]
        try:
            if os.path.getsize(src_path) == os.path.getsize(dst_path):
                matched += 1
            else:
                mismatched.append(rel_path)
        except Exception as e:
            mismatched.append(f"{rel_path} (error: {e})")
    else:
        missing_in_dest.append(rel_path)

# --- Report ---
print(f"\n✅ {matched} files matched successfully")
print(f"❌ {len(mismatched)} mismatched (size mismatch)")
print(f"🚫 {len(missing_in_dest)} missing from destination")

if mismatched:
    print("\n⚠️ Mismatched files:")
    for f in mismatched:
        print(f" - {f}")

if missing_in_dest:
    print("\n⚠️ Missing files in destination:")
    for f in missing_in_dest:
        print(f" - {f}")
