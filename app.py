import streamlit as st

st.set_page_config(
    page_title="SkinMicroMap",
    page_icon="🗺️",
    layout="wide",
)

st.title("SkinMicroMap 🗺️🧬")
st.write("""
A Streamlit interface for exploring skin microbiome metagenomic metadata, 
mapping sample locations, visualizing sequencing types, and linking to Krona plots
computed externally (Kraken2/Bracken/Krona).
""")

st.markdown("""
**Workflow overview**

1. Load or fetch metadata  
2. Compute geographic distribution  
3. Explore sequencing type distribution  
4. Browse interactive map & open Krona plots  
5. Select target samples for downstream analysis
""")