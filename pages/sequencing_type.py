import streamlit as st
from utils.plots import barplot_counts

st.header("3) Sequencing Types")

df = st.session_state.get("metadata", None)
if df is None:
    st.info("Load or fetch metadata first.")
    st.stop()

st.markdown("Pick column that stores sequencing/library strategy (16S rRNA amplicon vs shotgun).")
col = st.selectbox("Sequencing type column", options=list(df.columns))

fig = barplot_counts(df, col, title="Sequencing Types")
st.pyplot(fig)