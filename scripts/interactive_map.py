#!/usr/bin/env python3

import json
from pathlib import Path
import folium
import pandas as pd

root = Path(".")  # assume script is run from project root

all_meta   = root / "raw_data"   / "filtered_meta.tsv"
sel_meta   = root / "raw_data"   / "selected_samples.tsv"
geojson    = root / "data"       / "ne_countries.geojson"
krona_dir  = root / "results"    / "krona_html"
out_html   = root / "results"    / "final_interactive_map.html"


# load metadata, filter to amplicon (16S)
df_all = pd.read_csv(all_meta, sep="\t", dtype=str)

country_col = ("country_from_coords"
    if "country_from_coords" in df_all.columns
    else "country")

df_amp = df_all[df_all["library_strategy"] == "AMPLICON"].copy()

# count amplicon samples by country
counts = (df_amp.groupby(country_col)
          .size()
          .reset_index(name="count")
          .rename(columns={country_col: "country"}))


# load selected samples
df_sel = pd.read_csv(sel_meta, sep="\t", dtype=str)

# ensure numeric coords
for col in ("lat", "lon"):
    df_sel[col] = pd.to_numeric(df_sel[col], errors="coerce")

df_sel = df_sel.dropna(subset=["lat", "lon"]).copy()

# color for selected samples (body site)
site_color = {
    "hand": "red",
    "palm": "orange",
    "skin_other": "blue",
    "unknown": "gray",}

def pick_color(label: str) -> str:
    if not isinstance(label, str):
        return "gray"
    return site_color.get(label.strip().lower(), "gray")


# load geojson and set stable join key
with open(geojson, "r") as f:
    gj = json.load(f)

for feature in gj["features"]:
    props = feature.get("properties", {})
    props["country_key"] = (
        props.get("ADMIN")
        or props.get("admin")
        or props.get("name")
        or props.get("NAME")
        or props.get("NAME_EN")
        or "UNKNOWN")
    feature["properties"] = props


# generate folium map
m = folium.Map(
    location=[20, 0],
    zoom_start=2,
    tiles="CartoDB positron")

folium.TileLayer("OpenStreetMap").add_to(m)
folium.TileLayer("CartoDB dark_matter").add_to(m)


# build choropleth for 16S counts
palette = "PuBuGn"   # choose any: YlOrRd, OrRd, BuPu, YlGn, BuGn, etc.

choropleth = folium.Choropleth(
    geo_data=gj,
    data=counts,
    columns=["country", "count"],
    key_on="feature.properties.country_key",
    fill_color=palette,
    fill_opacity=0.85,
    line_opacity=0.3,
    nan_fill_color="lightgray",
    name="16S amplicon per country",
    legend_name="16S samples per country",
    overlay=True,
    control=True,).add_to(m)

tooltip = folium.GeoJsonTooltip(
    fields=["country_key"],
    aliases=["country:"],)
tooltip.add_to(choropleth.geojson)

# selected samples with krona popups
sel_layer = folium.FeatureGroup(
    name="selected samples (krona plots)",
    show=True)

for _, row in df_sel.iterrows():

    sample = row["run_accession"]
    lat = float(row["lat"])
    lon = float(row["lon"])
    country = row.get("country_from_coords", row.get("country", "unknown"))
    body = (row.get("body_site_label") or "unknown").strip().lower()
    color = pick_color(body)

    krona_file = krona_dir / f"{sample}.krona.html"

    # compute relative path so it works on mac/linux/windows
    try:
        relative_link = krona_file.relative_to(out_html.parent)
    except Exception:
        relative_link = krona_file.name

    # create anchor tag
    if krona_file.exists():
        link_html = f"<a href='{relative_link}' target='_blank'>open krona plot</a>"
    else:
        link_html = f"<i>(missing: {relative_link})</i>"

    popup_html = f"""
    <b>{sample}</b><br>
    country: {country}<br>
    body site: {body}<br>
    {link_html}
    """

    folium.CircleMarker(
        location=[lat, lon],
        radius=8,
        color="black",
        weight=2,
        fill=True,
        fill_color=color,
        fill_opacity=0.95,
        tooltip=f"{sample} ({country}, {body})",
        popup=folium.Popup(popup_html, max_width=320),
    ).add_to(sel_layer)

sel_layer.add_to(m)

# legend for selected sample colors
legend_html = """
<div style="
  position: fixed;
  bottom: 20px; left: 20px; z-index: 9999;
  background: white; padding: 10px 12px;
  border: 1px solid #bbb; border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.3);
  font-size: 13px;">
<b>selected: body site</b><br>
<span style='display:inline-block;width:10px;height:10px;background:red;border:1px solid #333;margin-right:6px;'></span> hand<br>
<span style='display:inline-block;width:10px;height:10px;background:orange;border:1px solid #333;margin-right:6px;'></span> palm<br>
<span style='display:inline-block;width:10px;height:10px;background:blue;border:1px solid #333;margin-right:6px;'></span> skin_other<br>
<span style='display:inline-block;width:10px;height:10px;background:gray;border:1px solid #333;margin-right:6px;'></span> unknown<br>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# save map
out_html.parent.mkdir(parents=True, exist_ok=True)
m.save(str(out_html))

print("[ok] final interactive map saved to:", out_html)
print("copy this file AND the krona_html/ folder to your mac for popups to work.")
print("or serve locally with:")
print("  cd results && python3 -m http.server 8000")
print("  open http://localhost:8000/final_interactive_map.html")
