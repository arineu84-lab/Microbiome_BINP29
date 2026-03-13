#!/usr/bin/env python

import os
import sys
import json
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import shape, Point

input_file = "raw_data/filtered_meta.tsv"
geo_file = "data/ne_countries.geojson"
plots = "plots"
os.makedirs(plots, exist_ok=True)

df = pd.read_csv(input_file, sep="\t", dtype=str)

# Ensure coordinates exist
if "lat" not in df.columns or "lon" not in df.columns:
    sys.exit("ERROR: filtered_meta.tsv must contain columns 'lat' and 'lon'.")

df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
df["lon"] = pd.to_numeric(df["lon"], errors="coerce")

# Keep only rows with valid coordinates
df = df.dropna(subset=["lat", "lon"])
df = df[(df["lat"].between(-90, 90)) & (df["lon"].between(-180, 180))]

if df.empty:
    sys.exit("ERROR: All coordinate rows are invalid. Check lat/lon values.")

print(f"[INFO] Using {len(df)} rows with valid coordinates.")

# IDs to preserve
id_cols = [c for c in ["run_accession", "sample_accession"] if c in df.columns]

# build the data fram for geo location
points = gpd.GeoDataFrame(
    df[id_cols + ["lat", "lon"]],
    geometry=[Point(x, y) for x, y in zip(df["lon"], df["lat"])],
    crs="EPSG:4326"
)

# set country boundaries
if not os.path.exists(geo_file):
    sys.exit(f"ERROR: GeoJSON file missing: {geo_file}")

print("[INFO] Loading Natural Earth GeoJSON manually...")

with open(geo_file, "r") as f:
    data = json.load(f)

records = []
for feat in data["features"]:
    props = feat["properties"]
    geom = shape(feat["geometry"])

    # Auto-detect country label from properties
    name = (props.get("ADMIN")
            or props.get("admin")
            or props.get("name")
            or props.get("NAME")
            or "UNKNOWN")

    records.append({"country": name, "geometry": geom})

world = gpd.GeoDataFrame(records, crs="EPSG:4326")

print(f"[INFO] Loaded {len(world)} country polygons.")

# Join spatial coordinates to polygon
print("[INFO] Performing spatial join...")

joined = gpd.sjoin(points, world, how="left", predicate="within")

matched = joined.dropna(subset=["country"])
unmatched = joined[joined["country"].isna()]

# Save unmatched if any
if not unmatched.empty:
    out_unmatched = "raw_data/unmatched_points.tsv"
    unmatched[id_cols + ["lat", "lon"]].to_csv(out_unmatched, sep="\t", index=False)
    print(f"[INFO] Saved unmatched → {out_unmatched}")

# Count countries
counts = matched["country"].value_counts()

if counts.empty:
    sys.exit("ERROR: No points matched any country polygons. Check coordinates.")

out_counts = "raw_data/country_counts_from_coords.tsv"
counts.to_frame("count").assign(
    percent=(counts / counts.sum() * 100).round(2)
).to_csv(out_counts, sep="\t")
print(f"[OK] Saved country counts → {out_counts}")

# Generate barplot
plt.figure(figsize=(12, max(6, 0.3 * len(counts))))
counts.sort_values().plot(kind="barh", color="#1b2d4e")
plt.title("Number of Samples per Country")
plt.xlabel("Sample Count")
plt.tight_layout()

out_plot = os.path.join(plots, "country_distribution.png")
plt.savefig(out_plot, dpi=300)
plt.close()

print(f"[OK] Plot saved → {out_plot}")
print("[DONE]")