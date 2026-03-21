#!/usr/bin/env python
# sequence_type.py 

import os
import json
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point, shape

meta_file = "raw_data/filtered_meta.tsv"
geo_file = "data/ne_countries.geojson"
plots = "plots/country_worldmap.png"
os.makedirs("plots", exist_ok=True)

df = pd.read_csv(meta_file, sep="\t", dtype=str)

df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
df = df.dropna(subset=["lat", "lon"])

print(f"[INFO] Metadata rows with valid coordinates: {len(df)}")

# Assigning sequencing type
amplicon = ["AMPLICON"]
shotgun = ["WGS", "WGA", "WXS", "WCS"]

def classify(x):
    if x in amplicon:
        return "16S_amplicon"
    elif x in shotgun:
        return "shotgun_metagenome"
    else:
        return "other"

df["seq_type"] = df["library_strategy"].apply(classify)

# Keep only main categories
df = df[df["seq_type"].isin(["16S_amplicon", "shotgun_metagenome"])]

if df.empty:
    raise SystemExit("No 16S or shotgun samples found in metadata.")

print("[INFO] Sequencing types included:")
print(df["seq_type"].value_counts())

# Create geo fame
points = gpd.GeoDataFrame(
    df[["run_accession", "lat", "lon", "seq_type"]],
    geometry=[Point(lon, lat) for lon, lat in zip(df["lon"], df["lat"])],
    crs="EPSG:4326")

# load country boundaries
print("[INFO] Loading Natural Earth GeoJSON manually...")

with open(geo_file , "r") as f:
    data = json.load(f)

records = []
for feature in data["features"]:
    props = feature["properties"]
    geom = shape(feature["geometry"])

    # Auto‑detect polygon label
    name = (props.get("ADMIN")
            or props.get("admin")
            or props.get("name")
            or props.get("NAME")
            or "UNKNOWN")

    records.append({"country": name, "geometry": geom})

world = gpd.GeoDataFrame(records, crs="EPSG:4326")

print(f"[INFO] Loaded {len(world)} country polygons.")

# assign points to country polygon
print("[INFO] Spatial join: assigning samples to countries...")
joined = gpd.sjoin(points, world, how="left", predicate="within")

# Remove samples located in the United States
joined = joined[joined["country"] != "United States of America"]

# Remove unmatched points 
joined = joined.dropna(subset=["country"])

if joined.empty:
    raise SystemExit("[ERROR] No samples matched any country polygons.")

# count sequencing type per country
counts = (
    joined.groupby(["country", "seq_type"])
          .size()
          .reset_index(name="count"))

# switch into wide format
wide = counts.pivot(
    index="country", columns="seq_type", values="count"
).fillna(0)

# Merge into world polygons for plotting
world = world.merge(wide, how="left", on="country")
world["16S_amplicon"] = world["16S_amplicon"].fillna(0)
world["shotgun_metagenome"] = world["shotgun_metagenome"].fillna(0)

# Generate plots
fig, axes = plt.subplots(2, 1, figsize=(10, 20))

titles = {"16S_amplicon": "16S rRNA Amplicon Samples per Country",
    "shotgun_metagenome": "Shotgun Metagenome Samples per Country"}

for ax, col in zip(axes, ["16S_amplicon", "shotgun_metagenome"]):
    world.plot(
        column=col,
        ax=ax,
        cmap="YlOrRd",
        legend=True,
        legend_kwds={"shrink": 0.25},
        edgecolor="black",
        linewidth=0.2,
        missing_kwds={"color": "lightgrey"})
    ax.set_axis_off()
    ax.set_title(titles[col], fontsize=14)

plt.tight_layout()
plt.savefig(plots, dpi=300)
plt.close()
print(f"[OK] Saved choropleth → {plots}")