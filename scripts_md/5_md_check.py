from __future__ import annotations

import json
import argparse
from pathlib import Path
from datetime import datetime
import csv

# Match your pipeline's root discovery
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

if RAW_ROOT is None:
    raise RuntimeError("Could not find RAW_ROOT (Z:/East/... or Z:/WhitneyHansen/...).")
if PROCESSED_ROOT is None:
    # processed is optional for this check
    PROCESSED_ROOT = None


def norm_rel(p: Path, root: Path) -> str:
    return str(p.relative_to(root)).replace("\\", "/")


def parse_args():
    ap = argparse.ArgumentParser(
        description="Check which BTCF folders have MegaDetector output (image_recognition_file.json)."
    )
    ap.add_argument(
        "--prefix",
        default=None,
        help='Limit search to a prefix under RAW_ROOT, e.g. "site01" or "site01/2025-04-29_2025-06-16".'
    )
    ap.add_argument(
        "--out-csv",
        default=r"Z:\East\output\md_check.csv",
        help=r'Write CSV summary here (default: Z:\East\output\md_check.csv).'
    )
    ap.add_argument(
        "--only-missing",
        action="store_true",
        help="Only print rows where MD output is missing."
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max number of BTCF folders to report (for quick tests)."
    )
    return ap.parse_args()


def main():
    args = parse_args()

    search_root = RAW_ROOT
    if args.prefix:
        search_root = RAW_ROOT / Path(args.prefix)
        if not search_root.exists():
            raise FileNotFoundError(f"Prefix does not exist under RAW_ROOT: {search_root}")

    # Find all BTCF folders by looking for directories with 'BTCF' in the name
    btcf_folders = sorted([p for p in search_root.rglob("*") if p.is_dir() and "BTCF" in p.name])

    if args.limit is not None:
        btcf_folders = btcf_folders[: args.limit]

    rows = []
    n_total = 0
    n_has_json = 0

    for btcf in btcf_folders:
        n_total += 1
        addax_json = btcf / "image_recognition_file.json"
        has_json = addax_json.exists()
        if has_json:
            n_has_json += 1

        # Optional: read a little metadata from JSON
        json_mtime = None
        n_images = None
        n_dets = None
        has_classifications = None
        model_name = None
        parse_error = None

        if has_json:
            try:
                json_mtime = datetime.fromtimestamp(addax_json.stat().st_mtime).isoformat(timespec="seconds")
                with open(addax_json, "r") as f:
                    data = json.load(f)
                images = data.get("images", []) or []
                n_images = len(images)
                n_dets = sum(len(im.get("detections", []) or []) for im in images)
                has_classifications = any(
                    any(bool(d.get("classifications")) for d in (im.get("detections", []) or []))
                    for im in images
                )
                info = data.get("info", {}) or {}
                addax_meta = info.get("addaxai_metadata", {}) if isinstance(info, dict) else {}
                cm = addax_meta.get("custom_model_info", {}) if isinstance(addax_meta, dict) else {}
                model_name = cm.get("name")
            except Exception as e:
                parse_error = str(e)

        # Optional: check processed STATUS.json mirror
        status_path = None
        status_last_run = None
        status_skipped = None
        status_reason = None

        if PROCESSED_ROOT is not None:
            try:
                rel = btcf.relative_to(RAW_ROOT)
                status_path = PROCESSED_ROOT / rel / "STATUS.json"
                if status_path.exists():
                    with open(status_path, "r") as f:
                        st = json.load(f)
                    status_last_run = st.get("last_run") or st.get("timestamp")
                    status_skipped = st.get("skipped")
                    status_reason = st.get("reason")
                else:
                    status_path = str(status_path)
            except Exception:
                status_path = None

        rel_btcf = norm_rel(btcf, RAW_ROOT)
        row = {
            "rel_btcf": rel_btcf,
            "site": rel_btcf.split("/")[0] if "/" in rel_btcf else rel_btcf,
            "date_range": rel_btcf.split("/")[1] if rel_btcf.count("/") >= 1 else None,
            "btcf_folder": btcf.name,
            "md_json_exists": has_json,
            "md_json_path": str(addax_json) if has_json else "",
            "md_json_mtime": json_mtime or "",
            "n_images": n_images if n_images is not None else "",
            "n_detections": n_dets if n_dets is not None else "",
            "has_classifications": has_classifications if has_classifications is not None else "",
            "model_name": model_name or "",
            "parse_error": parse_error or "",
            "status_json_path": str(status_path) if status_path else "",
            "status_last_run": status_last_run or "",
            "status_skipped": status_skipped if status_skipped is not None else "",
            "status_reason": status_reason or "",
        }
        rows.append(row)

    # Print summary + (optionally filtered) rows
    print(f"RAW_ROOT: {RAW_ROOT}")
    print(f"PROCESSED_ROOT: {PROCESSED_ROOT if PROCESSED_ROOT else '(none)'}")
    print(f"BTCF folders scanned: {n_total}")
    print(f"With image_recognition_file.json: {n_has_json}")
    print(f"Missing: {n_total - n_has_json}\n")

    to_print = rows
    if args.only_missing:
        to_print = [r for r in rows if not r["md_json_exists"]]

    # console output (compact)
    for r in to_print[:2000]:
        flag = "✅" if r["md_json_exists"] else "❌"
        print(f"{flag} {r['rel_btcf']}  (images={r['n_images']}, dets={r['n_detections']})")

    # write CSV
    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = list(rows[0].keys()) if rows else []
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"\nWrote CSV: {out_csv}")


if __name__ == "__main__":
    main()
