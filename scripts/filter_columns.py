#!/usr/bin/env python
import pandas as pd
from pathlib import Path

IN = Path("raw_data/metadata.tsv")
OUT = Path("raw_data/filtered_meta.tsv")

# Columns needed
COLS = ["run_accession", "sample_accession", "country", "lat", "lon",
    "library_strategy", "tax_lineage",
    "host_body_site", "sample_description", "description"]

def first_nonnull(*vals):
    for v in vals:
        if pd.notna(v) and str(v).strip() != "":
            return v
    return pd.NA

def main():
    df = pd.read_csv(IN, sep="\t", dtype=str, low_memory=False)

    have_cols = [c for c in COLS if c in df.columns]
    df = df[have_cols].copy()

    # Convert coordinates
    for c in ("lat", "lon"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="ignore")

    # Prepare text concat fields
    text_cols = [c for c in df.columns if c not in ["lat", "lon", "run_accession", "sample_accession", "country"]]
    df["_concat"] = df[text_cols].fillna("").agg(" ".join, axis=1).str.lower()

    # --- REMOVE DOOR HANDLE SAMPLES ---
    before = len(df)
    df = df[~df["_concat"].str.contains("door handle", case=False, na=False)]
    removed = before - len(df)
    print(f"[INFO] Removed {removed} 'door handle' samples")

    # Identify palm / hand
    df["is_palm"] = df["_concat"].str.contains("palm", na=False)
    df["is_hand"] = df["_concat"].str.contains(r"\bhand\b", regex=True, na=False)
    df["mentions_skin"] = df["_concat"].str.contains("skin", na=False)

    def label_body_site(row):
        if row["is_palm"]:
            return "palm"
        if row["is_hand"]:
            return "hand"
        if row["mentions_skin"]:
            return "skin_other"
        return "other"

    df["body_site_label"] = df.apply(label_body_site, axis=1)

    df.drop(columns=["_concat"], inplace=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, sep="\t", index=False)
    print(f"[OK] New filtered metadata saved to {OUT}")
    print(df["body_site_label"].value_counts())

if __name__ == "__main__":
    main()