import os
import json
import time
from pathlib import Path
from datetime import datetime
from subprocess import run, CalledProcessError
from concurrent.futures import ProcessPoolExecutor
from tqdm import tqdm

# --- Root path options ---
POTENTIAL_RAW_ROOTS = [
    Path("Z:/East/Camera Trap Images (raw)"),
    Path("Z:/WhitneyHansen/East/Camera Trap Images (raw)")
]

POTENTIAL_PROCESSED_ROOTS = [
    Path("Z:/East/Camera Trap Images (processed)"),
    Path("Z:/WhitneyHansen/East/Camera Trap Images (processed)")
]

RAW_ROOT = next((p for p in POTENTIAL_RAW_ROOTS if p.exists()), None)
PROCESSED_ROOT = next((p for p in POTENTIAL_PROCESSED_ROOTS if p.exists()), None)

if RAW_ROOT is None or PROCESSED_ROOT is None:
    raise RuntimeError("Could not find appropriate raw or processed root paths.")

LOG_PATH = PROCESSED_ROOT / "speciesnet_log.json"

# --- Load or initialize log ---
if LOG_PATH.exists():
    with open(LOG_PATH, "r") as f:
        processing_log = json.load(f)
else:
    processing_log = []

# --- Determine processed folders from log ---
processed_folders ={
    entry["folder"]
    for entry in processing_log
    if "folder" in entry and "error" not in entry
}

# --- Find all BTCF folders across all sites ---
btcf_folders = []
for site_dir in RAW_ROOT.iterdir():
    if not site_dir.is_dir():
        continue
    for date_dir in site_dir.iterdir():
        if not date_dir.is_dir():
            continue
        for subdir in date_dir.iterdir():
            if "BTCF" in subdir.name:
                rel_path = subdir.relative_to(RAW_ROOT)
                if str(rel_path) not in processed_folders:
                    btcf_folders.append(subdir)
                    
# --- Processing function ---
def process_btcf_folder(btcf_folder):
    rel_path = btcf_folder.relative_to(RAW_ROOT)
    processed_dir = PROCESSED_ROOT / rel_path
    results_dir = processed_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    output_json = results_dir / "speciesnet_predictions.json"
    boxes_dir = results_dir / "boxes"
    boxes_dir.mkdir(exist_ok=True)

    cmd = [
        "python", "-m", "speciesnet.scripts.run_model",
        "--folders", str(btcf_folder),
        "--predictions_json", str(output_json)
    ]

    start = time.time()
    try:
        run(cmd, check=True)

        vis_cmd = [
            "python", "-m", "megadetector.visualization.visualize_detector_output",
            str(output_json), str(boxes_dir),
            "--confidence", "0.2",
            "--detections_only"
        ]
        run(vis_cmd, check=True)

        duration = round(time.time() - start, 2)
        return {
            "timestamp": datetime.now().isoformat(),
            "folder": str(rel_path),
            "duration_sec": duration
        }
    except CalledProcessError as e:
        return {
            "timestamp": datetime.now().isoformat(),
            "folder": str(rel_path),
            "error": str(e)
        }

# --- sequential processing ---
if __name__ == "__main__":
    # Only re-run folders that are either missing or failed
    folders_to_run = [
        f for f in btcf_folders
        if str(f.relative_to(RAW_ROOT)) not in processed_folders
    ]

    print(f"📁 Skipping {len(btcf_folders) - len(folders_to_run)} previously successful folders.")
    print(f"🚀 Running on {len(folders_to_run)} new or failed folders...")

    results = []
    for folder in tqdm(folders_to_run, desc="Running SpeciesNet"):
        results.append(process_btcf_folder(folder))

    # ✅ Clean the log: remove any previous entries for re-run folders
    rerun_folder_keys = {r["folder"] for r in results}
    processing_log = [entry for entry in processing_log if entry.get("folder") not in rerun_folder_keys]

    # ✅ Add updated results
    processing_log.extend(results)

    # ✅ Save log
    with open(LOG_PATH, "w") as f:
        json.dump(processing_log, f, indent=2)

    print("✅ Finished processing all folders.")


