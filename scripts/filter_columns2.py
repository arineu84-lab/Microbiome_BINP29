#!/usr/bin/env python
import pandas as pd
from pathlib import Path

in_path = Path("raw_data/metadata.tsv")
out_path = Path("raw_data/filtered_meta2.tsv")

# columns needed (soft-coded; script will keep only those that exist)
cols = [
    "run_accession", "sample_accession", "country", "lat", "lon",
    "library_strategy", "tax_lineage",
    "host_body_site", "sample_description", "description"
]

def first_nonnull(*vals):
    for v in vals:
        if pd.notna(v) and str(v).strip() != "":
            return v
    return pd.NA

def safe_to_numeric(series: pd.Series) -> pd.Series:
    """convert to numeric if possible; otherwise leave unchanged (fixes deprecated errors='ignore')."""
    try:
        return pd.to_numeric(series)
    except Exception:
        return series

def main():
    # read as strings to avoid unintended parsing
    df = pd.read_csv(in_path, sep="\t", dtype=str, low_memory=False)

    # keep only available columns (soft-coding)
    have_cols = [c for c in cols if c in df.columns]
    df = df[have_cols].copy()

    # convert coordinates safely (no FutureWarning)
    for c in ("lat", "lon"):
        if c in df.columns:
            df[c] = safe_to_numeric(df[c])

    # build a lowercase concatenated text field (exclude obvious numeric/id columns)
    text_exclude = {"lat", "lon", "run_accession", "sample_accession", "country"}
    text_cols = [c for c in df.columns if c not in text_exclude]
    if text_cols:
        df["_concat"] = df[text_cols].fillna("").agg(" ".join, axis=1).str.lower()
    else:
        df["_concat"] = ""

    # remove door handle samples (keep this non–body-site filter)
    before = len(df)
    df = df[~df["_concat"].str.contains("door handle", case=False, na=False)]
    removed = before - len(df)
    print(f"[info] removed {removed} 'door handle' samples")

    # simple site indicators derived from text only (no filtering by these)
    df["is_palm"] = df["_concat"].str.contains(r"\bpalm\b", na=False)
    df["is_hand"] = df["_concat"].str.contains(r"\bhand\b", regex=True, na=False)
    df["mentions_skin"] = df["_concat"].str.contains(r"\bskin\b", na=False)

    # keep the body_site_label column for later use (no filtering is applied)
    def label_body_site(row):
        if row["is_palm"]:
            return "palm"
        if row["is_hand"]:
            return "hand"
        if row["mentions_skin"]:
            return "skin_other"
        return "other"

    df["body_site_label"] = df.apply(label_body_site, axis=1)

    # clean up helper column
    df.drop(columns=["_concat"], inplace=True)

    # write out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, sep="\t", index=False)
    print(f"[ok] new filtered metadata saved to {out_path}")

    # quick summary (won’t crash; column exists)
    print(df["body_site_label"].value_counts())

if __name__ == "__main__":
    main()