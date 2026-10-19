"""Section 1: flow diagrams, SDK call, and raw request/response."""
import streamlit as st

import jev
from sections.common import mermaid

PIPELINE = """flowchart LR
    A["YouTube URL"] -->|yt-dlp| B["Top N comments"]
    B -->|"5 calls in parallel"| C["JEV API<br/>POST /v1/systemone"]
    C --> D["noul: flag 0-1"]
    C --> E["choice: category"]
    C --> F["score: severity"]
    D & E & F --> G[("data/video_id.json")]
    G --> H["Streamlit dashboard"]"""

QUESTION_TYPES = """flowchart LR
    S["state<br/>{video_title, comment}"] --> N & C & K
    N["noul: yes/no<br/>Should a moderator review it?"] --> NA["noul: 0.91<br/>probability of yes"]
    C["choice: pick one of 7<br/>What is the main category?"] --> CA["choice: spam<br/>+ probabilities, confidence"]
    K["score: ordered levels<br/>How harmful is it?"] --> KA["score: 1.2 = Mild<br/>+ probabilities, confidence"]"""

SDK_CALL = """from typesafe_sdk import TypeSafeClient

with TypeSafeClient() as client:  # reads TYPESAFE_API_KEY
    result = client.system_one(state, questions)
raw = result.raw_http_response.json()"""


def render(records):
    st.header("1. How it works")
    mermaid(PIPELINE, 320)
    st.markdown("**What each question type does** (one request, three questions, example answers)")
    mermaid(QUESTION_TYPES, 300)

    st.markdown("**Python SDK call** (`typesafe-sdk`): the raw request body and response it sends and receives are shown below.")
    st.code(SDK_CALL, language="python")

    example = next(((r, c) for r in records for c in r["comments"] if "response" in c), None)
    req_col, resp_col = st.columns(2)
    if example:
        r, c = example
        req_col.markdown(f"**Request** (one real comment from *{r['title']}*)")
        req_col.json(jev.build_request(c["text"], r["title"]), expanded=False)
        resp_col.markdown("**Response** (real JEV output)")
        resp_col.json(c["response"], expanded=False)
    else:
        req_col.markdown("**Request** (example)")
        req_col.json(jev.build_request("Help! Free iPhone giveaway, click my channel!!", "iPhone 18 review"), expanded=False)
        resp_col.info("No real response yet. Fetch a video to see JEV's actual output here.")
