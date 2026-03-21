import streamlit as st
import pandas as pd
import geopandas as gpd
from utils.geo_utils import load_world_polygons, add_geometry_from_latlon, reverse_geocode_country, count_by_country
from utils.plots import barplot_counts

st.header("2) Geographic Distribution")

df = st.session_state.get("metadata", None)
if df is None:
    st.info("Load or fetch metadata first.")
    st.stop()

st.markdown("#### Select latitude/longitude columns")
cols = list(df.columns)
lat_col = st.selectbox("Latitude column", options=cols, index=cols.index("latitude") if "latitude" in cols else 0)
lon_col = st.selectbox("Longitude column", options=cols, index=cols.index("longitude") if "longitude" in cols else 0)

world_source = st.radio("Country polygons source", ["GeoPandas built‑in ", "Local Natural Earth shapefile"])
world_path = None
if world_source == "Local Natural Earth shapefile":
    shp = st.file_uploader("Upload admin_0 countries shapefile (.zip)", type=["zip"])
    if shp:
        st.warning("Place the shapefile on disk if large; for now use the built‑in dataset.")
        world_source = "GeoPandas built‑in "

with st.spinner("Assigning countries by spatial join..."):
    world = load_world_polygons(None)  
    gdf = add_geometry_from_latlon(df.dropna(subset=[lat_col, lon_col]), lat_col, lon_col)
    joined = reverse_geocode_country(gdf, world)

st.success("Countries assigned.")
st.dataframe(joined[[lat_col, lon_col, "country"]].head(50))

counts = count_by_country(joined)
fig = barplot_counts(counts.rename(columns={'n': 'Count'}), "country", "Samples per Country")
st.pyplot(fig)

st.download_button(
    "Download metadata_with_country.tsv",
    data=joined.drop(columns="geometry").to_csv(sep="\t", index=False),
    file_name="metadata_with_country.tsv",
    mime="text/tab-separated-values",
)