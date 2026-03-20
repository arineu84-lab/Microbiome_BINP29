#!/usr/bin/env python
import argparse
from pathlib import Path
import pandas as pd

meta_file = Path("raw_data/filtered_meta.tsv")
out_file  = Path("raw_data/selected_samples.tsv")

def pick_from(df, country, n, strategy):
    """return up to n rows from df for country (case-insensitive), coords present, strategy match by substring"""
    if "country_from_coords" in df.columns:
        mask_country = df["country_from_coords"].str.lower() == country.lower()
    else:
        mask_country = df["country"].str.lower() == country.lower()
    mask_coords = df["lat"].notna() & df["lon"].notna()
    # match strategy by substring, all lowercase
    mask_strategy = df["library_strategy"].str.contains(strategy.lower(), na=False)
    subset = df[mask_country & mask_coords & mask_strategy]
    # deterministic: first n rows
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
    # normalize
    for col in ("lat","lon"):
        df[col] = pd.to_numeric(df.get(col), errors="coerce")
    df["library_strategy"] = df["library_strategy"].astype(str).str.lower()
    df["country"] = df.get("country", "").astype(str)

    # 1) try primary country
    picked = pick_from(df, args.country, args.n, args.strategy)

    # 2) try fallbacks if needed
    if len(picked) < args.n and args.fallback.strip():
        for c in [c.strip() for c in args.fallback.split(",") if c.strip()]:
            if len(picked) >= args.n:
                break
            need = args.n - len(picked)
            extra = pick_from(df, c, need, args.strategy)
            if not extra.empty:
                picked = pd.concat([picked, extra], ignore_index=True)

    # 3) last resort: any country with coords & amplicon
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