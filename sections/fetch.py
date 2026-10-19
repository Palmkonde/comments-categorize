"""Section 2: fetch a YouTube video's comments and analyze them."""
import streamlit as st

import jev
from sections.common import flash, run_with_progress


def render(key):
    st.header("2. Fetch & analyze a video")
    url = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")
    n = st.number_input("Number of top comments (max 200)", min_value=1, max_value=200, value=50, step=10)
    flash("saved")
    if st.button("Fetch & analyze", type="primary", disabled=not key or not url):
        run_with_progress(
            "Fetching comments with yt-dlp...",
            lambda on_progress: jev.analyze_video(url, n, key, on_progress),
            "saved",
            lambda rec: f"Saved {len(rec['comments'])} comments from '{rec['title']}' "
            f"({sum('error' in c for c in rec['comments'])} errors).",
        )
