from __future__ import annotations

import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

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

# =========================
# MAIN MERGE
# =========================
def merge_all(prefix_rel: Optional[str], out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    search_root = RAW_ROOT
    if prefix_rel:
        search_root = RAW_ROOT / Path(prefix_rel)
        if not search_root.exists():
            raise FileNotFoundError(f"Prefix path does not exist under RAW_ROOT: {search_root}")

    json_files = sorted(search_root.rglob("image_recognition_file.json"))

    image_rows: List[Dict[str, Any]] = []
    det_rows: List[Dict[str, Any]] = []

    for jf in json_files:
        rel_json = normalize_rel(jf, RAW_ROOT)
        site, date_range, btcf = infer_site_date_btcf_from_rel(rel_json)
        raw_btcf_dir = jf.parent  # .../106_BTCF

        try:
            data = safe_json_load(jf)
        except Exception as e:
            image_rows.append({
                "json_path": str(jf),
                "rel_json_path": rel_json,
                "site": site,
                "date_range": date_range,
                "btcf_folder": btcf,
                "parse_error": str(e)
            })
            continue

        info = data.get("info", {}) or {}
        det_cats = {str(k): v for k, v in (data.get("detection_categories") or {}).items()}
        cls_cats = {str(k): v for k, v in (data.get("classification_categories") or {}).items()}

        addax_meta = (info.get("addaxai_metadata") or {}) if isinstance(info, dict) else {}
        model_name = None
        try:
            cm = addax_meta.get("custom_model_info") or {}
            model_name = cm.get("name") or None
        except Exception:
            model_name = None

        images = data.get("images", []) or []
        for im in images:
            file_field = im.get("file")
            abs_image = to_abs_image_path(file_field, raw_btcf_dir) if file_field else None

            dets = im.get("detections", []) or []
            max_conf = None
            max_conf_animal = None
            n_det = len(dets)
            n_animal = 0

            for d in dets:
                conf = d.get("conf", None)
                cat = str(d.get("category")) if d.get("category") is not None else None
                try:
                    if conf is not None:
                        max_conf = float(conf) if max_conf is None else max(max_conf, float(conf))
                except Exception:
                    pass
                if cat == "1":
                    n_animal += 1
                    try:
                        if conf is not None:
                            max_conf_animal = float(conf) if max_conf_animal is None else max(max_conf_animal, float(conf))
                    except Exception:
                        pass

            image_rows.append({
                "json_path": str(jf),
                "rel_json_path": rel_json,
                "site": site,
                "date_range": date_range,
                "btcf_folder": btcf,
                "raw_btcf_dir": str(raw_btcf_dir),
                "image_file": file_field,
                "image_path_abs": abs_image,
                "n_detections": n_det,
                "n_animal_detections": n_animal,
                "max_conf": max_conf,
                "max_conf_animal": max_conf_animal,
                "info_format_version": info.get("format_version") if isinstance(info, dict) else None,
                "info_detector": info.get("detector") if isinstance(info, dict) else None,
                "addax_version": addax_meta.get("version") if isinstance(addax_meta, dict) else None,
                "custom_model_name": model_name,
            })

            for i, d in enumerate(dets):
                bbox = d.get("bbox", [None, None, None, None])
                cat = str(d.get("category")) if d.get("category") is not None else None
                conf = d.get("conf", None)
                cls = d.get("classifications", None)
                top_cls_id, top_cls_score, cls_raw = flatten_classifications(cls)
                top_cls_label = cls_cats.get(str(top_cls_id), top_cls_id) if top_cls_id is not None else None

                det_rows.append({
                    "json_path": str(jf),
                    "rel_json_path": rel_json,
                    "site": site,
                    "date_range": date_range,
                    "btcf_folder": btcf,
                    "raw_btcf_dir": str(raw_btcf_dir),
                    "image_file": file_field,
                    "image_path_abs": abs_image,
                    "detection_index": i,
                    "category_id": cat,
                    "category_label": det_cats.get(cat, cat) if cat is not None else None,
                    "confidence": conf,
                    "bbox_xmin": bbox[0] if isinstance(bbox, list) and len(bbox) > 0 else None,
                    "bbox_ymin": bbox[1] if isinstance(bbox, list) and len(bbox) > 1 else None,
                    "bbox_width": bbox[2] if isinstance(bbox, list) and len(bbox) > 2 else None,
                    "bbox_height": bbox[3] if isinstance(bbox, list) and len(bbox) > 3 else None,
                    "top_classification_id": top_cls_id,
                    "top_classification_label": top_cls_label,
                    "top_classification_score": top_cls_score,
                    "classifications_raw": cls_raw,
                })

    images_df = pd.DataFrame(image_rows)
    det_df = pd.DataFrame(det_rows)

    run_id = datetime.now().strftime("mdmerge_%Y-%m-%d_%H%M%S")
    created_at = datetime.now().isoformat(timespec="seconds")

    for df in (images_df, det_df):
        df.insert(0, "run_id", run_id)
        df.insert(1, "created_at", created_at)
        df.insert(2, "raw_root", str(RAW_ROOT))
        df.insert(3, "processed_root", str(PROCESSED_ROOT))

    out_dir.mkdir(parents=True, exist_ok=True)
    images_path = out_dir / f"md_images_{run_id}.csv"
    det_path = out_dir / f"md_detections_{run_id}.csv"

    images_df.to_csv(images_path, index=False)
    det_df.to_csv(det_path, index=False)

    print(f"RAW_ROOT: {RAW_ROOT}")
    print(f"Found {len(json_files)} image_recognition_file.json files")
    print(f"Wrote images CSV:     {images_path} ({len(images_df):,} rows)")
    print(f"Wrote detections CSV: {det_path} ({len(det_df):,} rows)")

    return images_df, det_df

def parse_args():
    p = argparse.ArgumentParser(description="Merge image_recognition_file.json outputs to CSVs for R")
    p.add_argument(
        "--run-prefix-rel",
        default=None,
        help='Optional relative prefix under RAW_ROOT to limit merge (e.g. "site01" or "site01/2025-04-29_2025-06-16")'
    )
    p.add_argument(
        "--out-dir",
        default=r"Z:\East\output",
        help=r'Output folder for merged CSVs (default: Z:\East\output)'
    )
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    merge_all(prefix_rel=args.run_prefix_rel, out_dir=Path(args.out_dir))
