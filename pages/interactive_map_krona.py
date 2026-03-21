# pages/interactive_map_krona.py

import streamlit as st
import pandas as pd
import folium
from pathlib import Path
from streamlit_folium import st_folium
from utils.krona_utils import krona_html_for_sample

st.header("4) Interactive Map & Krona")

df = st.session_state.get("metadata", None)
if df is None or df.empty:
    st.info("Load or fetch metadata first (Page 1).")
    st.stop()

# Sidebar controls 
st.sidebar.header("Krona settings")
krona_dir_input = st.sidebar.text_input("Krona directory (contains *_krona.html)", value="results/krona")
use_example_krona = st.sidebar.checkbox("Use example Krona", value=False)
if use_example_krona:
    krona_dir_input = "examples/results/krona"

krona_dir = Path(krona_dir_input)

# Column selection
lat_col = st.selectbox("Latitude column", options=list(df.columns))
lon_col = st.selectbox("Longitude column", options=list(df.columns))
id_col  = st.selectbox("Sample ID column (must match Krona filename prefix)", options=list(df.columns))

# Prepare map 
lat_mean = pd.to_numeric(df[lat_col], errors="coerce").mean()
lon_mean = pd.to_numeric(df[lon_col], errors="coerce").mean()
m = folium.Map(location=[lat_mean, lon_mean], zoom_start=2, tiles="CartoDB positron")

# Add markers
for _, r in df.dropna(subset=[lat_col, lon_col]).iterrows():
    sid = str(r[id_col])
    lat = float(r[lat_col]); lon = float(r[lon_col])

    popup_html = f"<b>Sample:</b> {sid}"
    folium.Marker([lat, lon], popup=popup_html, tooltip=sid).add_to(m)

# map (left) + Krona viewer (right) 
left, right = st.columns([2, 1], gap="large")

with left:
    st.write("### Map")
    map_state = st_folium(m, width=950, height=600)

# Detect last clicked marker by tooltip 
clicked_sample = None
if map_state and map_state.get("last_object_clicked_popup"):
    # If you used popups, you can parse sample from popup HTML; here we used tooltip,
    # so we read from 'last_object_clicked' if available.
    pass

# streamlit-folium 0.20+
if map_state and map_state.get("last_clicked"):
    last_lat = map_state["last_clicked"]["lat"]
    last_lon = map_state["last_clicked"]["lng"]
    m1 = (pd.to_numeric(df[lat_col], errors="coerce") == last_lat) & \
         (pd.to_numeric(df[lon_col], errors="coerce") == last_lon)
    if m1.any():
        clicked_sample = str(df.loc[m1, id_col].iloc[0])
    else:
        lat_diff = (pd.to_numeric(df[lat_col], errors="coerce") - last_lat).abs()
        lon_diff = (pd.to_numeric(df[lon_col], errors="coerce") - last_lon).abs()
        idx = (lat_diff + lon_diff).idxmin()
        if pd.notna(idx):
            clicked_sample = str(df.loc[idx, id_col])

with right:
    st.write("### Krona viewer")
    manual_id = st.selectbox("Pick a sample to open Krona (optional)", options=[None] + df[id_col].astype(str).tolist())
    sample_to_show = manual_id or clicked_sample

    if sample_to_show is None:
        st.info("Click a marker on the map or choose a sample above to preview its Krona plot.")
    else:
        krona_path = krona_html_for_sample(sample_to_show, krona_dir)
        if krona_path is None:
            st.warning(f"No Krona HTML found for **{sample_to_show}** in: `{krona_dir}`.\n\n"
                       f"Expected file name: `{sample_to_show}_krona.html`")
        else:
            st.success(f"Showing Krona for **{sample_to_show}**")
            with open(krona_path, "r", encoding="utf-8", errors="ignore") as f:
                html = f.read()
            st.components.v1.html(html, height=650, scrolling=True)

            # 'Open in new tab' link 
            st.markdown(
                f"[Open in new tab]({krona_path.resolve help="Opens the Krona plot in your browser"
            )
