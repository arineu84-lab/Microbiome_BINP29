#!/usr/bin/env python
import pandas as pd
from pathlib import Path

in_path = Path("raw_data/metadata.tsv")
out_path = Path("raw_data/filtered_meta.tsv")

# minimal columns we try to keep (lowercase names)
cols_keep = [
    "run_accession", "sample_accession", "country", "lat", "lon",
    "library_strategy", "tax_lineage",
    "host_body_site", "sample_description", "description",
]

def first_nonnull(*vals):
    for v in vals:
        if pd.notna(v) and str(v).strip() != "":
            return v
    return pd.NA

def main():
    df = pd.read_csv(in_path, sep="\t", dtype=str, low_memory=False)

    # keep only columns that exist (safe subset)
    have = [c for c in cols_keep if c in df.columns]
    df = df[have].copy()

    # numeric coords (keep original values if already numeric strings)
    for c in ("lat", "lon"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # build a lowercase catch-all text field to detect body-site keywords
    text_cols = [c for c in df.columns if c not in ["lat", "lon", "run_accession", "sample_accession", "country"]]
    df["_concat"] = df[text_cols].fillna("").agg(" ".join, axis=1).str.lower()

    # remove known off-targets 
    before = len(df)
    df = df[~df["_concat"].str.contains("door handle", na=False)]
    removed = before - len(df)
    print(f"[info] removed {removed} 'door handle' rows")

    # extended keyword detection 
    df["k_palm"]    = df["_concat"].str.contains(r"\bpalm\b", na=False)
    df["k_hand"]    = df["_concat"].str.contains(r"\bhand\b", na=False)
    df["k_foot"]    = df["_concat"].str.contains(r"\bfoot\b|\bfeet\b|\bplantar\b", na=False)
    df["k_face"]    = df["_concat"].str.contains(r"\bface\b|\bfacial\b", na=False)
    df["k_scalp"]   = df["_concat"].str.contains(r"\bscalp\b", na=False)
    df["k_armpit"]  = df["_concat"].str.contains(r"\baxilla\b|\barmpit\b", na=False)
    df["k_forearm"] = df["_concat"].str.contains(r"\bforearm\b", na=False)
    df["k_skin"]    = df["_concat"].str.contains(r"\bskin\b", na=False)

    def label_body_site(row):
        if row["k_palm"]:    return "palm"
        if row["k_hand"]:    return "hand"
        if row["k_foot"]:    return "foot"
        if row["k_face"]:    return "face"
        if row["k_scalp"]:   return "scalp"
        if row["k_armpit"]:  return "armpit"
        if row["k_forearm"]: return "forearm"
        if row["k_skin"]:    return "skin_other"
        return "other"

    df["body_site_label"] = df.apply(label_body_site, axis=1)

    # drop helpers
    drop_cols = ["_concat","k_palm","k_hand","k_foot","k_face","k_scalp","k_armpit","k_forearm","k_skin"]
    df.drop(columns=[c for c in drop_cols if c in df.columns], inplace=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, sep="\t", index=False)
    print(f"[ok] wrote {out_path}")
    print(df["body_site_label"].value_counts())

if __name__ == "__main__":
    main()
