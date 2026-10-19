"""Sections 3-8: summary, one panel per JEV type, confidence, and the comment table."""
import plotly.express as px
import streamlit as st

import jev
from sections.common import ACTIONS, route

TABLE_COLUMNS = [
    "video", "author", "text", "action", "flagged", "flag", "flag_confidence", "category", "category_confidence",
    "severity", "severity_score", "severity_confidence", "input_tokens",
]


def render(df, s):
    ok = route(df[df["flag"].notna()], s) if not df.empty else df
    if ok.empty:
        st.info("No results yet. Add your key to .env, then fetch a video above.")
        return
    summary(ok, df, s)
    noul_panel(ok, s)
    choice_panel(ok)
    score_panel(ok)
    confidence(ok)
    table(ok)


def summary(ok, df, s):
    st.header("3. Summary")
    tokens = int(ok["input_tokens"].sum())
    total = jev.cost(tokens, s.price)
    per = total / len(ok)
    k = st.columns(6)
    k[0].metric("Comments analyzed", len(ok))
    k[1].metric("Flagged", f"{ok['flagged'].mean():.0%}")
    k[2].metric("Auto-handled", f"{(ok['action'] != 'Human review').mean():.0%}", help="Flag confidence ≥ cut-off, so no person needed")
    k[3].metric("Input tokens", f"{tokens:,}")
    k[4].metric("Total cost", f"${total:.6f}")
    k[5].metric("Avg cost / comment", f"${per:.8f}")
    st.caption(
        f"Projected: ${per * 1_000:.4f} per 1,000 comments · ${per * 1_000_000:,.2f} per 1,000,000 comments. "
        f"Cost = input tokens × ${s.price}/1M. Price is unofficial (see sidebar)."
    )
    failed = df[df["error"].notna()]
    if not failed.empty:
        st.warning(f"{len(failed)} comments failed and are not counted.")


def noul_panel(ok, s):
    st.header("4. noul: should a moderator review it?")
    fig = px.histogram(ok, x="flag", color="video", nbins=20, range_x=[0, 1], labels={"flag": "Flag probability"})
    fig.add_vline(x=s.threshold, line_dash="dash", annotation_text=f"threshold {s.threshold}")
    fig.add_vrect(x0=0.5 - s.cutoff / 2, x1=0.5 + s.cutoff / 2, fillcolor="gray", opacity=0.15, line_width=0,
                  annotation_text="unsure: human review", annotation_position="bottom left")
    st.plotly_chart(fig)
    st.caption("Near 1 = strong yes, near 0 = strong no, near 0.5 = unsure. Shaded band: flag confidence |2p − 1| below the cut-off.")


def choice_panel(ok):
    st.header("5. choice: what kind of comment is it?")
    fig = px.histogram(ok, x="category", color="video", category_orders={"category": list(jev.CATEGORIES)})
    st.plotly_chart(fig)
    st.caption(f"Average choice confidence: {ok['category_confidence'].mean():.2f}")


def score_panel(ok):
    st.header("6. score: how harmful is it?")
    fig = px.histogram(ok, x="severity", color="video", category_orders={"severity": jev.SEVERITY})
    st.plotly_chart(fig)
    st.caption(f"Average score confidence: {ok['severity_confidence'].mean():.2f}")


def confidence(ok):
    st.header("7. Confidence: when can we trust JEV?")
    st.caption(
        "Confidence (0-1) tells how sure JEV is: 1 = all probability on one answer, 0 = spread evenly. "
        "Rule: confident flag → act automatically; unsure flag → send to a person."
    )
    c1, c2 = st.columns(2)
    fig = px.histogram(ok, x="action", color="video", category_orders={"action": ACTIONS}, title="What happens to each comment")
    c1.plotly_chart(fig)
    fig = px.box(ok, x="category", y="category_confidence", points="all", range_y=[0, 1],
                 category_orders={"category": list(jev.CATEGORIES)}, title="choice confidence by category")
    c2.plotly_chart(fig)
    st.caption("Low boxes show categories JEV finds hard to tell apart. Those labels need a person to check them before you trust them.")


def table(ok):
    st.header("8. All comments")
    t = ok[TABLE_COLUMNS]
    st.dataframe(t, hide_index=True)
    st.download_button("Download CSV", t.to_csv(index=False).encode("utf-8-sig"), "jev_results.csv", "text/csv")
