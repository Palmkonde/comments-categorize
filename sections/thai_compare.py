"""Section 10: same comments, English questions vs Thai questions."""
import pandas as pd
import streamlit as st

import jev
from sections.common import flash, route, run_with_progress

DETAIL_FIELDS = ("flag", "category", "category_confidence", "severity", "severity_confidence", "input_tokens")


def render(records, key, s):
    st.header("10. Thai comments: English questions vs Thai questions")
    st.caption(
        "Asks the same saved comments again with the three questions translated to Thai, using the same JEV version, "
        "then compares. Use a Thai video. Matching answers show consistency, not which language is right."
    )
    st.markdown("**The questions sent to JEV** (choice keys stay in English so answers can be compared)")
    st.dataframe(question_table(), hide_index=True)
    if not records:
        st.info("Fetch a Thai video first.")
        return
    titles = [r["title"] for r in records]
    rec = records[titles.index(st.selectbox("Video", titles))]
    flash("thai_saved")
    st.caption(f"This makes {len(rec['comments'])} more JEV calls (model pinned to {rec['model']}).")
    if st.button("Run Thai questions on this video", disabled=not key):
        run_with_progress(
            "Asking Thai questions...",
            lambda on_progress: jev.compare_thai(rec, key, on_progress),
            "thai_saved",
            lambda th: f"Saved Thai-question results for {len(th['comments'])} comments.",
        )

    th = jev.load_thai(rec["video_id"])
    if th:
        compare(rec, th, s)


def question_table():
    """English and Thai wording of every question, side by side."""
    rows = []
    for name, en in jev.QUESTIONS.items():
        th = jev.QUESTIONS_TH[name]
        rows.append({"Question": f"{name} ({en['type']})", "Part": "instructions", "English": en["instructions"], "Thai": th["instructions"]})
        crit = en["criteria"]
        labels = crit.keys() if isinstance(crit, dict) else range(len(crit))
        for k in labels:
            part = jev.SEVERITY[k] if isinstance(k, int) else k
            rows.append({"Question": "", "Part": part, "English": crit[k], "Thai": th["criteria"][k]})
    return pd.DataFrame(rows)


def summary(d, s):
    return {
        "Comments answered": len(d),
        "Avg flag probability": round(d["flag"].mean(), 3),
        "Avg category confidence": round(d["category_confidence"].mean(), 3),
        "Avg severity confidence": round(d["severity_confidence"].mean(), 3),
        "Sent to human review": f"{(d['action'] == 'Human review').mean():.0%}",
        "Avg input tokens / comment": round(d["input_tokens"].mean(), 1),
        "Total cost (USD)": f"${jev.cost(int(d['input_tokens'].sum()), s.price):.6f}",
    }


def compare(rec, th, s):
    en_df = route(pd.DataFrame(jev.flatten(rec)).dropna(subset=["flag"]), s)
    th_df = route(pd.DataFrame(jev.flatten(th)).dropna(subset=["flag"]), s)
    both = en_df.merge(th_df, on=["id", "text"], suffixes=("_en", "_th"))
    if both.empty:
        st.warning("No comments answered in both runs.")
        return

    st.dataframe(pd.DataFrame({
        "English questions": {"JEV model": rec["model"], **summary(en_df, s)},
        "Thai questions": {"JEV model": th["model"], **summary(th_df, s)},
    }).astype(str))

    m = st.columns(3)
    m[0].metric("Same category", f"{(both['category_en'] == both['category_th']).mean():.0%}")
    m[1].metric("Same severity", f"{(both['severity_en'] == both['severity_th']).mean():.0%}")
    m[2].metric("Same action", f"{(both['action_en'] == both['action_th']).mean():.0%}")

    cols = ["text"] + [f"{f}_{lang}" for f in DETAIL_FIELDS for lang in ("en", "th")]
    st.dataframe(both[cols], hide_index=True)
    st.download_button("Download comparison CSV", both[cols].to_csv(index=False).encode("utf-8-sig"), "jev_thai_comparison.csv", "text/csv")
