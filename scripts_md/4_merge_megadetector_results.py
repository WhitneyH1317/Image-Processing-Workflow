from __future__ import annotations

import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# EXIF reading (pip install pillow)
from PIL import Image, ExifTags


# =========================
# ROOT PATH OPTIONS (match your pipeline)
# =========================
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


# =========================
# HELPERS
# =========================
def normalize_rel(p: Path, root: Path) -> str:
    return str(p.relative_to(root)).replace("\\", "/")


def infer_site_date_btcf_from_rel(rel: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    parts = rel.split("/")
    site = parts[0] if len(parts) >= 1 else None
    date_range = parts[1] if len(parts) >= 2 else None
    btcf = parts[2] if len(parts) >= 3 else None
    return site, date_range, btcf


def safe_json_load(p: Path) -> Dict[str, Any]:
    with open(p, "r") as f:
        return json.load(f)


def to_abs_image_path(image_file_field: str, raw_btcf_dir: Path) -> str:
    if image_file_field is None:
        return ""
    s = str(image_file_field)
    # already absolute like Z:/...
    if len(s) >= 3 and s[1:3] == ":/":
        return s
    return str((raw_btcf_dir / s).resolve())


def flatten_classifications(cls: Any) -> Tuple[Optional[str], Optional[float], Optional[str]]:
    if not cls:
        return None, None, None
    try:
        raw = json.dumps(cls)
    except Exception:
        raw = str(cls)

    top_id = None
    top_score = None

    # list of [id, score]
    if isinstance(cls, list) and len(cls) > 0 and isinstance(cls[0], (list, tuple)) and len(cls[0]) >= 2:
        try:
            top = max(cls, key=lambda x: float(x[1]))
            top_id, top_score = str(top[0]), float(top[1])
            return top_id, top_score, raw
        except Exception:
            return None, None, raw

    # list of dicts
    if isinstance(cls, list) and len(cls) > 0 and isinstance(cls[0], dict):
        def score_of(d):
            for k in ("conf", "score", "prob", "p"):
                if k in d:
                    return float(d[k])
            return 0.0

        try:
            top = max(cls, key=score_of)
            for k in ("category", "class", "id", "label"):
                if k in top:
                    top_id = str(top[k])
                    break
            top_score = score_of(top)
            return top_id, top_score, raw
        except Exception:
            return None, None, raw

    return None, None, raw


# ---------- EXIF helpers ----------
_EXIF_TAGS = {v: k for k, v in ExifTags.TAGS.items()}


def exif_capture_datetime(abs_image_path: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (capture_datetime, capture_datetime_source)

    capture_datetime is formatted as 'YYYY-MM-DD HH:MM:SS' when parseable.
    source is one of: 'DateTimeOriginal', 'DateTimeDigitized', 'DateTime'
    """
    if not abs_image_path:
        return None, None

    p = Path(abs_image_path)
    if not p.exists():
        return None, None

    try:
        with Image.open(p) as img:
            exif = None

            # Preferred newer API
            try:
                exif = img.getexif()
            except Exception:
                exif = None

            # Fallback older API
            if not exif:
                try:
                    exif = img._getexif()  # type: ignore[attr-defined]
                except Exception:
                    exif = None

            if not exif:
                return None, None

            for tag_name in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
                tag_id = _EXIF_TAGS.get(tag_name)
                if tag_id is None:
                    continue

                v = exif.get(tag_id) if hasattr(exif, "get") else None
                if not v:
                    continue

                s = str(v).strip()  # typically 'YYYY:MM:DD HH:MM:SS'
                try:
                    dt = datetime.strptime(s, "%Y:%m:%d %H:%M:%S")
                    return dt.strftime("%Y-%m-%d %H:%M:%S"), tag_name
                except Exception:
                    return s, tag_name

    except Exception:
        return None, None

    return None, None


def site_id_to_folder(site_id: int) -> str:
    """site 1 -> site01, site 84 -> site84"""
    return f"site{site_id:02d}"


def parse_site_selector(site_sel: Optional[str]) -> Optional[List[str]]:
    """
    Accepts:
      - None -> None
      - "1-84" -> ["site01", ..., "site84"]
      - "1,2,5-8,84" -> list of site folders
      - "site01,site02" -> list of site folders (passthrough)
    Returns list of site folder names (e.g., ["site01", "site02"]) or None.
    """
    if not site_sel:
        return None

    raw = site_sel.strip()
    if not raw:
        return None

    tokens = [t.strip() for t in raw.split(",") if t.strip()]
    sites: List[str] = []

    for t in tokens:
        tl = t.lower()

        # already like "site01"
        if tl.startswith("site"):
            sites.append(tl)
            continue

        # range like "1-84"
        if "-" in tl:
            a, b = tl.split("-", 1)
            a = a.strip()
            b = b.strip()
            if a.isdigit() and b.isdigit():
                start = int(a)
                end = int(b)
                if start > end:
                    start, end = end, start
                for sid in range(start, end + 1):
                    sites.append(site_id_to_folder(sid))
            continue

        # single number like "7"
        if tl.isdigit():
            sites.append(site_id_to_folder(int(tl)))
            continue

        # ignore unknown token (or raise if you prefer)
        raise ValueError(f"Unrecognized site selector token: '{t}'")

    # de-dup, preserve order
    seen = set()
    out = []
    for s in sites:
        if s not in seen:
            out.append(s)
            seen.add(s)
    return out


def build_output_filename(site_sel: Optional[str]) -> str:
    """
    mdmerge_nonblanks_YYYY-MM-DD.csv
    or mdmerge_nonblanks_YYYY-MM-DD_site_sel.csv if site_sel is provided
    """
    today = datetime.now().strftime("%Y-%m-%d")
    if site_sel:
        return f"mdmerge_nonblanks_{today}_site_sel.csv"
    return f"mdmerge_nonblanks_{today}.csv"


# =========================
# MAIN MERGE (NON-BLANK ONLY, MINIMAL COLUMNS, OPTIONAL SITE LIST)
# =========================
def merge_all(prefix_rel: Optional[str], out_dir: Path, site_sel: Optional[str]) -> pd.DataFrame:
    selected_sites = parse_site_selector(site_sel)

    # If a selection is provided, we iterate each site folder explicitly (fast + avoids crawling everything).
    # Otherwise we use RAW_ROOT (or run-prefix-rel).
    search_roots: List[Path] = []
    if selected_sites:
        for s in selected_sites:
            root = RAW_ROOT / s
            if root.exists():
                search_roots.append(root)
            else:
                print(f"WARNING: site folder not found, skipping: {root}")
        if not search_roots:
            raise FileNotFoundError("No selected site folders were found under RAW_ROOT.")
    else:
        search_root = RAW_ROOT
        if prefix_rel:
            search_root = RAW_ROOT / Path(prefix_rel)
            if not search_root.exists():
                raise FileNotFoundError(f"Prefix path does not exist under RAW_ROOT: {search_root}")
        search_roots = [search_root]

    det_rows: List[Dict[str, Any]] = []

    n_json = 0
    n_images = 0
    n_images_with_dets = 0
    n_dets = 0
    n_exif_missing = 0

    # Process each root separately (helps progress + avoids enormous rglob)
    for root_i, root in enumerate(search_roots, start=1):
        json_files = sorted(root.rglob("image_recognition_file.json"))
        print(f"\n[{root_i}/{len(search_roots)}] Searching: {root}  (found {len(json_files)} json files)")

        for j, jf in enumerate(json_files, start=1):
            n_json += 1
            if j % 50 == 0:
                print(f"  [{j}/{len(json_files)}] {jf}")

            rel_json = normalize_rel(jf, RAW_ROOT)
            site, date_range, _btcf = infer_site_date_btcf_from_rel(rel_json)
            raw_btcf_dir = jf.parent

            try:
                data = safe_json_load(jf)
            except Exception as e:
                print(f"WARNING: failed to parse {jf}: {e}")
                continue

            det_cats = {str(k): v for k, v in (data.get("detection_categories") or {}).items()}
            cls_cats = {str(k): v for k, v in (data.get("classification_categories") or {}).items()}

            info = data.get("info", {}) or {}
            addax_meta = (info.get("addaxai_metadata") or {}) if isinstance(info, dict) else {}
            model_name = None
            try:
                cm = addax_meta.get("custom_model_info") or {}
                model_name = cm.get("name") or None
            except Exception:
                model_name = None

            images = data.get("images", []) or []
            for im in images:
                n_images += 1

                dets = im.get("detections", []) or []
                if len(dets) == 0:
                    continue  # BLANK -> skip; do NOT open image

                n_images_with_dets += 1

                file_field = im.get("file")
                abs_image = to_abs_image_path(file_field, raw_btcf_dir) if file_field else None

                # EXIF read only for non-blank images
                capture_dt, capture_dt_source = exif_capture_datetime(abs_image)
                if capture_dt is None:
                    n_exif_missing += 1

                for i, d in enumerate(dets):
                    n_dets += 1

                    cat = str(d.get("category")) if d.get("category") is not None else None
                    conf = d.get("conf", None)

                    cls = d.get("classifications", None)
                    top_cls_id, top_cls_score, _cls_raw = flatten_classifications(cls)
                    top_cls_label = cls_cats.get(str(top_cls_id), top_cls_id) if top_cls_id is not None else None

                    det_rows.append({
                        "site": site,
                        "date_range": date_range,
                        "image_path_abs": abs_image,
                        "capture_datetime": capture_dt,
                        "capture_datetime_source": capture_dt_source,
                        "custom_model_name": model_name,
                        "detection_index": i,
                        "category_id": cat,
                        "category_label": det_cats.get(cat, cat) if cat is not None else None,
                        "confidence": conf,
                        "top_classification_id": top_cls_id,
                        "top_classification_label": top_cls_label,
                        "top_classification_score": top_cls_score,
                    })

    det_df = pd.DataFrame(det_rows)

    # Optional run provenance; keep or remove
    run_day = datetime.now().strftime("%Y-%m-%d")
    det_df.insert(0, "run_day", run_day)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_name = build_output_filename(site_sel if selected_sites else None)
    det_path = out_dir / out_name
    det_df.to_csv(det_path, index=False)

    print("\nDONE")
    print(f"RAW_ROOT: {RAW_ROOT}")
    if selected_sites:
        print(f"Selected sites: {len(selected_sites)} (e.g., {selected_sites[:5]}{'...' if len(selected_sites)>5 else ''})")
    if prefix_rel:
        print(f"Prefix used: {prefix_rel}")
    print(f"JSON files scanned:           {n_json:,}")
    print(f"Images listed in JSONs:       {n_images:,}")
    print(f"Images with detections:       {n_images_with_dets:,}")
    print(f"Detection rows written:       {n_dets:,}")
    print(f"Nonblank images missing EXIF: {n_exif_missing:,}")
    print(f"Wrote CSV: {det_path}")

    return det_df


def parse_args():
    p = argparse.ArgumentParser(
        description="Merge MD JSON to detections CSV (nonblank only) with EXIF timestamps (minimal columns)"
    )
    p.add_argument(
        "--run-prefix-rel",
        default=None,
        help='Optional relative prefix under RAW_ROOT to limit merge (e.g. "site01" or "site01/2025-04-29_2025-06-16")'
    )
    p.add_argument(
        "--site-sel",
        default=None,
        help='Optional site selector, e.g. "1-84" or "1,2,5-8,84" or "site01,site02". When set, output filename gets _site_sel.'
    )
    p.add_argument(
        "--out-dir",
        default=r"Z:\East\output",
        help=r'Output folder for merged CSVs (default: Z:\East\output)'
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    merge_all(prefix_rel=args.run_prefix_rel, out_dir=Path(args.out_dir), site_sel=args.site_sel)