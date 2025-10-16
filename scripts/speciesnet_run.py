import os
import json
import time
from pathlib import Path
from datetime import datetime
from subprocess import run, CalledProcessError
from tqdm import tqdm

# =========================
# TEST/RUN OPTIONS
# =========================
RUN_ONLY_ONE = False  # CHANGE: set True to process a single folder to sanity-check the pipeline
ONLY_THIS_REL_PATH = None  # e.g., Path("Site01/2024-01-01/100_BTCF")
MEGADETECTOR_PY = None
RUN_PREFIX_REL = "site02"  # e.g., "site01"

ADDAX_MODE = "custom_species"

CUSTOM_MODEL_INFO = {
    "name": "SpeciesNet Southwest",
    "label_map_version": "v1",
    "notes": "Animal/blank + cervidae/odocoileus/WTD hierarchy"
}

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
processing_log = []

# =========================
# HELPERS
# =========================
def run_module(py_module: str, args: list[str]):
    return run(["python", "-m", py_module, *args], check=True)

# CHANGE: quick file utils for skip logic
IMG_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}

def _list_image_files(btcf: Path):
    return [p.name for p in btcf.iterdir() if p.is_file() and p.suffix.lower() in IMG_EXTS]

def _latest_mtime(btcf: Path):
    latest = 0.0
    for p in btcf.iterdir():
        if p.is_file():
            try:
                latest = max(latest, p.stat().st_mtime)
            except FileNotFoundError:
                pass
    return latest

def should_skip_by_raw_json(btcf: Path):
    """
    Fast path: if image_recognition_file.json is newer than any image -> skip.
    Safe path: if its 'images[*].file' set matches current disk files -> skip.
    Returns (skip: bool, reason: str, meta: dict)
    """
    addax_json = btcf / "image_recognition_file.json"
    if not addax_json.exists():
        return (False, "no image_recognition_file.json", {})

    try:
        json_mtime = addax_json.stat().st_mtime
    except FileNotFoundError:
        return (False, "json disappeared", {})

    latest_img_mtime = _latest_mtime(btcf)
    if json_mtime >= latest_img_mtime:
        return (True, "json_mtime >= latest image mtime", {"json_mtime": json_mtime, "latest_img_mtime": latest_img_mtime})

    # safer filename-set check
    try:
        with open(addax_json, "r") as f:
            data = json.load(f)
        json_names = [im.get("file") for im in data.get("images", []) if im.get("file")]
    except Exception as e:
        return (False, f"failed to parse json ({e})", {})

    disk_names = _list_image_files(btcf)
    if set(n.lower() for n in json_names) == set(n.lower() for n in disk_names):
        return (True, "filename sets match", {"json_count": len(json_names), "disk_count": len(disk_names)})
    else:
        return (False, "filename sets differ", {"json_count": len(json_names), "disk_count": len(disk_names)})

# CHANGE: add helper to sync detection + classification vocabularies
def sync_detection_and_classification_categories(data: dict) -> dict:
    det = {str(k): v for k, v in (data.get("detection_categories") or {}).items()}
    cls = {str(k): v for k, v in (data.get("classification_categories") or {}).items()}
    det.setdefault("1", "animal")
    det.setdefault("2", "blank")
    det.setdefault("3", "no cv result")
    for k, v in cls.items():
        det.setdefault(k, v)
    data["detection_categories"] = det
    return data

def patch_to_addax(data: dict, addax_mode: str):
    info = data.setdefault("info", {})
    info.setdefault("format_version", 1.4)
    info.setdefault("detector", "converted_from_predictions_json")

    addax_meta = info.setdefault("addaxai_metadata", {})
    addax_meta.setdefault("version", "6.12")

    if addax_mode == "custom_species":
        addax_meta["custom_model"] = True
        addax_meta["custom_model_info"] = CUSTOM_MODEL_INFO
    else:
        addax_meta["custom_model"] = False
        addax_meta.setdefault("custom_model_info", {})
        data.pop("classification_categories", None)
        data.pop("classification_category_descriptions", None)
        for im in data.get("images", []):
            for d in im.get("detections", []):
                d.pop("classifications", None)

    det = data.get("detection_categories", {}) or {}
    det.setdefault("1", "animal")
    det.setdefault("2", "blank")
    det.setdefault("3", "no cv result")
    data["detection_categories"] = det
    data = sync_detection_and_classification_categories(data)
    return data

# CHANGE: helpers to make RUN_ONLY_ONE actually work
def _normalize_rel(p: Path) -> str:
    return str(p.relative_to(RAW_ROOT)).replace("\\", "/").lower()

def choose_folders_to_run(btcf_folders):
    normed = [_normalize_rel(p) for p in btcf_folders]
    if RUN_PREFIX_REL:
        prefix = str(RUN_PREFIX_REL).replace("\\", "/").lower().strip("/")
        selected = [p for p in btcf_folders if _normalize_rel(p).startswith(prefix + "/") or _normalize_rel(p) == prefix]
        if not selected:
            raise FileNotFoundError(f"No BTCF folders found under prefix '{RUN_PREFIX_REL}'.")
        print(f"📂 RUN_PREFIX_REL matched {len(selected)} folder(s) under '{prefix}'.")
        if RUN_ONLY_ONE:
            print("🛑 RUN_ONLY_ONE=True; using only the first matching folder.")
            return [sorted(selected, key=lambda p: _normalize_rel(p))[0]]
        return sorted(selected, key=lambda p: _normalize_rel(p))
    if RUN_ONLY_ONE:
        if ONLY_THIS_REL_PATH is None:
            if not btcf_folders:
                raise RuntimeError("No BTCF folders found.")
            chosen = sorted(btcf_folders, key=lambda p: _normalize_rel(p))[0]
            print(f"🔎 RUN_ONLY_ONE=True; auto-picked first folder: {_normalize_rel(chosen)}")
            return [chosen]
        target = str(ONLY_THIS_REL_PATH).replace("\\", "/").lower().strip("/")
        matches = [p for p in btcf_folders if _normalize_rel(p) == target] or \
                  [p for p in btcf_folders if _normalize_rel(p).endswith("/" + target)]
        if not matches:
            raise FileNotFoundError(f"Could not find BTCF folder matching '{ONLY_THIS_REL_PATH}'.")
        chosen = sorted(matches, key=lambda p: _normalize_rel(p))[0]
        print(f"🎯 RUN_ONLY_ONE=True; chosen folder: {_normalize_rel(chosen)}")
        return [chosen]
    return btcf_folders

# =========================
# MAIN PROCESS
# =========================
# Find all BTCF folders across RAW
btcf_folders = []
for site_dir in RAW_ROOT.iterdir():
    if not site_dir.is_dir():
        continue
    for date_dir in site_dir.iterdir():
        if not date_dir.is_dir():
            continue
        for subdir in date_dir.iterdir():
            if subdir.is_dir() and "BTCF" in subdir.name:
                btcf_folders.append(subdir)

btcf_folders = sorted(btcf_folders, key=lambda p: _normalize_rel(p))
folders_to_run = choose_folders_to_run(btcf_folders)
print(f"🚀 Will process {len(folders_to_run)} folder(s).")

def process_btcf_folder(btcf_folder: Path):
    """
    Steps:
      0) NEW: Skip if RAW image_recognition_file.json is up-to-date and matches filenames
      1) Run SpeciesNet -> temp SpeciesNet JSON (in RAW BTCF)
      2) Convert to MD JSON with base_folder=RAW BTCF (relative paths)
      3) Patch to Addax schema & metadata (KEEP classifications in 'custom_species' mode)
      4) Write final image_recognition_file.json in RAW BTCF (overwrite)
      5) Create/update mirrored folder under PROCESSED + STATUS.json
    """
    rel_path = btcf_folder.relative_to(RAW_ROOT)
    raw_btc = RAW_ROOT / rel_path
    raw_btc.mkdir(parents=True, exist_ok=True)

    # mirror dir in processed tree for postprocessing outputs
    processed_dir = PROCESSED_ROOT / rel_path
    processed_dir.mkdir(parents=True, exist_ok=True)
    status_path = processed_dir / "STATUS.json"

    # CHANGE: Skip logic based on RAW JSON + filenames
    skip, why, meta = should_skip_by_raw_json(raw_btc)
    if skip:
        print(f"⏭️  Skipping {rel_path} ({why})")
        # still write/update STATUS so you have visibility
        status = {
            "skipped": True,
            "reason": why,
            **meta,
            "raw_btc_folder": str(raw_btc),
            "checked_at": datetime.now().isoformat()
        }
        with open(status_path, "w") as f:
            json.dump(status, f, indent=2)
        return {"folder": str(rel_path), "skipped": True, "reason": why}

    # temp files in RAW BTCF
    sn_tmp = raw_btc / "_speciesnet_output_predictions.temp.json"
    md_tmp = raw_btc / "_megadetector_input_predictions.temp.json"

    # final Addax JSON (overwrite)
    addax_json = raw_btc / "image_recognition_file.json"

    print(f"\n--- Processing {rel_path} ---")
    print(f"RAW BTCF:       {raw_btc}")
    print(f"PROCESSED BTCF: {processed_dir}")

    t0 = time.time()
    try:
        # 1) SpeciesNet (classifier)
        run_module("speciesnet.scripts.run_model", [
            "--folders", str(raw_btc),
            "--predictions_json", str(sn_tmp)
        ])

        # 2) Convert SpeciesNet -> MD JSON with base_folder = RAW BTCF
        run_module("speciesnet.scripts.speciesnet_to_md", [
            str(sn_tmp), str(md_tmp),
            "--base_folder", f"{raw_btc.as_posix()}/"
        ])

        # 3) Patch to Addax (keep classifications in custom_species mode)
        with open(md_tmp, "r") as f:
            data = json.load(f)

        # defensive merge from SN if converter dropped classifications
        try:
            with open(sn_tmp, "r") as f:
                sn = json.load(f)
            if "classification_categories" in sn and "classification_categories" not in data:
                data["classification_categories"] = sn["classification_categories"]
            if "classification_category_descriptions" in sn and "classification_category_descriptions" not in data:
                data["classification_category_descriptions"] = sn["classification_category_descriptions"]

            sn_index = {im["file"] if "file" in im else Path(im.get("image_path","")).name: im
                        for im in sn.get("images", [])}
            merged = 0
            for md_im in data.get("images", []):
                key = md_im.get("file")
                sn_im = sn_index.get(key)
                if not sn_im:
                    continue
                for md_det, sn_det in zip(md_im.get("detections", []), sn_im.get("detections", [])):
                    if not md_det.get("classifications") and sn_det.get("classifications"):
                        md_det["classifications"] = sn_det["classifications"]
                        merged += 1
            if merged:
                print(f"🔁 Merged classifications onto {merged} detections from SpeciesNet temp")
        except Exception:
            pass

        data = patch_to_addax(data, ADDAX_MODE)

        # 4) Write final JSON (overwrite)
        with open(addax_json, "w") as f:
            json.dump(data, f, indent=2)

        # quick sanity print
        det_with_cls = sum(
            sum(1 for d in im.get("detections", []) if d.get("classifications"))
            for im in data.get("images", [])
        )
        print(f"✅ classifications present on {det_with_cls} detections")

        # 5) STATUS.json in processed mirror
        status = {
            "last_run": datetime.now().isoformat(),
            "raw_btc_folder": str(raw_btc),
            "addax_json_in_raw": str(addax_json),
            "mode": ADDAX_MODE,
            "note": "Place postprocessing outputs (after Addax verification) in this processed folder."
        }
        with open(status_path, "w") as f:
            json.dump(status, f, indent=2)

        # cleanup temps
        try:
            sn_tmp.unlink(missing_ok=True)
            md_tmp.unlink(missing_ok=True)
        except Exception:
            pass

        return {"folder": str(rel_path), "timestamp": datetime.now().isoformat(),
                "duration_sec": round(time.time() - t0, 2), "mode": ADDAX_MODE}

    except CalledProcessError as e:
        err = {"folder": str(rel_path), "timestamp": datetime.now().isoformat(),
               "error": str(e), "mode": ADDAX_MODE}
        with open(status_path, "w") as f:
            json.dump(err, f, indent=2)
        return err

if __name__ == "__main__":
    print(f"Found {len(btcf_folders)} BTCF folder(s).")
    results = []
    for i, folder in enumerate(folders_to_run, start=1):
        results.append(process_btcf_folder(folder))
        if RUN_ONLY_ONE:
            print("🛑 RUN_ONLY_ONE=True; stopping after the first folder.")
            break

    with open(LOG_PATH, "w") as f:
        json.dump(results, f, indent=2)

    print("✅ Done.")
