"""Sections 3-8: summary, one panel per JEV type, confidence, and the comment table."""
import plotly.express as px
import streamlit as st

import jev
from sections.common import ACTIONS, route

TABLE_COLUMNS = [
    "video", "author", "text", "action", "flag", "category", "category_confidence",
    "severity", "severity_score", "severity_confidence", "input_tokens",
]
COLUMN_HELP = {
    "flag": "JEV's answer (noul): the chance, from 0 to 1, that a moderator should look at this comment. Example: 0.81.",
    "action": "What happens to the comment: Auto-flag, Auto-keep, or Human review. See the list below the table.",
    "category": "choice answer: the most likely category.",
    "category_confidence": "How clearly the top category beats the others (0-1), from JEV.",
    "severity": "score answer: the most likely level (None, Mild, Moderate, Severe).",
    "severity_score": "Weighted average level from 0 (None) to 3 (Severe), so it can fall between levels and differ from severity.",
    "severity_confidence": "How sure JEV is about the level (0-1). Spread to a nearby level lowers it less than spread to a far level.",
    "input_tokens": "Tokens JEV read for this comment (questions + title + comment). Cost = input_tokens × price / 1,000,000.",
}
ACTION_HELP = """**action:**

- **Auto-flag:** flag is at or above the high end of the review band (default 0.75). JEV is sure the comment breaks the rules: spam, scams, harassment, hate, or harmful misinformation. Sure enough to skip the moderator and hide it automatically.
- **Auto-keep:** flag is at or below the low end of the review band (default 0.25). JEV is sure the comment is fine. It stays up, no person needed.
- **Human review:** flag is inside the review band (default between 0.25 and 0.75). JEV is unsure, so a moderator decides.

Only the flag decides the action, because it is the question "should a moderator review this?". noul has no confidence field: the flag probability itself shows how sure JEV is. Move the band with the sidebar slider."""


def render(df, s):
    ok = route(df[df["flag"].notna()], s) if not df.empty else df
    if ok.empty:
        st.info("No results yet. Add your key to .env, then fetch a video above.")
        return
    summary(ok, df, s)
    noul_panel(ok, s)
    choice_panel(ok)
    score_panel(ok)
    confidence(ok, s)
    table(ok)


def summary(ok, df, s):
    st.header("3. Summary")
    tokens = int(ok["input_tokens"].sum())
    total = jev.cost(tokens, s.price)
    per = total / len(ok)
    k = st.columns(6)
    k[0].metric("Comments analyzed", len(ok))
    k[1].metric("Sent to a person", f"{(ok['action'] == 'Human review').mean():.0%}", help="Flag inside the human review band")
    k[2].metric("Auto-handled", f"{(ok['action'] != 'Human review').mean():.0%}", help="Flag outside the human review band, so no person needed")
    k[3].metric("Input tokens", f"{tokens:,}")
    k[4].metric("Total cost", f"${total:.6f}")
    k[5].metric("Avg cost / comment", f"${per:.8f}")
    st.caption(
        f"Projected: ${per * 1_000:.4f} per 1,000 comments · ${per * 1_000_000:,.2f} per 1,000,000 comments. "
        f"Cost = input tokens × ${s.price}/1M. Price from TypeSafe's launch post (see sidebar)."
    )
    failed = df[df["error"].notna()]
    if not failed.empty:
        st.warning(f"{len(failed)} comments failed and are not counted.")


def noul_panel(ok, s):
    st.header("4. noul: should a moderator review it?")
    fig = px.histogram(ok, x="flag", color="video", nbins=20, range_x=[0, 1], labels={"flag": "Flag probability"})
    fig.add_vrect(x0=s.review[0], x1=s.review[1], fillcolor="gray", opacity=0.15, line_width=0,
                  annotation_text="unsure: human review", annotation_position="bottom left")
    st.plotly_chart(fig)
    st.caption("Near 1 = strong yes, near 0 = strong no, near 0.5 = unsure. Shaded band: the human review band from the sidebar.")


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


def confidence(ok, s):
    st.header("7. Confidence: when can we trust JEV?")
    st.caption(
        "Confidence (0-1) tells how sure JEV is: 1 = all probability on one answer, 0 = spread evenly. "
        "Rule: flag near 0 or 1 → act automatically; flag in the middle → send to a person."
    )
    c1, c2 = st.columns(2)
    fig = px.histogram(ok, x="action", color="video", category_orders={"action": ACTIONS}, title="What happens to each comment")
    c1.plotly_chart(fig)
    fig = px.box(ok, x="category", y="category_confidence", points="all", range_y=[0, 1],
                 category_orders={"category": list(jev.CATEGORIES)}, title="choice confidence by category")
    c2.plotly_chart(fig)
    st.caption("Low boxes show categories JEV finds hard to tell apart. Those labels need a person to check them before you trust them.")
    fig = px.histogram(ok, x="flag", color="action", nbins=20, range_x=[0, 1], category_orders={"action": ACTIONS},
                       labels={"flag": "Flag probability"}, title="Flag from 0 to 1, by action")
    for x in s.review:
        fig.add_vline(x=x, line_dash="dash", annotation_text=f"{x}")
    st.plotly_chart(fig)
    st.caption("Between the two lines goes to Human review. Outside them, JEV decides alone: Auto-keep on the left, Auto-flag on the right.")


def table(ok):
    st.header("8. All comments")
    t = ok[TABLE_COLUMNS]
    st.dataframe(t, hide_index=True)
    st.download_button("Download CSV", t.to_csv(index=False).encode("utf-8-sig"), "jev_results.csv", "text/csv")
    st.markdown("**What each column means**")
    st.table([{"Column": k, "Meaning": v} for k, v in COLUMN_HELP.items()])
    st.markdown(ACTION_HELP)
