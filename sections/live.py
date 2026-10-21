"""Section 9: ask JEV about one typed comment, live."""
import pandas as pd
import streamlit as st

import jev
from sections.common import route


def render(key, s):
    st.header("9. Try your own comment")
    text = st.text_area("Comment (Thai or English)")
    title = st.text_input("Video title (optional, helps with off_topic / misinformation)")
    if not st.button("Ask JEV", disabled=not key or not text):
        return
    try:
        resp = jev.ask_jev(jev.build_request(text, title), key)
    except Exception as e:
        st.error(str(e))
        return
    a = resp["answers"]
    t = resp.get("usage", {}).get("input_tokens", 0)
    p = a["flag"]["noul"]
    c = st.columns(5)
    c[0].metric("noul: flag", f"{p:.2f}")
    c[1].metric("choice: category", a["category"]["choice"], f"conf {a['category'].get('confidence', 0):.2f}", delta_color="off")
    c[2].metric("score: severity", jev.severity_label(a["severity"]), f"conf {a['severity'].get('confidence', 0):.2f}", delta_color="off")
    c[3].metric("Input tokens", t)
    c[4].metric("Cost", f"${jev.cost(t, s.price):.8f}")
    one = route(pd.DataFrame([{"flag": p}]), s)
    st.markdown(f"**Action:** {one['action'].iloc[0]}")
    st.json(resp, expanded=False)
