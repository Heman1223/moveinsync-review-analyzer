# MoveInSync Play Store Ratings — Project Spec v2

> v2 replaces the v1 build spec. The main change: **the deliverable is a recommendation, not a tool.** The tool is the evidence behind the recommendation and the answer to "we'll keep asking this question".

---

## 1. What the case study actually asks

From the MoveInSync FDE assignment:

- **Problem:** "Our Play Store ratings are lower than they should be." Work out **why**, then say **exactly what to do to raise them: what to fix and what to do first.**
- **Bar:** specific enough that a product or engineering team **could start the next day.**
- **Data:** nothing provided; everything needed is public.
- **Tools:** anything, AI included.
- **Recurring:** "How are our Play Store ratings?" will be asked again. It is not a one-time question.
- **Submit:** (1) the recommendation, in whatever form will get it acted on, and (2) a short note on how I got there and which tools I used.

### What gets submitted

| # | Deliverable | Purpose |
|---|---|---|
| 1 | **Recommendation memo** (1–2 pages, or a 5-slide deck) | The answer. Primary deliverable. |
| 2 | **Review analyzer dashboard** (Streamlit, deployed link) | The evidence, and the repeatable answer to the recurring question. |
| 3 | **Method note** (half a page) | How I got there, which tools, assumptions, limitations. |
| 4 | **GitHub repo + README** | Lets anyone reproduce it. |

**Rule:** if time runs short, a sharp memo with basic analysis beats a polished dashboard with no recommendation.

---

## 2. Early evidence (live pull, 10 Oct 2026)

The data shows a clear story before any classification is done:

| Metric | Value |
|---|---|
| Employee app `com.moveinsync.ets`, lifetime rating | **4.64** (114,854 ratings; ~6% 1★) |
| Same app, latest 1,000 reviews (14 Jun – 9 Oct 2026) | **3.77 avg; 26% 1★** |
| Developer replies in those 1,000 reviews | **5 (0.5%)** |
| Driver Partner `com.moveinsync.driver.dco` | 3.5★ lifetime; only 7 text reviews |
| Partner Lite `com.moveinsync.driver.lite` | 4.25★ lifetime; 108 text reviews |
| Employee app text reviews available | ~23,600 |

~~Working hypothesis: recent sentiment has dropped sharply.~~ **Disproved by the full fetch (11 Oct 2026):** text reviews have averaged 3.5–3.9★ with 24–30% 1★ in every quarter since 2023. There was no recent drop.

**Revised picture (full history, 24,317 employee-app text reviews):**
- **Two populations.** About 90k people rated without writing a review, mostly 5★, which keeps the store score at 4.64. The ~24k who write text are far unhappier (about 25% 1★ vs about 6% across all ratings). The written reviews are what people read on the listing.
- **Developer replies stopped in mid-2024.** The reply rate was about 97–98% through 2024 Q1, fell to 53% in Q2, and has been 0–10% since 2024 Q3. This is a clear process change, worth a recommendation.
- Store score history can't be reconstructed from public data. `snapshots.csv` builds it from now on.

---

## 3. Scope

### Apps covered ("our apps" is plural)
| App | Package ID | Who uses it | Role |
|---|---|---|---|
| MoveInSync (Employee) | `com.moveinsync.ets` | Employees: book, track, board | **Default and primary focus** (~23.6k text reviews) |
| Moveinsync Partner – Lite | `com.moveinsync.driver.lite` | Drivers: run assigned trips | Secondary; low-data warning (~111 text reviews) |

Out of scope, with the reason stated in the method note:
- `com.moveinsync.driver.dco` (Driver Partner): an onboarding form for prospective drivers; 46 ratings and 7 text reviews; not part of the commute.
- `field.moveinsync.ets` (Field app): admin and supervisor tool; 24 ratings.
- `com.workinsync.meeting` (Workplace): meeting-room and visitor kiosk; no ratings.

Apps are listed in `src/config.py`; adding one back is a one-line change.

### Not in this version
- Authentication, a database, a custom React frontend.
- Automatic ticket creation, emailing teams, or replying to reviews from the tool.
- Contacting reviewers or asking them to change ratings.
- Claims that a review proves a specific technical root cause.

---

## 4. Data collection

- Library: `google-play-scraper` (unofficial; say so). Verify function signatures against the installed version.
- **Fetch all available reviews, sorted NEWEST**, using continuation tokens. No sample-size picker.
- **Incremental refresh:** on later runs, fetch only until reaching a `review_id` we already have.
- Settings: `lang='en'`, `country='in'`, stated as an assumption (Hinglish reviews still come through).
- **App snapshot on every refresh:** call `app()` and append `score`, `ratings`, `reviews`, `histogram`, `version`, and the timestamp to `snapshots.csv`. Over time this gives a real rating history.
- Deduplicate by `review_id`. Never overwrite good data with a failed fetch. Never substitute fake data.
- Do not store `userName` or `userImage`.

### Review fields
| Column | Source |
|---|---|
| `app_id` | added |
| `review_id` | `reviewId` |
| `review_text` | `content` (original, untouched) |
| `rating` | `score` |
| `review_date` | `at` (ISO, normalized) |
| `review_version` | `reviewCreatedVersion` (blank if missing) |
| `thumbs_up` | `thumbsUpCount` |
| `has_reply` / `reply_text` / `reply_date` | `replyContent`, `repliedAt` |
| `is_low_info` | derived: e.g. under 4 words with no category keyword ("good", "nice app") |

---

## 5. Classification: rules first, LLM for the long tail

### 5.1 Build the categories from the data first
Before writing any rules, **read about 100 recent 1–3★ reviews by hand** and note the themes. Then finalize the list below. This becomes a line in the method note.

Starting category list (edit after reading):

| Category | Fixable by | Notes |
|---|---|---|
| Booking / Scheduling | App | cut-off windows, slot missing, booking failed |
| Cab late / ETA / Tracking | Ops + App | live tracking accuracy vs actual lateness |
| Driver behaviour | Ops | rude, rash driving, phone use |
| Wrong route / Routing | Ops + App | long routes, too many pickups |
| No-show / Attendance dispute | Ops + App | marked no-show, OTP dispute |
| App crash / Performance | App | crash, freeze, slow, battery |
| Login / OTP / Account | App | OTP not received, SSO, logout |
| Notifications | App | missing or late pickup alerts |
| Support / Complaint unresolved | Ops | "raised complaint, no response" |
| **Safety concern** | **Human review** | always flagged, never ranked down by low volume |
| Other / Unclassified | — | goes to the LLM step |
| Rating only / Low info | — | excluded from issue counts, included in rating metrics |

The "Fixable by" values (**App / Ops / Human review**) are a key output. Many 1★ reviews are about cab operations, not the app, and need a different fix.

### 5.2 Rule engine (core, deterministic)
- Keywords live in `config.py`, one list per category, including **Hinglish variants** (e.g. `nahi aayi`, `nhi aaya`, `booking nahi`).
- Lowercase and normalize whitespace; use word-boundary regexes; keep the original text unchanged.
- Multi-label allowed. Store `categories` (all matched), `primary_category` (first by priority order), and `matched_keywords`.
- `label_source = "rule"`.

### 5.3 LLM assist (two narrow jobs)
**Job A: classify only the unclassified reviews.**
- Input: reviews where rules found nothing (and not low-info). **Send review text only**, never names.
- The model must choose from the fixed category list. Output JSON:
  `{category, secondary, fixable_by, is_safety, short_reason}`
- **Cached by `review_id`** in `labels_llm.csv`, so each review is classified once. Refreshes only send new reviews.
- `label_source = "llm"`; the UI shows `short_reason`.

**Job B: suggest keywords; a person approves them.**
- The LLM reads the remaining unclassified reviews and proposes new keyword → category pairs into `keyword_suggestions.csv`.
- I review them and copy approved ones into `config.py`. The rules improve each run; every rule is still approved by a person.

**Model:** `claude-haiku-5-5` for Jobs A and B (cheap and fast). Optional: `claude-sonnet-5-5` to draft memo text from the computed tables. Gemini's free tier is an acceptable swap if there's no budget.
**Without an API key:** the app runs rules-only and shows a note. Nothing breaks.
**Secrets:** `.env` locally and Streamlit secrets when deployed. Never commit keys.

### 5.4 Decision gate (measure, don't guess)
After rules v1 runs on the real data, record the **% Unclassified**:
- under ~15%: the LLM step is optional polish.
- over ~25%: the LLM step is justified. Quote the number in the memo.

### 5.5 Validation
- Hand-label **150 reviews** in `data/gold_labels.csv`.
- Report accuracy for rules-only and for rules + LLM. One line in the README and the method note.

---

## 6. Analysis and prioritisation

Computed per app, for the selected period:

- Rating metrics: average rating, 1★ share, count, star distribution (all reviews, including low-info).
- **Trend:** average rating by month, with release markers from `review_version`.
- **By version:** average rating and review count per app version (flag versions with n < 30).
- **Reply health:** % of 1–2★ reviews with a developer reply; median reply delay.
- Per category: unique review count, % of issue reviews, average rating, thumbs-up weight, Fixable by, top quotes (low-rated reviews first, most thumbs-up).

### Priority = estimated rating impact
For each category *c* (primary category only, to avoid double counting):

```
uplift_c = Σ (4 − rating)  over reviews in c with rating ≤ 2
           ─────────────────────────────────────────────
                 total reviews in the period
```

In plain words: "if this category's 1–2★ reviewers had been satisfied enough to give 4★, the average would rise by about +uplift_c." Show it as "could lift rating by about +0.2".
- Clearly a what-if, not a forecast. Say so once in "How this works".
- **Safety concerns are always pinned and flagged** for human review, whatever their uplift.

---

## 7. Dashboard (Streamlit)

### Design rules
- A first-time visitor understands the page in **10 seconds**: four numbers, one chart, three cards.
- **Every number can be clicked** to see the reviews behind it.
- Plain language: "Fixable by: Ops", not `suggested_owner`.
- No ML jargon on screen. Method details go in a "How this works" expander and the README.

### Layout (single page, top to bottom)
1. **Header:** title, "Updated <time> · public Play Store reviews", **Refresh data** button (the only action button).
2. **Filters:** app switcher (segmented: Employee app · Partner Lite · Compare) and period (30 days · 90 days · 6 months · All time).
   - Low-data warning banner when the filtered sample has fewer than 30 reviews.
3. **KPI row:** Recent rating (vs lifetime) · 1★ share · Reviews replied to (vs target) · Reviews analysed.
4. **Trend chart:** average rating by month, dashed lines at releases.
5. **"Fix these first":** top 3 cards, each with a tag (App fix / Ops fix / Quick win), title, % of 1★, uplift, owner.
6. **All issues table:** issue · reviews · avg ★ · fixable by · uplift. Click a row to see quotes (rating, date, version, source = rule/llm, matched keywords or reason).
7. **Compare all view:** one row per app with recent rating, lifetime rating, 1★ share, reply rate, n.
8. **Export:** review-level CSV and issue-summary CSV.
9. **How this works** (expander): data source, rules + LLM, uplift formula, limitations, % unclassified, validation accuracy.

### Stretch: grounded "Ask the data" panel (build last, optional)
- Answers **only** from the computed tables plus retrieved reviews; never estimates numbers on its own.
- Every answer cites review IDs or quotes.
- 3–4 starter question buttons (e.g. "Why did ratings drop in September?", "What do Hinglish reviews complain about?").

---

## 8. The recommendation memo (primary deliverable)

Structure:
1. **Headline (2 lines):** current state and the single most important action.
2. **Diagnosis:** lifetime vs recent rating; when the drop happened; which version or period; what share is app vs ops.
3. **Top 3–5 recommendations.** Each one includes:
   - Evidence: count, % of 1★, uplift, 2 real quotes
   - Owner (Product / Engineering / Ops / Support)
   - **First step for tomorrow** (concrete)
   - Success metric and how the dashboard will show it
4. **Non-bug levers to evaluate** (include only those the data supports):
   - **In-App Review API timing:** ask for a rating right after a successful trip, not at random.
   - **In-app "Report a problem"** before the rating prompt, so complaints become tickets instead of 1★ reviews.
   - **Reply to reviews:** reply to most 1–2★ reviews (currently 0.5%); reviewers can update their rating.
   - **Release safeguards:** staged rollouts and crash-rate checks in Android vitals before full release.
   - **Ops feedback loop:** send ops-category complaints to the client transport desk on a weekly cadence.
5. **What I'd do first and why** (sequencing: quick wins this week, then fixes this sprint, then structural changes).
6. **Assumptions and limitations** (short).

Method note: data source and dates, sample sizes, how categories were built, rules + LLM design, validation accuracy, tools used (Python, google-play-scraper, pandas, Streamlit, Claude), and what I'd do with internal data (crash logs, booking funnel, trip ETA data).

---

## 9. Project structure

```text
moveinsync-review-analyzer/
├── app.py                 # Streamlit UI only
├── refresh.py             # CLI: python refresh.py  → fetch + classify + snapshot
├── src/
│   ├── config.py          # apps, categories, keywords, owners, thresholds
│   ├── collector.py       # fetch, normalize, incremental refresh, snapshots
│   ├── classifier.py      # rule engine
│   ├── llm_assist.py      # Job A (classify long tail) + Job B (keyword suggestions)
│   └── analysis.py        # metrics, trend, versions, reply health, uplift
├── data/
│   ├── reviews.csv
│   ├── labels_llm.csv
│   ├── keyword_suggestions.csv
│   ├── snapshots.csv
│   └── gold_labels.csv
├── deliverables/
│   ├── recommendation_memo.md
│   └── method_note.md
├── tests/
│   ├── test_classifier.py
│   └── test_analysis.py
├── .env.example           # ANTHROPIC_API_KEY=
├── requirements.txt
├── README.md
└── .gitignore             # .env, venv, __pycache__
```

Data processing never imports Streamlit, so it can be tested and run from the CLI.

---

## 10. Tests (offline, synthetic text only)

- An English booking complaint → Booking.
- A Hinglish complaint ("cab nahi aayi") → Cab late.
- A review mentioning two issues → both categories; one primary.
- Word boundary: "mapping" doesn't trigger a "map" rule.
- Empty or low-info text → Rating only / Low info.
- A safety phrase → `is_safety=True` and pinned.
- Duplicate `review_id`s are removed.
- Missing version or reply fields don't crash the analysis.
- The uplift calculation is deterministic and correct on a small hand-checked example.
- The LLM module is mocked; with no API key it falls back to rules-only.

---

## 11. Build order (milestones)

| # | Milestone | Done when |
|---|---|---|
| M1 | Setup | venv, repo, requirements, folders, `.env.example` |
| M2 | Collector + snapshots | All 3 apps fetched to CSV; incremental refresh works |
| M3 | Exploratory read | Trend by month and version, reply rate, ~100 reviews read; categories finalized |
| M4 | Rules v1 + tests | Classifier runs; **% unclassified measured** |
| M5 | LLM assist | Jobs A and B with caching; gold-set accuracy reported |
| M6 | Analysis + uplift | All metrics computed; top 3 identified |
| M7 | **Memo draft** | Recommendations written from real numbers |
| M8 | Dashboard | Layout in §7; works with missing fields and no API key |
| M9 | Ship | Deployed on Streamlit Cloud; README; method note; final memo |
| M10 | Stretch | Grounded "Ask the data" panel |

---

## 12. Interview talking points

- "The lifetime 4.64 hides a recent 3.77. Google weights recent reviews, so that's the number to fix."
- "Not every 1★ is an app bug. I split issues by who can fix them (App vs Ops), because they need different fixes."
- "Rules first for transparency. The LLM handles the Hinglish long tail and suggests new rules, and a person approves every rule."
- "I measured instead of assuming: X% unclassified by rules, Y% accuracy on 150 hand-labelled reviews."
- "Priority is the estimated rating impact, not raw count, and safety issues are always surfaced."
- "It's built for the recurring question: one command refreshes it, and snapshots build a rating history over time."
