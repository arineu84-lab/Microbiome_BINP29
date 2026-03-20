#!/usr/bin/env python3
from pathlib import Path
import pandas as pd
import folium
from folium.plugins import MarkerCluster

root = Path(".")
all_meta  = root / "raw_data" / "filtered_meta.tsv"
sel_meta  = root / "raw_data" / "selected_samples.tsv"
krona_dir = root / "results" / "krona_html"
out_html  = root / "results" / "map" / "interactive_map.html"

# load metadata
df_all = pd.read_csv(all_meta, sep="\t", dtype=str)
for col in ("lat", "lon"):
    df_all[col] = pd.to_numeric(df_all[col], errors="coerce")
df_all = df_all.dropna(subset=["lat", "lon"]).copy()

# 16s only
df_all["library_strategy"] = df_all["library_strategy"].astype(str).str.lower()
df16 = df_all[df_all["library_strategy"] == "amplicon"].copy()

# choose country column if available
country_col = "country_from_coords" if "country_from_coords" in df16.columns else "country"

# colors by body_site_label
COLOR = {
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
def pick_color(label: str) -> str:
    if not isinstance(label, str): return "#cccccc"
    return COLOR.get(label.strip().lower(), "#cccccc")

# base map
m = folium.Map(location=[20, 0], zoom_start=2, tiles="cartodb positron")
folium.TileLayer("openstreetmap").add_to(m)
folium.TileLayer("cartodb dark_matter").add_to(m)

# layer: all 16s points (clustered)
cluster = MarkerCluster(name="all 16s points (clustered)", show=True)
for _, row in df16.iterrows():
    lat, lon = float(row["lat"]), float(row["lon"])
    run  = row.get("run_accession", "na")
    body = (row.get("body_site_label") or "other").strip().lower()
    country = row.get(country_col, row.get("country", "unknown"))
    color = pick_color(body)
    html = f"<b>{run}</b><br>country: {country}<br>body site: {body}"
    folium.CircleMarker(
        location=[lat, lon],
        radius=5,
        color="#333333",
        weight=1,
        fill=True,
        fill_opacity=0.9,
        fill_color=color,
        tooltip=f"{run} ({country}, {body})",
        popup=folium.Popup(html, max_width=320),
    ).add_to(cluster)
m.add_child(cluster)

# layer: selected samples with krona links (3 from denmark)
# layer: selected samples with krona links (3 from denmark)
df_sel = pd.read_csv(sel_meta, sep="\t", dtype=str)
for col in ("lat", "lon"):
    df_sel[col] = pd.to_numeric(df_sel[col], errors="coerce")
df_sel = df_sel.dropna(subset=["lat", "lon"]).copy()

sel_layer = folium.FeatureGroup(name="selected (krona popups)", show=True)
for _, row in df_sel.iterrows():
    run = row["run_accession"]
    lat, lon = float(row["lat"]), float(row["lon"])
    body = (row.get("body_site_label") or "other").strip().lower()
    country = row.get(country_col, row.get("country", "unknown"))
    color = pick_color(body)

    krona_file = krona_dir / f"{run}.krona.html"
    try:
        # relative path from results/map/interactive_map.html to krona_html/<run>.krona.html
        rel = krona_file.relative_to(out_html.parent)
    except Exception:
        # conservative fallback if relative_to() cannot be computed
        rel = f"../krona_html/{run}.krona.html"

    # >>> paste this exact part <<<
    if krona_file.exists():
        link = f"<a href='{rel}' target='_blank'>open krona plot</a>"
    else:
        link = f"<i>(krona not found: {rel})</i>"
    # >>> end paste <<<

    popup_html = (
        f"<b>{run}</b><br>"
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
        tooltip=f"{run} (selected)",
        popup=folium.Popup(popup_html, max_width=340),
    ).add_to(sel_layer)

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

# save
out_html.parent.mkdir(parents=True, exist_ok=True)
m.save(str(out_html))
print("[ok] interactive map:", out_html)
print("tip: serve locally to ensure krona popups open:")
print("  cd results && python3 -m http.server 8000")
print("  open http://localhost:8000/map/interactive_map.html")