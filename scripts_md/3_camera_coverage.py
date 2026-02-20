import os
import re
import csv
from datetime import datetime, timedelta

# ========= CONFIG =========
RAW_ROOT = r"Z:\East\Camera Trap Images (raw)"
REPORT_ROOT = r"Z:\East\report_files"   # folder to store reports
# =========================

SITE_REGEX = re.compile(r"^(site)?\d+$", re.IGNORECASE)
RANGE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2}$")


def parse_range_folder(name):
    """Parse 'YYYY-MM-DD_YYYY-MM-DD' into (start_date, end_date)."""
    if not RANGE_REGEX.match(name):
        return None
    a, b = name.split("_", 1)
    try:
        start = datetime.strptime(a, "%Y-%m-%d").date()
        end = datetime.strptime(b, "%Y-%m-%d").date()
        if end < start:
            return None
        return (start, end)
    except ValueError:
        return None


def list_site_dirs(root):
    """Return absolute paths to folders like siteXX."""
    if not os.path.isdir(root):
        raise SystemExit(f"Root not found or not a directory: {root}")

    return sorted(
        os.path.join(root, d)
        for d in os.listdir(root)
        if os.path.isdir(os.path.join(root, d)) and SITE_REGEX.match(d)
    )


def coalesce_intervals(intervals):
    """Merge overlapping or touching intervals."""
    if not intervals:
        return []
    intervals = sorted(intervals, key=lambda x: x[0])
    merged = [intervals[0]]
    for s, e in intervals[1:]:
        ms, me = merged[-1]
        if s <= me + timedelta(days=1):  # overlap or touch
            merged[-1] = (ms, max(me, e))
        else:
            merged.append((s, e))
    return merged


def find_gaps(merged):
    """Return gaps between merged intervals as (gap_start, gap_end, gap_days)."""
    gaps = []
    for (ps, pe), (ns, ne) in zip(merged, merged[1:]):
        gap_start = pe + timedelta(days=1)
        gap_end = ns - timedelta(days=1)
        if gap_start <= gap_end:
            gap_days = (gap_end - gap_start).days + 1
            gaps.append((gap_start, gap_end, gap_days))
    return gaps


def interval_days(intervals):
    """Sum inclusive days in merged intervals."""
    return sum((e - s).days + 1 for s, e in intervals)


def fmt_date(d):
    """Pretty date for text report."""
    return d.strftime("%B %d, %Y")


def main():
    # Ensure report directory exists
    os.makedirs(REPORT_ROOT, exist_ok=True)

    # Prepare dated filenames
    today_str = datetime.now().strftime("%Y-%m-%d")
    txt_path = os.path.join(REPORT_ROOT, f"camera_coverage_report_{today_str}.txt")
    csv_path = os.path.join(REPORT_ROOT, f"camera_coverage_report_{today_str}.csv")

    sites = list_site_dirs(RAW_ROOT)
    lines = []          # for the text report
    csv_rows = []       # for the CSV report

    for site_path in sites:
        site_name = os.path.basename(site_path)
        digits = re.sub(r"\D", "", site_name)
        site_label = f"Site {int(digits)}" if digits else site_name

        # Collect intervals from date-range folders
        intervals = []
        for child in sorted(os.listdir(site_path)):
            folder_path = os.path.join(site_path, child)
            if not os.path.isdir(folder_path):
                continue
            rng = parse_range_folder(child)
            if rng:
                intervals.append(rng)

        if not intervals:
            # No date ranges: still give one row in CSV
            lines.append(f"{site_label}:")
            lines.append("  (no date-range folders found)")
            lines.append("")

            csv_rows.append({
                "site": site_label,
                "status": "data available",
                "start_date": "",
                "end_date": ""
            })
            continue

        merged = coalesce_intervals(intervals)
        first_start = merged[0][0]
        last_end = merged[-1][1]

        total_span_days = (last_end - first_start).days + 1
        covered_days = interval_days(merged)
        missing_days = total_span_days - covered_days
        percent_missing = (missing_days / total_span_days * 100) if total_span_days > 0 else 0.0

        gaps = find_gaps(merged)

        # --- TEXT REPORT BLOCK ---
        lines.append(f"{site_label}:")
        lines.append(f"  data available from: {fmt_date(first_start)} - {fmt_date(last_end)}")

        if gaps:
            for (gs, ge, gd) in gaps:
                lines.append(
                    f"  data missing from: {fmt_date(gs)} - {fmt_date(ge)} ({gd} days)"
                )
        else:
            lines.append("  data missing from: (no gaps)")

        lines.append(
            f"  percentage missing data: {percent_missing:.1f}% "
            f"({missing_days} of {total_span_days} days)"
        )
        lines.append("")

        # --- CSV REPORT ROWS ---
        # 1) Data-available rows: one per merged interval
        for (s, e) in merged:
            csv_rows.append({
                "site": site_label,
                "status": "data available",
                "start_date": s.isoformat(),
                "end_date": e.isoformat()
            })

        # 2) Data-missing rows: one per gap
        for (gs, ge, gd) in gaps:
            csv_rows.append({
                "site": site_label,
                "status": "data missing",
                "start_date": gs.isoformat(),
                "end_date": ge.isoformat()
            })

    # Write text report
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # Write CSV report
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["site", "status", "start_date", "end_date"]
        )
        writer.writeheader()
        writer.writerows(csv_rows)

    print(f"✅ Text report created: {txt_path}")
    print(f"✅ CSV report created:  {csv_path}")


if __name__ == "__main__":
    main()
