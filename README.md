# JEV comment moderation demo

A Streamlit app that moderates YouTube comments with [JEV](https://typesafe.ai/blog/introducing-system-one-models-and-jev), TypeSafe's System One model. Each comment gets three questions in one API call:

- **flag** (`noul`): should a moderator review it? (probability 0 to 1)
- **category** (`choice`): clean, spam, self_promotion, harassment, hate_speech, misinformation, or off_topic
- **severity** (`score`): None, Mild, Moderate, or Severe

The flag decides the action: **Auto-keep**, **Auto-flag**, or **Human review** when JEV is unsure.

## Run

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env   # then set TYPESAFE_API_KEY
uv run streamlit run app.py
```

Without a key the app still opens, but fetching and live calls are off.

## What's in the app

1. How it works: flow diagram and a real request and response
2. Fetch: paste a YouTube link and analyze its top comments
3. to 8. Dashboard: summary, cost, charts per answer type, confidence, and a table of every comment
9. Try your own comment
10. English questions vs Thai questions on the same comments
11. Question wording experiment: English, Thai, and reworded English on new videos

## Layout

```
app.py          # page setup, sidebar, sections in order
jev.py          # questions, SDK call, yt-dlp fetch, save/load, cost
sections/       # one module per app section
data/           # saved results (git-ignored)
REPORT.md       # full write-up: design decisions, results, experiments
```

Run `uv run python jev.py` and `uv run python -m sections.experiment` for the self-checks (no API key needed).

## Notes

- Results, design decisions, and limitations are in [REPORT.md](REPORT.md).
- `data/` and `.env` are not committed. Scraped comments and the API key stay local.
- Comments are downloaded with `yt-dlp`, which is a grey area under YouTube's Terms of Service. Use it only for small research samples.
