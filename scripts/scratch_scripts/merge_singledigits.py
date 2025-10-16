import shutil
import filecmp
import hashlib
import os
from pathlib import Path

# =========================
# CONFIG
# =========================
PARENT = Path(r"Z:/East/Camera Trap Images (raw)")  # parent directory containing the site folders
SITE_A = "site6"
SITE_B = "site06"
TARGET_SITE = "site06"     # where everything gets consolidated

DRY_RUN = True             # preview first!

# Optional: restrict what counts as a "date folder"
DATE_FOLDER_FILTER = None  # e.g., lambda p: "_" in p.name and p.name[:4].isdigit()

# =========================
# HELPERS
# =========================
def iter_dirs(d: Path):
    for p in sorted(d.iterdir()):
        if p.is_dir() and (DATE_FOLDER_FILTER(p) if DATE_FOLDER_FILTER else True):
            yield p

def same_file(src: Path, dst: Path) -> bool:
    """Quick 'identical' check."""
    try:
        if src.stat().st_size != dst.stat().st_size:
            return False
        try:
            return filecmp.cmp(str(src), str(dst), shallow=False)
        except Exception:
            # Hash fallback if needed
            h1 = hashlib.sha1(); h2 = hashlib.sha1()
            with src.open('rb') as f:
                for chunk in iter(lambda: f.read(1 << 20), b''):
                    h1.update(chunk)
            with dst.open('rb') as f:
                for chunk in iter(lambda: f.read(1 << 20), b''):
                    h2.update(chunk)
            return h1.digest() == h2.digest()
    except FileNotFoundError:
        return False

def ensure_dir(p: Path):
    if not DRY_RUN:
        p.mkdir(parents=True, exist_ok=True)

def move_dir(src: Path, dst: Path):
    if DRY_RUN:
        return
    shutil.move(str(src), str(dst))

def copy_file(src: Path, dst: Path):
    if DRY_RUN:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(src), str(dst))

def merge_dirs(src: Path, dst: Path):
    """
    Recursively merge src into dst.
    Never overwrite different files: keep target’s copy on conflict.
    Returns (files_copied, identical_skipped, conflicts_kept_target)
    """
    ensure_dir(dst)
    files_copied = identical_skipped = conflicts = 0

    for root, dirs, files in os.walk(src):
        rel = Path(root).relative_to(src)
        dst_root = dst / rel
        ensure_dir(dst_root)

        for d in dirs:
            ensure_dir(dst_root / d)

        for f in files:
            s = Path(root) / f
            t = dst_root / f
            if t.exists():
                if same_file(s, t):
                    identical_skipped += 1
                else:
                    # conflict; keep target
                    conflicts += 1
                continue
            copy_file(s, t)
            files_copied += 1

    return files_copied, identical_skipped, conflicts

# =========================
# MAIN
# =========================
def main():
    site_a = PARENT / SITE_A
    site_b = PARENT / SITE_B
    for p in (site_a, site_b):
        if not p.exists():
            raise FileNotFoundError(f"Missing site folder: {p}")

    target = PARENT / TARGET_SITE
    if not DRY_RUN:
        target.mkdir(parents=True, exist_ok=True)

    # Gather date folders
    a_dates = {d.name: d for d in iter_dirs(site_a)}
    b_dates = {d.name: d for d in iter_dirs(site_b)}

    only_a = sorted(set(a_dates) - set(b_dates))
    only_b = sorted(set(b_dates) - set(a_dates))
    both  = sorted(set(a_dates) & set(b_dates))

    # Summaries
    moved_from_a = []
    moved_from_b = []
    merged_names = []
    per_merge_stats = {}  # name -> (files_copied, identical_skipped, conflicts)

    # Move unique date folders
    for name in only_a:
        src = a_dates[name]; dst = target / name
        if dst.exists():
            # should be rare; treat as merge to be safe
            fc, iskip, conf = merge_dirs(src, dst)
            merged_names.append(name)
            per_merge_stats[name] = (fc, iskip, conf)
        else:
            move_dir(src, dst)
            moved_from_a.append(name)

    for name in only_b:
        src = b_dates[name]; dst = target / name
        if dst.exists():
            fc, iskip, conf = merge_dirs(src, dst)
            merged_names.append(name)
            per_merge_stats[name] = (fc, iskip, conf)
        else:
            move_dir(src, dst)
            moved_from_b.append(name)

    # Merge shared date folders (A and B → target)
    for name in both:
        dst = target / name
        if not DRY_RUN:
            dst.mkdir(parents=True, exist_ok=True)
        # Merge A then B; target wins on conflicts
        fc_a, is_a, cf_a = merge_dirs(a_dates[name], dst)
        fc_b, is_b, cf_b = merge_dirs(b_dates[name], dst)
        merged_names.append(name)
        per_merge_stats[name] = (fc_a + fc_b, is_a + is_b, cf_a + cf_b)

    # ======= SUMMARY OUTPUT (concise) =======
    print("=== Merge Summary ===")
    print(f"Source A: {site_a}")
    print(f"Source B: {site_b}")
    print(f"Target : {target}")
    print(f"DRY_RUN: {DRY_RUN}")
    print()

    print(f"Moved from {SITE_A} → {TARGET_SITE}: {len(moved_from_a)} folder(s)")
    if moved_from_a:
        for n in moved_from_a:
            print(f"  • {n}")

    print(f"\nMoved from {SITE_B} → {TARGET_SITE}: {len(moved_from_b)} folder(s)")
    if moved_from_b:
        for n in moved_from_b:
            print(f"  • {n}")

    print(f"\nMerged into {TARGET_SITE}: {len(merged_names)} folder(s)")
    if merged_names:
        for n in merged_names:
            fc, iskip, conf = per_merge_stats.get(n, (0,0,0))
            # brief per-date stats (counts only, still concise)
            print(f"  • {n}  (copied: {fc}, identical: {iskip}, conflicts_kept_target: {conf})")

    if DRY_RUN:
        print("\nDRY_RUN is ON — no files were moved or copied. Set DRY_RUN=False to execute.")

if __name__ == "__main__":
    main()
