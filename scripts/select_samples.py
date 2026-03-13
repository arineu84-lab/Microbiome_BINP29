#!/usr/bin/env python

import pandas as pd
from pathlib import Path

meta_file = Path("raw_data/filtered_meta.tsv")
output = Path("raw_data/selected_samples.tsv")

# Countries of interest
selected_countries = ["Germany", "Denmark", "France", "Austria"]

# Minimum samples to select per country
N = 2

df = pd.read_csv(meta_file, sep="\t", dtype=str)

# Ensure numeric coords
df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
df["lon"] = pd.to_numeric(df["lon"], errors="coerce")

# Keep samples with valid coordinates
df = df.dropna(subset=["lat", "lon"])

# select samples with body_site_label (hand, palm, skin_other, etc.)
df = df[df["body_site_label"].notna()]

# keep only 16S samples
df = df[df["library_strategy"] == "AMPLICON"]

selected_rows = []

for country in selected_countries:
    subset = df[df["country"] == country]

    if subset.empty:
        print(f"[WARN] No samples found for {country}.")
        continue

    # If many samples exist, we take the *first 3* for reproducibility
    picked = subset.head(N)
    selected_rows.append(picked)

    print(f"[OK] Selected {len(picked)} samples from {country}")

# Combine selections
if selected_rows:
    final_df = pd.concat(selected_rows, ignore_index=True)
else:
    raise SystemExit("[ERROR] No samples selected for any target country.")

# Save output
output.parent.mkdir(exist_ok=True, parents=True)
final_df.to_csv(output, sep="\t", index=False)

print("\n[OK] Final selection saved to:", output)
print(final_df[["run_accession", "country", "body_site_label", "lat", "lon"]])