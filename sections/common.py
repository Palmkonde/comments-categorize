"""Shared helpers for the dashboard sections."""
from dataclasses import dataclass

import pandas as pd
import streamlit as st

import jev

ACTIONS = ["Auto-keep", "Auto-flag", "Human review"]


@dataclass
class Settings:
    price: float
    review: tuple  # (low, high): flag strictly between them goes to a person


def route(d, s):
    """Add the action column. The flag drives the action; a flag inside the review band goes to a person."""
    low, high = s.review
    action = pd.Series("Human review", index=d.index)
    action.loc[d["flag"] <= low] = "Auto-keep"
    action.loc[d["flag"] >= high] = "Auto-flag"
    return d.assign(action=action)


def mermaid(src, height):
    st.iframe(
        f"""<pre class="mermaid" style="background:white">{src}</pre>
        <script type="module">
          import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.esm.min.mjs";
          mermaid.initialize({{ startOnLoad: true }});
        </script>""",
        height=height,
    )


def flash(state_key):
    """Show a success message saved before the last st.rerun()."""
    if state_key in st.session_state:
        st.success(st.session_state.pop(state_key))


def run_with_progress(start_text, job, state_key, done_message):
    """Run job(on_progress) with a progress bar, then save a success message and rerun."""
    bar = st.progress(0.0, start_text)
    try:
        result = job(lambda done, total: bar.progress(done / total, f"JEV: {done}/{total} comments"))
    except jev.TypeSafeAuthenticationError:
        st.error("JEV rejected the API key (401). Check TYPESAFE_API_KEY in .env.")
    except Exception as e:
        st.error(f"Failed: {e}")
    else:
        st.session_state[state_key] = done_message(result)
        st.rerun()
