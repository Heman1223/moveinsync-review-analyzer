# MoveInSync review analyzer

Why are MoveInSync's Play Store ratings where they are, and what should the team fix first?
This project collects public Google Play reviews, sorts the complaints into issues, ranks them by their
impact on the rating, turns each one into an action (owner, effort, what to check, how to know it worked),
and answers "How are our ratings?" every week automatically.

- **Full report (12 pages, PDF):** [deliverables/MoveInSync_Ratings_Report.pdf](deliverables/MoveInSync_Ratings_Report.pdf)
- **Recommendation memo:** [deliverables/recommendation_memo.md](deliverables/recommendation_memo.md)
- **How I got there and tools used:** [deliverables/method_note.md](deliverables/method_note.md)
- **This week's digest:** [docs/weekly_digest.md](docs/weekly_digest.md)
- **Live dashboard:** https://moveinsync-review-analyzer.streamlit.app

## Key findings (12 Oct 2026)

- MoveInSync is **#1 of 7 employee-transport apps** on Google Play (4.64★; the others average 3.05★).
- Its written reviews (3.8★) are level with Uber and Rapido. That ~1★ gap below the store rating is normal across apps.
- **Replies collapsed:** about 97% of 1–2★ reviews got a reply in 2023, 1% in 2026. Routematic replies to 100%.
- **Fix first (last 90 days):**
  1. app stability (23% of complaints, rising), led by a false "not installed from Play Store" block
  2. booking flow (16%)
  3. OTP delivery (10%)

## The dashboard

| Tab | What it shows |
|---|---|
| **Summary** | Weekly status (OK / WATCH / ALERT) with reasons, the answer in a few sentences, headline numbers, trends, and the top 3 issues to fix |
| **Issues** | Every issue ranked; the specific problems inside each, with an action card; the reviews behind it (filter by problem, stars, version, text) |
| **Reply to reviews** | Unanswered 1–2★ reviews with a suggested reply (template, or Gemini when enabled) to check and post in Play Console |
| **Fix tracker** | Issues being fixed, with complaints per 100 reviews before vs after and a verdict |
| **Benchmark** | MoveInSync against 10 comparable apps |
| **How it works** | Method, accuracy, rules, glossary |

## Run it yourself

Needs Python 3.11 or newer.

**Windows (PowerShell)**
```powershell
git clone https://github.com/Heman1223/moveinsync-review-analyzer.git
cd moveinsync-review-analyzer
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

**macOS / Linux**
```bash
git clone https://github.com/Heman1223/moveinsync-review-analyzer.git
cd moveinsync-review-analyzer
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The repo includes the collected data, so the dashboard opens straight away with no API key.

### Useful commands

| Command | What it does |
|---|---|
| `python refresh.py` | Fetch new reviews and rebuild the labels (`--no-llm` for keyword rules only) |
| `python -m scripts.benchmark` | Re-measure the 10 comparison apps (about 2 minutes, no AI) |
| `python -m scripts.digest` | Write the weekly digest to `docs/weekly_digest.md` |
| `python -m scripts.report` | Write the full numbers to `docs/analysis_snapshot.md` |
| `python -m scripts.validate` | Accuracy check on 100 held-out reviews |
| `python -m pytest` | Run the 68 automated tests (no network needed) |

### Optional: Gemini

Copy `.env.example` to `.env` and add `GEMINI_API_KEY=...`. Gemini is then used only for reviews the keyword
rules can't sort, keyword suggestions and reply drafts. Each review is sent once and the results are saved,
with at most 10 requests per run. Without a key, everything runs on keyword rules and templates. **Never put
a real key in `.env.example`; it is committed to git.**

## How it works (short version)

1. **Collect:** `src/collector.py` fetches reviews (newest first, incremental, retries, no personal data) and store rating snapshots.
2. **Sort:** `src/classifier.py` matches 13 issue categories with readable English and Hinglish keyword rules (`src/config.py`). `src/llm_assist.py` sends only what the rules miss to Gemini.
3. **Rank:** `src/analysis.py` computes rating impact per issue, trends, plausible ranges, release effects, reply health and the weekly status.
4. **Act:** `src/playbook.py` holds the specific problems inside each issue, with action, owner, effort, measure, and what to check first. `src/fix_tracker.py` tracks fixes; `src/replies.py` drafts replies (350-character limit, no promises, a human posts).
5. **Compare:** `src/benchmark.py` measures 10 other apps the same way.
6. **Repeat:** `.github/workflows/weekly.yml` runs every Monday 09:00 IST: tests, refresh, benchmark, digest, commit.

## Limits

Reviews describe experiences, not proven causes; confirm in MoveInSync's own data before building. Written
reviewers are more critical than people who only tap a star. The scraper is unofficial and may break if
Google changes its pages. Issue sorting is about 75% accurate on held-out reviews (90% counting a second issue).

## Public demo mode

Set `PUBLIC_DEMO=1` (on Streamlit Community Cloud: in the app's *Secrets* as `PUBLIC_DEMO = "1"`) to make the
dashboard read-only: no Refresh button, no fix tracking and no Gemini calls. Data still updates every Monday
through the GitHub Action.
