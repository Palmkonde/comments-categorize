"""Streamlit entry point: page setup, sidebar settings, then each dashboard section in order."""
import pandas as pd
import streamlit as st

import jev
from sections import dashboard, experiment, fetch, how_it_works, live, thai_compare
from sections.common import Settings

st.set_page_config(page_title="JEV Comment Moderation", layout="wide")
st.title("JEV Comment Moderation Demo")
st.caption("YouTube comments → JEV (TypeSafe System One model) → three answer types: noul, choice, score")

key = jev.api_key()
records = jev.load_all()
df = pd.DataFrame([row for r in records for row in jev.flatten(r)])

with st.sidebar:
    if key:
        st.success("TYPESAFE_API_KEY loaded")
    else:
        st.warning("No TYPESAFE_API_KEY in .env. Fetching and live test are off.")
    st.markdown(f"**Price:** ${jev.PRICE_PER_M} per 1M input tokens")
    st.caption("Price from TypeSafe's launch post (Oct 2026); it may change. Output tokens are free.")
    review = st.slider("Human review band (flag)", 0.0, 1.0, (0.25, 0.75), 0.05)
    st.caption("Flag at or below the low end: Auto-keep. At or above the high end: Auto-flag. In between: a person decides.")
    videos = sorted(df["video"].unique()) if not df.empty else []
    picked = st.multiselect("Videos", videos, default=videos)

s = Settings(price=jev.PRICE_PER_M, review=review)

how_it_works.render(records)                                     # 1
fetch.render(key)                                                # 2
dashboard.render(df[df["video"].isin(picked)] if not df.empty else df, s)  # 3-8
live.render(key, s)                                              # 9
thai_compare.render(records, key, s)                             # 10
experiment.render(key)                                           # 11
