# pages/load_fetch_metadata.py

import streamlit as st
import pandas as pd
from pathlib import Path

from utils.io_utils import read_metadata_tsv, fetch_ena_metadata

st.header("1) Load or Fetch Metadata")

st.markdown("""
- **Upload** a prepared `metadata.tsv` **or**  
- **Fetch** metadata from ENA using `NCBI.skin.metagenome.sampleID.txt` (one accession per line), **or**  
- **Point** to a local path (or example file) in the sidebar.
""")

# path-based loading 
st.sidebar.header("Paths")
default_meta = st.sidebar.text_input(
    "Path to metadata.tsv",
    value="raw_data/metadata.tsv"  
)
use_example = st.sidebar.checkbox("Use example metadata", value=False)

if use_example:
    default_meta = "examples/metadata.example.tsv"

# Try to load if the path exists
if Path(default_meta).exists():
    df_from_path = read_metadata_tsv(default_meta)
    st.session_state["metadata"] = df_from_path
    st.success(f"Loaded {default_meta} with shape {df_from_path.shape}")
else:
    # Only inform if user typed something non-empty
    if default_meta.strip():
        st.info("Upload a metadata TSV, fetch from ENA, or enter a valid path in the sidebar.")

# Upload file / ENA fetch 
if "metadata" not in st.session_state:
    st.session_state["metadata"] = None

tab1, tab2 = st.tabs(["Upload metadata.tsv", "Fetch from ENA"])

with tab1:
    up = st.file_uploader("Upload metadata.tsv", type=["tsv"])
    if up:
        df = read_metadata_tsv(up)
        st.session_state["metadata"] = df
        st.success(f"Loaded metadata with shape {df.shape}")
        st.dataframe(df.head(50))

with tab2:
    ids_up = st.file_uploader("Upload NCBI.skin.metagenome.sampleID.txt", type=["txt"])
    if ids_up and st.button("Fetch from ENA"):
        sample_ids = [line.strip() for line in ids_up.getvalue().decode().splitlines() if line.strip()]
        if len(sample_ids) == 0:
            st.warning("No IDs found.")
        else:
            with st.spinner("Fetching metadata from ENA..."):
                df = fetch_ena_metadata(sample_ids)
            if df.empty:
                st.error("No metadata returned. Check IDs.")
            else:
                st.session_state["metadata"] = df
                st.success(f"Fetched metadata with shape {df.shape}")
                st.dataframe(df.head(50))

# Download helper for convenience
if st.session_state["metadata"] is not None:
    st.download_button(
        "Download current metadata.tsv",
        data=st.session_state["metadata"].to_csv(sep="\t", index=False),
        file_name="metadata.tsv",
        mime="text/tab-separated-values",
    )