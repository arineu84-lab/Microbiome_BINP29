#!/usr/bin/env python
# select_samples.py

import argparse
from pathlib import Path
import pandas as pd

meta_file = Path("raw_data/filtered_meta.tsv")
out_file  = Path("raw_data/selected_samples.tsv")

NORDIC_BBOXES = {
    "denmark": {"lat_min": 54.3, "lat_max": 58.1, "lon_min": 7.9,  "lon_max": 15.6},  
    "sweden":  {"lat_min": 55.0, "lat_max": 69.5, "lon_min": 11.0, "lon_max": 24.5},
    "norway":  {"lat_min": 58.0, "lat_max": 71.5, "lon_min": 4.5,  "lon_max": 31.5},  
    "finland": {"lat_min": 59.0, "lat_max": 70.5, "lon_min": 19.0, "lon_max": 32.5},
}

def _coords_in_any_nordic(df, lat_col="lat", lon_col="lon"):
    """Return boolean mask: True if point falls inside any Nordic bbox."""
    import numpy as np
    mask_any = np.zeros(len(df), dtype=bool)
    for bbox in NORDIC_BBOXES.values():
        m = (
            df[lat_col].between(bbox["lat_min"], bbox["lat_max"], inclusive="both")
            & df[lon_col].between(bbox["lon_min"], bbox["lon_max"], inclusive="both")
        )
        mask_any |= m
    return mask_any

def pick_from(df, country, n, strategy):
    """
    Return up to n rows selected ONLY by coordinates inside the Nordic region,
    with non-null lat/lon and a library_strategy matching 'strategy' (substring, case-insensitive).

    NOTE: 'country' argument is intentionally ignored to enforce coordinate-only selection.
    """
    # coords present
    mask_coords = df["lat"].notna() & df["lon"].notna()

    # in any Nordic bbox (Denmark, Sweden, Norway, Finland)
    mask_nordics = _coords_in_any_nordic(df, "lat", "lon")

    # match strategy by substring 
    mask_strategy = df["library_strategy"].str.contains(strategy.lower(), na=False)

    subset = df[mask_coords & mask_nordics & mask_strategy]

    return subset.head(n).copy()

def main():
    ap = argparse.ArgumentParser(description="select n samples from a country, with optional fallbacks")
    ap.add_argument("--country", default="denmark", help="primary country (lowercase)")
    ap.add_argument("--n", type=int, default=3, help="number to select")
    ap.add_argument("--strategy", default="amplicon", help="strategy substring to match (e.g., amplicon)")
    ap.add_argument("--fallback", default="", help="comma-separated fallback countries, in order (e.g., germany,austria,sweden)")
    ap.add_argument("--require-coords", action="store_true", default=True)
    args = ap.parse_args()

    df = pd.read_csv(meta_file, sep="\t", dtype=str)
    # normalise
    for col in ("lat","lon"):
        df[col] = pd.to_numeric(df.get(col), errors="coerce")
    df["library_strategy"] = df["library_strategy"].astype(str).str.lower()
    df["country"] = df.get("country", "").astype(str)

    # try primary country
    picked = pick_from(df, args.country, args.n, args.strategy)

    # try fallbacks if needed
    if len(picked) < args.n and args.fallback.strip():
        for c in [c.strip() for c in args.fallback.split(",") if c.strip()]:
            if len(picked) >= args.n:
                break
            need = args.n - len(picked)
            extra = pick_from(df, c, need, args.strategy)
            if not extra.empty:
                picked = pd.concat([picked, extra], ignore_index=True)

    # last resort: any country with coords & amplicon
    if len(picked) < args.n:
        need = args.n - len(picked)
        mask_coords = df["lat"].notna() & df["lon"].notna()
        mask_strategy = df["library_strategy"].str.contains(args.strategy.lower(), na=False)
        any_country = df[mask_coords & mask_strategy].head(need).copy()
        picked = pd.concat([picked, any_country], ignore_index=True)

    if picked.empty:
        raise SystemExit(f"[error] could not select any samples for strategy '{args.strategy}'")

    # write
    out_file.parent.mkdir(parents=True, exist_ok=True)
    picked.to_csv(out_file, sep="\t", index=False)

    print(f"[ok] selected {len(picked)} samples → {out_file}")
    cols = [c for c in ["run_accession","country","country_from_coords","body_site_label","lat","lon","library_strategy"] if c in picked.columns]
    print(picked[cols])

if __name__ == "__main__":
    main()