import os
import re

root_dir = r"Z:\East\Camera Trap Images (raw)"

# Regex to match ONLY date folders in the incorrect format (e.g., 2024-12-01-2025-02-01)
pattern = re.compile(r'^(\d{4}-\d{2}-\d{2})-(\d{4}-\d{2}-\d{2})$')

for site_folder in os.listdir(root_dir):
    site_path = os.path.join(root_dir, site_folder)
    if not os.path.isdir(site_path):
        continue

    for folder in os.listdir(site_path):
        match = pattern.match(folder)
        if match:
            correct_name = f"{match.group(1)}_{match.group(2)}"
            old_path = os.path.join(site_path, folder)
            new_path = os.path.join(site_path, correct_name)
            if not os.path.exists(new_path):  # Avoid overwriting anything
                os.rename(old_path, new_path)
                print(f"✅ Renamed: {folder} → {correct_name}")
            else:
                print(f"⚠️ Skipped (target exists): {correct_name}")