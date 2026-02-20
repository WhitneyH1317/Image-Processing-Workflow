import csv
import subprocess
import sys
from pathlib import Path

# ---- EDIT THIS ONLY ----
CSV_PATH = r"Z:\East\output\md_check_2026-02-16.csv"
# ------------------------

def parse_bool(x):
    return str(x).strip().lower() in {"true", "t", "1", "yes", "y"}

def clean_site(site_val: str) -> str:
    """
    md_check may store 'Site 12' or 'site12' or '12'. Normalize to 'site12' etc.
    """
    s = (site_val or "").strip()
    if not s:
        return ""
    s_low = s.lower()
    # handle "Site 12"
    if s_low.startswith("site "):
        digits = "".join(ch for ch in s_low if ch.isdigit())
        return f"site{digits}" if digits else s_low.replace(" ", "")
    # handle "Site12" or "site12"
    if s_low.startswith("site"):
        return s_low.replace(" ", "")
    # handle just digits
    if s.isdigit():
        return f"site{s}"
    return s_low.replace(" ", "")

def main():
    # Resolve sn_run.py relative to this script’s location
    here = Path(__file__).resolve().parent
    sn_run = here / "2_sn_run.py"
    if not sn_run.exists():
        raise SystemExit(f"Could not find sn_run.py next to this script: {sn_run}")

    missing = []

    with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fns = set(reader.fieldnames or [])

        # We can use rel_btcf if it's good, otherwise build from site/date_range/btcf_folder
        has_rel = "rel_btcf" in fns
        has_site = "site" in fns
        has_date = "date_range" in fns
        has_btcf = "btcf_folder" in fns

        if "md_json_exists" not in fns:
            raise SystemExit(f"CSV missing md_json_exists column. Found: {reader.fieldnames}")

        for row in reader:
            if parse_bool(row.get("md_json_exists", "")):
                continue

            rel = (row.get("rel_btcf") or "").strip().replace("\\", "/").strip("/")

            # If rel_btcf is missing the site prefix, fix it
            if rel and not rel.lower().startswith("site"):
                if has_site and has_date and has_btcf:
                    site = clean_site(row.get("site", ""))
                    date_range = (row.get("date_range") or "").strip().replace("\\", "/").strip("/")
                    btcf = (row.get("btcf_folder") or "").strip().replace("\\", "/").strip("/")
                    if site and date_range and btcf:
                        rel = f"{site}/{date_range}/{btcf}"
                # else: rel stays as-is

            # If rel_btcf is empty, build from parts
            if not rel and has_site and has_date and has_btcf:
                site = clean_site(row.get("site", ""))
                date_range = (row.get("date_range") or "").strip().replace("\\", "/").strip("/")
                btcf = (row.get("btcf_folder") or "").strip().replace("\\", "/").strip("/")
                if site and date_range and btcf:
                    rel = f"{site}/{date_range}/{btcf}"

            if rel:
                missing.append(rel)

    # de-dupe while preserving order
    seen = set()
    missing = [x for x in missing if not (x in seen or seen.add(x))]

    print(f"Found {len(missing)} BTCF folder(s) missing MD output.")

    if not missing:
        return

    for i, rel in enumerate(missing, start=1):
        print(f"\n[{i}/{len(missing)}] Running sn_run.py on: {rel}")

        cmd = [
            sys.executable,
            str(sn_run),
            "--run-only-one",
            "--only-this-rel-path", rel,
            # "--force-rerun",
        ]

        subprocess.run(cmd, check=True)

    print("\n✅ Finished all missing folders.")

if __name__ == "__main__":
    main()
