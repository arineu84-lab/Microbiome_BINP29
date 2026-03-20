#!/usr/bin/env python
from pathlib import Path
import os
import pandas as pd
import folium
from folium.plugins import MarkerCluster

root = Path(".")
all_meta = root / "raw_data" / "filtered_meta.tsv"
sel_meta = root / "raw_data" / "selected_samples.tsv"
geojson = root / "data" / "ne_countries.geojson"  
krona_dir = root / "results" / "krona_html"
out_html = root / "results" / "final_interactive_map.html"

def _detect_coord_columns(df: pd.DataFrame) -> tuple[str, str]:
    """
    pick (lat_col, lon_col) from common possibilities.
    raises a clear error if none are present.
    """
    candidates = [
        ("lat", "lon"),
        ("latitude", "longitude"),
        ("geo_latitude", "geo_longitude"),
        ("lat_deg", "lon_deg"),
    ]
    for la, lo in candidates:
        if la in df.columns and lo in df.columns:
            return la, lo
    raise ValueError(
        "no latitude/longitude columns found. "
        "looked for: lat/lon, latitude/longitude, geo_latitude/geo_longitude, lat_deg/lon_deg"
    )

_color_map = {
    "hand": "#e41a1c",
    "palm": "#ff7f00",
    "foot": "#377eb8",
    "face": "#984ea3",
    "armpit": "#4daf4a",
    "scalp": "#a65628",
    "forearm": "#f781bf",
    "skin_other": "#7f7f7f",
    "other": "#cccccc",
}
def pick_color(body_site: str) -> str:
    b = (body_site or "other").strip().lower()
    return _color_map.get(b, _color_map["other"])

# load metadata, filter to amplicon (16S)
df_all = pd.read_csv(all_meta, sep="\t", dtype=str)

country_col = ("country_from_coords"
    if "country_from_coords" in df_all.columns
    else "country")

# case-insensitive 
if "library_strategy" not in df_all.columns:
    raise ValueError("expected column 'library_strategy' not found in filtered_meta.tsv")

df_all["library_strategy_norm"] = df_all["library_strategy"].str.upper()
df_amp = df_all[df_all["library_strategy_norm"] == "AMPLICON"].copy()

# id column
id_col = (
    "run_accession" if "run_accession" in df_amp.columns
    else ("sample_accession" if "sample_accession" in df_amp.columns else None)
)
if id_col is None:
    raise ValueError("could not find an id column (run_accession or sample_accession) in filtered_meta.tsv")

# coordinates for all amplicon samples
lat_col, lon_col = _detect_coord_columns(df_amp)
for col in (lat_col, lon_col):
    df_amp[col] = pd.to_numeric(df_amp[col], errors="coerce")
df_amp_coords = df_amp.dropna(subset=[lat_col, lon_col]).copy()

# load selected samples (for krona links)
if sel_meta.exists() and sel_meta.stat().st_size > 0:
    df_sel = pd.read_csv(sel_meta, sep="\t", dtype=str)
else:
    df_sel = pd.DataFrame(columns=[id_col, lat_col, lon_col])

# ensure to have numeric coords for selected samples 
for col in (lat_col, lon_col):
    if col in df_sel.columns:
        df_sel[col] = pd.to_numeric(df_sel[col], errors="coerce")
df_sel = df_sel.dropna(subset=[lat_col, lon_col]).copy()

# selected id set 
sel_ids = set(df_sel[id_col].unique()) if id_col in df_sel.columns else set()

# generate map
if not df_amp_coords.empty:
    center_lat = float(df_amp_coords[lat_col].mean())
    center_lon = float(df_amp_coords[lon_col].mean())
else:
    center_lat, center_lon = 20.0, 0.0

m = folium.Map(location=[center_lat, center_lon], zoom_start=2, tiles="CartoDB positron")

# layer all amplicon samples (no krona links)
all_layer = folium.FeatureGroup(name="all amplicon samples (no krona)", show=True)
cluster_all = MarkerCluster(disableClusteringAtZoom=6).add_to(all_layer)

for _, row in df_amp_coords.iterrows():
    sid = row.get(id_col, "")
    lat, lon = float(row[lat_col]), float(row[lon_col]])
    body = (row.get("body_site_label") or "other").strip().lower()
    country = row.get(country_col, row.get("country", "unknown"))

    popup_html = (
        f"<b>{sid}</b><br>"
        f"country: {country}<br>"
        f"body site: {body}"
    )

    folium.CircleMarker(
        location=[lat, lon],
        radius=4,
        color="#666666",
        weight=1,
        fill=True,
        fill_opacity=0.7,
        fill_color="#b0b0b0",
        tooltip=f"{sid}",
        popup=folium.Popup(popup_html, max_width=340),
    ).add_to(cluster_all)

all_layer.add_to(m)

# layer selected samples (with krona popups)
sel_layer = folium.FeatureGroup(name="selected (krona popups)", show=True)
cluster_sel = MarkerCluster(disableClusteringAtZoom=6).add_to(sel_layer)

for _, row in df_sel.iterrows():
    sid = row[id_col]
    lat, lon = float(row[lat_col]), float(row[lon_col]])
    body = (row.get("body_site_label") or "other").strip().lower()
    country = row.get(country_col, row.get("country", "unknown"))
    color = pick_color(body)

    krona_file = krona_dir / f"{sid}.krona.html"
    try:
        rel = krona_file.relative_to(out_html.parent)
        rel_str = rel.as_posix()
    except Exception:
        rel_str = f"krona_html/{sid}.krona.html"

    # create anchor tag
    if krona_file.exists():
        link = f"<a href='{rel_str}' target='_blank'>open krona plot</a>"
    else:
        link = f"<i>(krona not found: {rel_str})</i>"

    popup_html = (
        f"<b>{sid}</b><br>"
        f"country: {country}<br>"
        f"body site: {body}<br>"
        f"{link}"
    )

    folium.CircleMarker(
        location=[lat, lon],
        radius=8,
        color="#000000",
        weight=2,
        fill=True,
        fill_opacity=1.0,
        fill_color=color,
        tooltip=f"{sid} (selected)",
        popup=folium.Popup(popup_html, max_width=340),
    ).add_to(cluster_sel)

sel_layer.add_to(m)

# legend
legend_html = """
<div style="
 position: fixed; bottom: 20px; left: 20px; z-index: 9999;
 background: white; padding: 10px 12px; border: 1px solid #bbb; border-radius: 8px;
 box-shadow: 0 1px 4px rgba(0,0,0,0.3); font-size: 13px;">
<b>body site</b><br>
<span style='display:inline-block;width:10px;height:10px;background:#e41a1c;border:1px solid #333;margin-right:6px;'></span> hand<br>
<span style='display:inline-block;width:10px;height:10px;background:#ff7f00;border:1px solid #333;margin-right:6px;'></span> palm<br>
<span style='display:inline-block;width:10px;height:10px;background:#377eb8;border:1px solid #333;margin-right:6px;'></span> foot<br>
<span style='display:inline-block;width:10px;height:10px;background:#984ea3;border:1px solid #333;margin-right:6px;'></span> face<br>
<span style='display:inline-block;width:10px;height:10px;background:#4daf4a;border:1px solid #333;margin-right:6px;'></span> armpit<br>
<span style='display:inline-block;width:10px;height:10px;background:#a65628;border:1px solid #333;margin-right:6px;'></span> scalp<br>
<span style='display:inline-block;width:10px;height:10px;background:#f781bf;border:1px solid #333;margin-right:6px;'></span> forearm<br>
<span style='display:inline-block;width:10px;height:10px;background:#7f7f7f;border:1px solid #333;margin-right:6px;'></span> skin_other<br>
<span style='display:inline-block;width:10px;height:10px;background:#cccccc;border:1px solid #333;margin-right:6px;'></span> other<br>
</div>"""
m.get_root().html.add_child(folium.Element(legend_html))

# allow layer toggling
folium.LayerControl(collapsed=False).add_to(m)

# save map
out_html.parent.mkdir(parents=True, exist_ok=True)
m.save(str(out_html))
print("[ok] interactive map:", out_html)
print("tip: serve locally to ensure krona popups open:")
print(" cd results && python3 -m http.server 8000")
print(f" open http://localhost:8000/{out_html.name}")