"""Section 11: are Thai questions more confident when English questions are unsure? Reworded English is the control."""
import numpy as np
import pandas as pd
import streamlit as st

import jev
from sections.common import flash, run_with_progress

UNSURE = 0.6  # English category confidence below this = unsure. Fixed before running.
MIN_UNSURE = 30
NAMES = {"en": "English", "th": "Thai", "en2": "Reworded English"}
COMPARISONS = [("th", "en"), ("en2", "en"), ("th", "en2")]
MEASURES = {"category_confidence": "Category confidence (main)", "severity_confidence": "Severity confidence", "flag_sureness": "Flag sureness |2·flag − 1|"}


def paired(records):
    """One row per comment, with each question set's answers side by side (suffix _en, _th, _en2)."""
    df = None
    for name in jev.QUESTION_SETS:
        rows = [row for r in records for row in jev.flatten({"title": r["title"], "comments": r["comments" if name == "en" else name]})]
        d = pd.DataFrame(rows).dropna(subset=["flag"]).assign(flag_sureness=lambda x: (2 * x["flag"] - 1).abs())
        d = d[["id", "video", "text", "category", "severity", "flag", *MEASURES]].add_suffix(f"_{name}").rename(
            columns={f"id_{name}": "id", f"video_{name}": "video", f"text_{name}": "text"})
        df = d if df is None else df.merge(d, on=["id", "video", "text"])
    return df


def bootstrap(d, n=5000, seed=0):
    """Mean of d with a 95% bootstrap interval."""
    d = np.asarray(d, dtype=float)
    means = np.random.default_rng(seed).choice(d, (n, len(d))).mean(axis=1)
    return d.mean(), np.percentile(means, 2.5), np.percentile(means, 97.5)


def results(df):
    """Every comparison x measure on the unsure group."""
    unsure = df[df["category_confidence_en"] < UNSURE]
    rows = []
    for a, b in COMPARISONS:
        for m, label in MEASURES.items():
            mean, lo, hi = bootstrap(unsure[f"{m}_{a}"] - unsure[f"{m}_{b}"]) if len(unsure) else (np.nan,) * 3
            rows.append({"Comparison": f"{NAMES[a]} − {NAMES[b]}", "Measure": label, "Mean": mean, "95% low": lo, "95% high": hi})
    return unsure, pd.DataFrame(rows)


def verdict(table, n_unsure):
    """The rule fixed before running: Thai − English and Thai − Reworded English must both be above 0 (category confidence)."""
    main = table[table["Measure"] == MEASURES["category_confidence"]].set_index("Comparison")
    th_en, th_en2 = main.loc["Thai − English", "95% low"], main.loc["Thai − Reworded English", "95% low"]
    if n_unsure < MIN_UNSURE:
        return "unclear", f"Unclear: only {n_unsure} unsure comments. Add videos (aim for about 100)."
    if th_en > 0 and th_en2 > 0:
        return "supported", "Supported: on unsure comments, Thai questions are more confident than English and than reworded English."
    if th_en > 0:
        return "rewording", "Not supported: Thai is higher than English, but not higher than reworded English, so rewording explains it."
    return "not supported", "Not supported: on unsure comments, Thai questions are not more confident than English."


def render(key):
    st.header("11. Question wording experiment")
    st.caption(
        f"Hypothesis: when English questions are unsure (category confidence < {UNSURE}), Thai questions are more confident. "
        "Control: the same English questions reworded. Rule, fixed before running: the 95% interval of Thai − English "
        "and of Thai − Reworded English (category confidence, unsure comments) must both be above 0."
    )
    with st.expander("The reworded English questions"):
        st.json(jev.QUESTIONS_EN2)

    flash("exp_saved")
    urls = [u.strip() for u in st.text_area("Video links (one per line, use new videos)").splitlines() if u.strip()]
    n = st.number_input("Comments per video", 1, 200, 50, key="exp_n")
    st.caption(f"This makes {len(urls) * n * 3} JEV calls at most (3 question sets).")
    if st.button("Run experiment", disabled=not key or not urls):
        run_with_progress(
            "Fetching comments...",
            lambda on_progress: jev.run_experiment(urls, n, key, on_progress),
            "exp_saved",
            lambda saved: f"Saved {len(saved)} videos to data/experiments/.",
        )

    records = jev.load_experiments()
    if not records:
        st.info("No experiment results yet.")
        return
    df = paired(records)
    unsure, table = results(df)
    status, text = verdict(table, len(unsure))
    c = st.columns(4)
    c[0].metric("Videos", len(records))
    c[1].metric("Comments (answered in all 3)", len(df))
    c[2].metric("Unsure comments", len(unsure))
    c[3].metric("JEV model", records[0]["model"])
    (st.success if status == "supported" else st.warning)(text)
    st.dataframe(table.round(3), hide_index=True)
    st.caption("Rows are paired differences on the unsure comments. Only category confidence decides; the others are context.")
    cols = ["video", "text"] + [f"{m}_{s}" for m in ("category", "category_confidence") for s in jev.QUESTION_SETS]
    st.dataframe(unsure[cols].sort_values("category_confidence_th", ascending=False), hide_index=True)
    st.download_button("Download paired CSV", df.to_csv(index=False).encode("utf-8-sig"), "jev_wording_experiment.csv", "text/csv")


if __name__ == "__main__":
    # Self-check with made-up numbers (no API key needed).
    def fake(conf):
        a = {"flag": {"noul": 0.5}, "category": {"choice": "clean", "confidence": conf},
             "severity": {"score": 0.0, "probabilities": {"None": 1.0}, "confidence": 0.5}}
        return {"answers": a, "usage": {"input_tokens": 1}}

    def record(en, th, en2):
        ids = range(len(en))
        rows = lambda confs: [{"id": i, "text": f"t{i}", "response": fake(c)} for i, c in zip(ids, confs)]
        return {"title": "v", "comments": rows(en), "th": rows(th), "en2": rows(en2)}

    n = 40
    up = record([0.4] * n, [0.5 + 0.01 * (i % 3) for i in range(n)], [0.4 + 0.01 * (i % 3) for i in range(n)])
    unsure, table = results(paired([up]))
    assert len(unsure) == n and verdict(table, n)[0] == "supported"
    same = record([0.4] * n, [0.5 + 0.01 * (i % 3) for i in range(n)], [0.5 + 0.01 * (i % 3) for i in range(n)])
    assert verdict(results(paired([same]))[1], n)[0] == "rewording"
    down = record([0.4] * n, [0.3 + 0.01 * (i % 3) for i in range(n)], [0.4] * n)
    assert verdict(results(paired([down]))[1], n)[0] == "not supported"
    assert verdict(table, 5)[0] == "unclear"
    sure = record([0.9] * n, [0.5] * n, [0.5] * n)
    assert len(results(paired([sure]))[0]) == 0
    print("ok")
