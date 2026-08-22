# job-matcher

A near-zero-cost job search agent designed to run as a scheduled GitHub Action.

It fetches listings from several job boards, cheaply filters out the noise,
ranks the survivors against your CV using **local embeddings**
(`sentence-transformers`, runs on the GitHub-hosted runner, no API calls),
and only sends the top handful of candidates to an **Ollama Cloud** model for
a final narrative fit/gap analysis. Results are posted as a GitHub Issue (or
a webhook of your choice) and the seen-job state is committed back to the repo
so nothing is ever re-processed.

## Why this is cheap

| Stage | Cost |
|---|---|
| Fetching (RSS/JSON feeds) | Free — plain HTTP |
| Keyword/regex filter | Free — runs in-process |
| Embedding similarity ranking | Free — local model, CPU-only, runs on the free GitHub runner |
| LLM fit analysis | Paid, but capped — only the top N (default 12) listings per run go to the LLM |
| Compute | Free — GitHub Actions free tier (public repos: unlimited; private: 2,000 min/month) |
| Storage | Free — a JSON/SQLite file committed to the repo |

A daily cron run over ~5 boards, filtered down to ~12 LLM calls a day, costs
pennies a month on Ollama Cloud's free-tier / pay-as-you-go models, and $0 in
compute.

## Project layout

```
job_matcher/
  config.py          # loads config.yaml + secrets from env
  cv_loader.py        # extracts plain text from your CV (pdf/docx/txt/md)
  state.py             # SQLite-backed "seen job" dedup store
  embeddings.py        # local sentence-transformers wrapper
  matcher.py            # keyword filter -> embedding rank -> top-N selection
  llm.py                 # Ollama Cloud client for the final fit analysis
  notify.py               # writes a Markdown report + optionally opens a GitHub Issue
  main.py                  # orchestrates the whole run
  fetchers/
    base.py                 # Fetcher interface + shared HTTP helpers
    remotive.py               # Remotive public JSON API
    weworkremotely.py          # We Work Remotely RSS feeds
    hn_hiring.py                 # Hacker News "Who is Hiring" (Algolia API)
    greenhouse.py                  # Any company's public Greenhouse board API
config.yaml           # boards, keywords, thresholds — edit this
.github/workflows/job-search.yml   # the scheduled Action
requirements.txt
data/seen_jobs.sqlite3   # created on first run, committed by the Action
```

## Setup

1. **Fork/clone this repo.**

2. **Add your CV** at `cv/resume.pdf` (or `.docx`/`.txt`/`.md` — see `cv_loader.py`).
   Update the path in `config.yaml` if you name it differently.

3. **Edit `config.yaml`**: job boards to query, search keywords, must-have /
   exclude terms, minimum embedding-similarity threshold, and how many
   listings get sent to the LLM per run.

4. **Add repo secrets** (Settings → Secrets and variables → Actions):
   - `OLLAMA_API_KEY` — from https://ollama.com/settings/keys
   - `GH_ISSUE_TOKEN` — optional, only needed if you want the Action to open
     an Issue with results (the default `GITHUB_TOKEN` already has this
     permission for same-repo issues, so this is usually not required —
     see the workflow comments).

5. Commit. The workflow runs on the schedule defined in
   `.github/workflows/job-search.yml` (default: daily at 07:00 UTC), and can
   also be triggered manually from the Actions tab (`workflow_dispatch`).

## Running locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OLLAMA_API_KEY=your_key_here
python -m job_matcher.main --config config.yaml
```

Results are written to `report.md` and printed to stdout. Use `--no-llm` to
do a dry run with just the free embedding ranking (useful while tuning
`config.yaml`).

## Extending

Add a new board by subclassing `Fetcher` in `job_matcher/fetchers/base.py`
(one method: `fetch() -> list[JobPosting]`) and registering it in
`job_matcher/main.py`'s `FETCHERS` dict. Greenhouse-based company boards
(hundreds of companies use Greenhouse) are already supported generically —
just add the company's board token to `config.yaml`.

## Cost controls baked in

- **Dedup persists across runs** (`data/seen_jobs.sqlite3`, committed by CI)
  — a listing is only ever embedded and LLM-matched once, ever.
- **Two-stage filter**: cheap keyword/regex pass first, so only plausible
  matches reach the embedding model.
- **`llm.max_candidates`** in config hard-caps how many listings can reach
  the paid LLM stage per run, regardless of how many pass the embedding
  threshold.
- **Daily, not hourly, cron** by default — job boards don't update fast
  enough to justify more, and this is the single biggest lever on total
  Action minutes and (indirectly) API usage.
- **CPU-only local embedding model** (`all-MiniLM-L6-v2`, ~80MB) — fast
  enough on a GitHub-hosted runner that it never approaches the free-tier
  time budget.
