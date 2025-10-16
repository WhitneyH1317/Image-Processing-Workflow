# Image-Processing-Workflow

Custom python scripts for uploading images in bulk from SD cards to remote storage, and running MegaDetector + SpeciesNet models on image data. 



* www: [Image-Processing-Workflow](https://WhitneyH1317.github.io/Image-Processing-Workflow/) 
* repository: [Image-Processing-Workflow](https://github.com/WhitneyH1317/Image-Processing-Workflow) 

# Directory Structure 

The repository contains the following files and directories:

```
```

# SpeciesNet Run Script (sn_run.py)
Overview

speciesnet_run.py automates camera trap image processing for the East Foundation’s wildlife monitoring workflow using the SpeciesNet deep learning pipeline.

It systematically traverses your raw image directories and:

Runs MegaDetector (detecting animals, humans, vehicles)

Classifies detections using SpeciesNet (custom Southwest US model)

Saves .json outputs with species predictions

Optionally saves bounding-box .jpg images

Automatically skips or resumes processing intelligently based on timestamps and partial outputs

This script is designed for large-scale, perpetual processing—safely re-runnable across all sites without overwriting completed results.

# 📁 Folder Structure

Expected layout for East Foundation camera-trap data:

```
Z:\East\Camera Trap Images (raw)
└── site03
├── 2024-12-12_2025-01-31
│ ├── 100_BTCF
│ │ ├── IMG_0001.JPG
│ │ └── ...
│ └── 101_BTCF
└── 2025-02-01_2025-03-31
├── 100_BTCF
└── ...
```

This script was written to produce images and .json files readable by Addax AI Software, within which humans can manually verify speciesnet output. Processed results (produced by Addax AI software) are written to the parallel path:

Z:\East\Camera Trap Images (processed)\

Each BTCF folder is mirrored with corresponding .json results and optional annotated bounding box images.

# ⚙️ Environment Setup

Activate your SpeciesNet conda environment before running:

conda activate speciesnet_env

If MegaDetector or SpeciesNet aren’t installed, you can add them via:

pip install megadetector speciesnet

Make sure your Python environment includes:

torch

absl-py

pandas

numpy

tqdm

speciesnet (>=0.5.0)

# 🚀 Basic Usage
Run all sites (recursive)

`python speciesnet_run.py`

Processes all sites and BTCF folders recursively under your raw root.

Automatically skips any folder whose .json output is newer than the latest .JPG.

You can safely rerun this anytime—it will only process what’s new or updated.

# 🧩 Command-Line Arguments
`--run-prefix-rel` 

Run all folders under a specific site prefix:

`python speciesnet_run.py --run-prefix-rel site03`

➡️ Processes all date ranges and BTCFs under site03
➡️ Skips all others

`--only-this-rel-path`

Process just one BTCF folder:

`python speciesnet_run.py --only-this-rel-path "site03\2024-12-12_2025-01-31\101_BTCF"`

➡️ Re-runs only that folder (useful when one camera failed or was interrupted).

`--force-rerun`

Reprocesses even if .json files already exist:

`python speciesnet_run.py --run-prefix-rel site03 --force-rerun`

➡️ Deletes or overwrites existing temporary or completed results.
➡️ Use this after path issues or model updates.

`--run-only-one`

Run just the first matching folder (quick test):

`python speciesnet_run.py --run-prefix-rel site01 --run-only-one`

`--addax-mode`

Select the SpeciesNet inference mode.

`--addax-mode custom_species # default; Southwest US species model`
`--addax-mode megadetector_only # detection only, no species classification`

# 🧠 Intelligent Skipping and Resume Behavior

The script automatically checks:

Condition	Behavior
JSON newer than all images	⏭️ Skip folder
Temp partial JSON exists, same image set	🔁 Resume from partial progress
New images added	🚀 Re-run folder
Missing or renamed files	⚠️ Raise error and abort folder

# 🩹 Common Errors & Fixes
`Error: RuntimeError: Filepath from loaded predictions is missing from the set of instances...`

Cause: A _speciesnet_output_predictions.temp.json file was created using a different drive or user path (e.g., Z:/WhitneyHansen/... vs Z:\East\...).

Fix:

Delete the stale temp file:
`Remove-Item "Z:\East\Camera Trap Images (raw)\site03\2024-12-12_2025-01-31\101_BTCF_speciesnet_output_predictions.temp.json" -Force`

Re-run the affected folder:
`python speciesnet_run.py --only-this-rel-path "site03\2024-12-12_2025-01-31\101_BTCF" --force-rerun`

`Error: Your push was rejected due to missing or corrupt local objects...`

Cause: Attempting to resume with missing or cloud-only (OneDrive) files.
Fix: Make sure all images are fully downloaded and local (green checkmark, not cloud icon) before re-running.

# 🧹 Maintenance & Troubleshooting
Delete all temporary partials

`Get-ChildItem -Recurse -Filter _speciesnet_output_predictions.temp.json | Remove-Item -Force`

Rerun a single failed camera

`python speciesnet_run.py --only-this-rel-path "site03\2024-12-12_2025-01-31\101_BTCF" --force-rerun`

Rerun all cameras for a site

`python speciesnet_run.py --run-prefix-rel site03 --force-rerun`

List all folders that would be processed (if supported)

`python speciesnet_run.py --run-prefix-rel site03 --list-only`

🧾 Output Files

Each *_BTCF folder produces:

File	Description
_speciesnet_output_predictions.temp.json	Partial predictions for resumable runs
speciesnet_output_predictions.json	Final output file (species detections and confidence scores)
*.jpg with bounding boxes	Optional visualization outputs (if enabled in script)

# 💡 Recommended Workflows
Routine site-wide updates

`python speciesnet_run.py`
Safe to run repeatedly; will skip already-processed folders.

Targeted re-run

`python speciesnet_run.py --only-this-rel-path "site03\2024-12-12_2025-01-31\101_BTCF" --force-rerun`

Clean reset (reprocess everything)

`python speciesnet_run.py --run-prefix-rel site03 --force-rerun`

# 🧠 Notes for Multi-Machine Use

Always run with a consistent drive mapping (e.g., Z:\East\...).

Avoid running from OneDrive-synced directories; use local or mapped drives instead.

If switching computers or users, delete partial .temp.json files before resuming.

# 🧑‍💻 Example Log Output

`📂 RUN_PREFIX_REL matched 23 folder(s) under 'site03'.
Found 5679 BTCF folder(s).
🚀 Will process 23 folder(s).
⏭️ Skipping site03\2024-12-12_2025-01-31\100_BTCF (json_mtime >= latest image mtime)
--- Processing site03\2024-12-12_2025-01-31\101_BTCF ---
RAW BTCF: Z:\East\Camera Trap Images (raw)\site03\2024-12-12_2025-01-31\101_BTCF
PROCESSED BTCF: Z:\East\Camera Trap Images (processed)\site03\2024-12-12_2025-01-31\101_BTCF
✅ Completed site03\2024-12-12_2025-01-31\101_BTCF`

# 🧩 Contributing

This script was developed for the East Foundation camera-trap pipeline, managed under the speciesnet_env conda environment.

If you adapt or extend it:

Add new argument handlers for filtering or batching runs.

Consider contributing improvements (e.g., robust path resolution, distributed runs).

Bug reports, feature requests, and documentation updates are welcome through Issues or Pull Requests on this repository.
