from __future__ import annotations

import json
import argparse
from pathlib import Path
from datetime import datetime
import csv
from collections import defaultdict

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
# processed is optional for this check
if PROCESSED_ROOT is None:
    PROCESSED_ROOT = None


def norm_rel(p: Path, root: Path) -> str:
    return str(p.relative_to(root)).replace("\\", "/")


def parse_args():
    ap = argparse.ArgumentParser(
        description="Summarize MegaDetector completion at the SITE level (date folders complete/missing)."
    )
    ap.add_argument(
        "--prefix",
        default=None,
        help='Limit search to a prefix under RAW_ROOT, e.g. "site01" or "site01/2025-04-29_2025-06-16".'
    )
    ap.add_argument(
        "--out-dir",
        default=r"Z:\East\output",
        help=r'Output directory for CSVs (default: Z:\East\output).'
    )
    ap.add_argument(
        "--require-all-btcf",
        action="store_true",
        help=(
            "If set: a date_range is COMPLETE only if ALL BTCF folders inside it have image_recognition_file.json. "
            "If not set: a date_range is COMPLETE if ANY BTCF folder inside it has image_recognition_file.json."
        ),
    )
    ap.add_argument(
        "--limit-sites",
        type=int,
        default=None,
        help="Optional max number of sites to report (for quick tests)."
    )
    ap.add_argument(
        "--print-missing-dates",
        action="store_true",
        help="Also print missing date folders to console (can be long)."
    )
    return ap.parse_args()


def main():
    args = parse_args()

    search_root = RAW_ROOT
    if args.prefix:
        search_root = RAW_ROOT / Path(args.prefix)
        if not search_root.exists():
            raise FileNotFoundError(f"Prefix does not exist under RAW_ROOT: {search_root}")

    # Find all BTCF folders under search_root
    btcf_folders = sorted([p for p in search_root.rglob("*") if p.is_dir() and "BTCF" in p.name])

    # Group BTCF status by (site, date_range)
    # We infer:
    #   site = first folder under RAW_ROOT (e.g., "site01")
    #   date_range = second folder under RAW_ROOT (e.g., "2025-04-29_2025-06-16")
    # Any BTCF folder not matching site/date_range depth is ignored.
    group = defaultdict(list)  # (site, date_range) -> list[dict(btcf_path, has_json, mtime)]
    sites_seen = set()

    for btcf in btcf_folders:
        try:
            rel = btcf.relative_to(RAW_ROOT)
        except ValueError:
            # should not happen, but just in case
            continue

        parts = rel.parts
        if len(parts) < 3:
            # Need at least: site / date_range / BTCF...
            continue

        site = parts[0]
        date_range = parts[1]
        sites_seen.add(site)

        md_json = btcf / "image_recognition_file.json"
        has_json = md_json.exists()
        mtime = ""
        if has_json:
            try:
                mtime = datetime.fromtimestamp(md_json.stat().st_mtime).isoformat(timespec="seconds")
            except Exception:
                mtime = ""

        group[(site, date_range)].append(
            {
                "rel_btcf": norm_rel(btcf, RAW_ROOT),
                "btcf_folder": btcf.name,
                "md_json_exists": has_json,
                "md_json_path": str(md_json) if has_json else "",
                "md_json_mtime": mtime,
            }
        )

    # Roll up per (site, date_range) completeness
    date_rows = []  # one row per (site, date_range)
    per_site_dates = defaultdict(list)

    for (site, date_range), items in sorted(group.items()):
        n_btcf = len(items)
        n_has = sum(1 for x in items if x["md_json_exists"])
        n_missing = n_btcf - n_has

        if args.require_all_btcf:
            complete = (n_btcf > 0 and n_missing == 0)
        else:
            complete = (n_has > 0)

        date_row = {
            "site": site,
            "date_range": date_range,
            "n_btcf_folders": n_btcf,
            "n_btcf_with_json": n_has,
            "n_btcf_missing_json": n_missing,
            "date_complete": complete,
        }
        date_rows.append(date_row)
        per_site_dates[site].append(date_row)

    # Site-level summary: % of date folders complete, plus which date folders missing
    site_summary = []
    site_missing_dates = []

    for site in sorted(per_site_dates.keys()):
        dates = per_site_dates[site]
        n_dates = len(dates)
        n_complete = sum(1 for d in dates if d["date_complete"])
        n_incomplete = n_dates - n_complete
        pct = (100.0 * n_complete / n_dates) if n_dates else 0.0

        missing_list = [d["date_range"] for d in dates if not d["date_complete"]]
        missing_list_sorted = sorted(set(missing_list))

        site_summary.append(
            {
                "site": site,
                "n_date_folders": n_dates,
                "n_date_complete": n_complete,
                "n_date_incomplete": n_incomplete,
                "pct_complete": round(pct, 1),
                "missing_date_ranges": ";".join(missing_list_sorted),
            }
        )

        for dr in missing_list_sorted:
            site_missing_dates.append(
                {
                    "site": site,
                    "date_range": dr,
                }
            )

    # Optional: limit number of sites reported (console + outputs)
    if args.limit_sites is not None:
        keep_sites = set(sorted(per_site_dates.keys())[: args.limit_sites])
        site_summary = [r for r in site_summary if r["site"] in keep_sites]
        site_missing_dates = [r for r in site_missing_dates if r["site"] in keep_sites]
        date_rows = [r for r in date_rows if r["site"] in keep_sites]

    # Print console summary
    print(f"RAW_ROOT: {RAW_ROOT}")
    print(f"PROCESSED_ROOT: {PROCESSED_ROOT if PROCESSED_ROOT else '(none)'}")
    print(f"Sites found: {len(site_summary)}")
    print(f"Date folders found (site/date_range): {len(date_rows)}\n")

    # Sort: lowest completion first so the sites needing work rise to the top
    site_summary_sorted = sorted(site_summary, key=lambda r: (r["pct_complete"], r["site"]))

    for r in site_summary_sorted:
        print(
            f"{r['site']}: {r['pct_complete']}% complete "
            f"({r['n_date_complete']}/{r['n_date_folders']} date folders complete)"
        )
        if args.print_missing_dates and r["missing_date_ranges"]:
            missing = r["missing_date_ranges"].split(";")
            for dr in missing:
                print(f"   ❌ {dr}")
    print()

    # Write CSVs
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) Per-date folder rollup (handy for debugging)
    date_csv = out_dir / "md_by_site_date.csv"
    with open(date_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(date_rows[0].keys()) if date_rows else [])
        if date_rows:
            w.writeheader()
            w.writerows(date_rows)

    # 2) Site summary
    summary_csv = out_dir / "md_site_summary.csv"
    with open(summary_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(site_summary[0].keys()) if site_summary else [])
        if site_summary:
            w.writeheader()
            w.writerows(site_summary_sorted)

    # 3) Missing site/date_range rows (easy to feed into a runner)
    missing_csv = out_dir / "md_site_missing_dates.csv"
    with open(missing_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(site_missing_dates[0].keys()) if site_missing_dates else [])
        if site_missing_dates:
            w.writeheader()
            w.writerows(site_missing_dates)

    print(f"Wrote: {date_csv}")
    print(f"Wrote: {summary_csv}")
    print(f"Wrote: {missing_csv}")


if __name__ == "__main__":
    main()