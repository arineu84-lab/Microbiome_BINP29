import streamlit as st
import pandas as pd

st.header("5) Select Target Samples")

df = st.session_state.get("metadata", None)
if df is None:
    st.info("Load or fetch metadata first.")
    st.stop()

st.markdown("Filter by geography and body site, then pick samples for downstream analysis.")

country_col = st.selectbox("Country column", options=list(df.columns))
body_col    = st.selectbox("Body site column", options=list(df.columns))

countries = st.multiselect("Countries", options=sorted(df[country_col].dropna().unique().tolist()))
body_sites = st.multiselect("Body sites", options=sorted(df[body_col].dropna().unique().tolist()))

filtered = df.copy()
if countries:
    filtered = filtered[filtered[country_col].isin(countries)]
if body_sites:
    filtered = filtered[filtered[body_col].isin(body_sites)]

st.write(f"Filtered rows: {len(filtered)}")
st.dataframe(filtered.head(100))

id_col = st.selectbox("Sample ID column", options=list(df.columns))
n = st.number_input("How many samples to select", value=3, min_value=1, step=1)
selection = filtered.head(n)

st.subheader("Selected samples")
st.dataframe(selection[[id_col, country_col, body_col]].head(n))

st.download_button(
    "Download selected_samples.txt",
    data="\n".join(map(str, selection[id_col].tolist())),
    file_name="selected_samples.txt",
    mime="text/plain"
)