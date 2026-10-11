# MoveInSync Play Store Ratings — Spec v3

> v3 builds on v2 (`docs/SPEC_v2.md`), which is now implemented: collector, rules + LLM classifier,
> analysis, dashboard, sub-problem playbook, fix tracker. v3 is about **winning the case**: turning a
> strong analysis engine into a recommendation a team acts on the next day, and answering
> "how are our ratings?" every week without anyone asking.
>
> Written 11 Oct 2026 after reviewing another candidate's submission (a Streamlit "Review Intelligence"
> dashboard). Their strengths were noted so we can meet that bar. **Nothing is copied**: no layout,
> wording or code.

---

## 1. Where we stand

### Compared with the other submission
| Area | Them | Us |
|---|---|---|
| Action cards (what to do, owner, effort, metric, "check in your own data", how to verify) | ✅ strong | 🟡 first step only |
| Statistical care (uncertainty ranges, ranking stability, precision-adjusted counts) | ✅ | 🟡 low-data flags only |
| Weekly status line (OK / WATCH) | ✅ static | ❌ |
| Plain-language glossary, tabs | ✅ | ❌ one long page |
| Hinglish + LLM for what keywords miss, measured accuracy | ❌ | ✅ 63% → 75%, unclassified 19% → 4% |
| Specific problems inside each issue, with shares | ❌ | ✅ e.g. Login = 43% OTP, 30% forced logout |
| Fix tracker with before/after verdict, next issue moves up | ❌ | ✅ |
| Evidence that replies work (edits after reply) | ❌ "data can't say" | ✅ 13 of 22 now 4–5★ |
| Review quotes with "why labelled", filters, exports | partial | ✅ |
| Driver app (Partner Lite) | ❌ | ✅ |

**Conclusion:** they're stronger on the *recommendation*, we're stronger on the *engine*. The brief rewards the
recommendation, so v3 closes that gap and then adds things neither submission has.

### New finding: competitor benchmark (store scores, 11 Oct 2026)
| App | Package | Store score | Installs |
|---|---|---|---|
| **MoveInSync** | `com.moveinsync.ets` | **4.64** | 1M+ |
| Routematic (named by reviewers as better) | `com.routematic.employee` | 4.34 | 1M+ |
| SMT Employee | `in.smarttransport.emp` | 3.16 | 100k+ |
| Shuttl | `app.goplus.in.myapplication` | 2.97 | 1M+ |
| eFmFm Employee (named by a reviewer) | `com.app.newt.employee` | 2.81 | 100k+ |
| NeOffice Commute | `com.agiledge.myatom` | 3.49 | 10k+ |
| NxtTrans Employee | `com.nxttrans.emp` | 1.96 | 50k+ |
| *Consumer reference:* Rapido | `com.rapido.passenger` | 4.72 | 100M+ |

**Implication for the story:** MoveInSync already leads its category on store score. "Lower than they should
be" therefore means **below consumer-app standards (Uber/Rapido ~4.7) and with written reviews (3.83) far below
the store score.** Written reviews are what prospective users and HR buyers read. The benchmark must also compare
*written-review* averages and reply rates, where the peer gap may be very different. (To verify in B5.)

---

## 2. The core insight to lead with

**Ratings are a sampling problem before they are a bug problem.**
- The brief: **~1.5M employees use the app every working day.** The store has **~115k ratings in total** since 2014.
  Almost no satisfied riders are ever asked to rate.
- Those who *do* write reviews are the unhappy minority: 3.83★ and 24% 1★ (last 12 months), vs 4.64 overall.
- Reviews also say the app pushes rating pop-ups **after every ride**, so users are asked at the wrong moment, and
  the unhappy ones get annoyed.
- Developer replies to 1–2★ reviews fell from ~97% (2023) to ~4% now; when replies existed, reviewers
  did edit, and 13 of 22 recent edits-after-reply now show 4–5★.

**Therefore, three levers, in order of cost:**
1. **Ask the right people at the right moment:** use Google's In-App Review API after a completed, on-time trip;
   stop indiscriminate rating pop-ups. *(Mostly product config: days, not months.)*
2. **Answer the unhappy ones:** restart replies to 1–2★ reviews, with a reply assistant (B8) and an SLA.
3. **Fix what they complain about:** the ranked app issues and specific problems, with owners and metrics (B4).

### Policy guardrail (must be in the memo)
Google Play forbids **review gating**: asking "do you like the app?" first and sending only happy users to the store,
or asking any question before showing the in-app review card. Our recommendation therefore triggers the prompt at
a **natural positive moment** (trip completed on time) **without a sentiment pre-question**, respects Google's
prompt quota, and offers **"Report a problem"** as a separate, always-available path, not as a filter in front of
the review prompt.

---

## 3. Deliverables (what gets submitted)

| # | Deliverable | Owner | Notes |
|---|---|---|---|
| D1 | **Recommendation memo** (1–2 pages) or 5–6 slide deck | **Heman writes**; Claude supplies numbers and challenges drafts | Structure in §5 |
| D2 | **Method note** (½ page) | Heman, from a Claude draft | Data, method, accuracy, tools (Python, google-play-scraper, pandas, Streamlit, Gemini, Claude Code), assumptions, limitations |
| D3 | **Deployed dashboard** link | Claude builds, Heman deploys | Safe for a public link (§4 C) |
| D4 | **GitHub repo + README** | Claude drafts | Setup on Windows/macOS/Linux, how to refresh, method |
| D5 | **2-minute walkthrough video** (optional, high value) | Heman records | Linked at the top of the app and memo |

---

## 4. Build workstreams

### A. Speed and structure (do first: everything else sits on it)
- **A1 Precompute labels.** Refresh writes `data/reviews_labelled.csv` (rules + cached LLM + sub-problems). The app
  only reads it, so no "Classifying reviews…" on page load. Cold start under ~5 s.
- **A2 Tabs:** **Summary · Issues · Fix tracker · Benchmark · How it works.**
- **A3 Glossary:** one-line plain-English definitions shown where each term appears (tooltips) and in How it works:
  written-review rating, store rating, rating impact, per 100 reviews, low-info review, App/Ops fix.

### B. Features
- **B1 Plain-English summary (top of the Summary tab):** three auto-generated sentences, e.g.
  *"Store rating 4.64 looks healthy, but people who write reviews average 3.83. The biggest fixable cause is
  login: mostly OTP not arriving. Start there, and restart replying to reviews (4% answered)."*
- **B2 Weekly status: OK / WATCH / ALERT,** with transparent rules (e.g. ALERT if the 1★ share in the last 30 days
  is up ≥5 points vs the previous 90 with enough reviews; WATCH if any issue's share rises ≥5 points, or the reply
  rate is below 20%). Shows the reason in words.
- **B3 Uncertainty:** Wilson ranges on 1★ share for months and versions; grey out bars with too few reviews. Keep it
  simple: "plausible range", not statistics jargon.
- **B4 Action cards at the specific-problem level.** Extend `src/playbook.py` entries with: **owner**,
  **effort (1–5)**, **metric to watch**, **check first in MoveInSync's own data**, **how to verify**. Cards show
  these; "Mark as being fixed" puts the problem in the fix tracker, whose before/after numbers are the verify step.
  (Tracker granularity: issue level stays; the specific problem is shown in the note.)
- **B5 Benchmark tab.** Peer apps from §1 plus 1–2 consumer references. For each: store score, ratings count,
  installs, and from the newest ~500 reviews: written-review average, 1★ share, reply rate to 1–2★.
  Rules-only classification of peers' top complaint themes is optional. Refreshed with the main refresh (capped).
  Public data only; no claims about competitors beyond the numbers.
- **B6 What-if planner.** Sliders: reply rate (%), reduction in complaints for each top issue (%), in-app prompt
  share of daily trips (%). Output: projected written-review average and 1★ share; for the in-app prompt, extra
  ratings per day and an illustrative effect on the store score. Every assumption shown next to the result;
  labelled "illustration, not a forecast".
- **B7 Rating-ask calculator** (part of B6): 1.5M daily riders (from the brief) × prompt share × Google quota ×
  typical completion rate (stated assumption) → ratings/day vs today's pace (from `snapshots.csv` once there are
  two or more snapshots; until then, an estimate stated as such).
- **B8 Reply assistant.** In the Issues tab, for an unanswered 1–2★ review: **"Suggest a reply"**.
  - Without a key, or on the public deploy: a template for its specific problem (from the playbook), filled with
    safe placeholders.
  - With a key, locally: Gemini drafts a short, polite, specific reply (one call, on click, cached by review_id,
    counted against the per-run cap).
  - Always: "Copy" button; a person reviews and posts in the Play Console. No auto-posting; no promises of refunds
    or compensation; no personal data.
- **B9 Weekly digest.** `python -m scripts.digest` writes `docs/weekly_digest.md`: status, what changed versus last
  week, top rising problem, tracked fixes' progress, reply rate, 3 example quotes. Readable by a manager in 60 s.
- **B10 Automatic weekly run.** A GitHub Actions workflow (weekly cron): refresh reviews (rules only by default, to
  protect Gemini credits; optional LLM via a repo secret with the existing cap), regenerate snapshot, digest and
  labels, commit the data back. The deployed app picks up the new data automatically. Also creates a store-score
  history week by week.

### C. Deploy hardening
- **C1** Streamlit toolbar in viewer mode (hide developer items; keep Settings → Theme).
- **C2** `DISABLE_LLM=1` on the public deploy: no Gemini calls from visitors (refresh and reply assistant use
  rules/templates).
- **C3** Fix tracker on the public link: read-only "demo" mode with a sample entry, or a clear banner that changes
  reset.
- **C4** README, method note, `requirements.txt` pinned to versions known to work.
- **C5** Check: phone width, light and dark mode, table row-click, cold start time.

---

## 5. Memo structure (D1)

1. **Headline (2 lines):** current state plus the single most important action.
2. **Diagnosis:**
   - category leader on store score (benchmark), but written reviews average 3.83 and 24% 1★
   - two populations (silent raters vs reviewers)
   - replies stopped in 2024
   - top fixable issues and their specific problems
   - release regressions (v12.19)
3. **Recommendations (3 levers, §2):** each with evidence, owner, first step for tomorrow, metric, target.
4. **30/60/90-day plan with targets** (fill from data):
   - *Week 1:* restart replies (target 80% of new 1–2★ within 48 h); make trip rating skippable; show the transport
     policy only when it changes; stop rating pop-ups after every ride.
   - *30 days:* In-App Review prompt after on-time trips (policy-compliant); OTP delivery fallback and monitoring;
     forced-logout fix.
   - *60–90 days:* booking flow fixes; startup/crash fixes; tracking staleness indicator.
   - Targets e.g. written-review 1★ share 24% → ≤18%; written-review average 3.83 → ≥4.1; reply rate 4% → 80%.
5. **What I'd check in MoveInSync's own data** (crash logs, OTP delivery, booking funnel, GPS ping logs).
6. **How you'll know it's working:** the dashboard's tracker and weekly digest.
7. **Assumptions and limitations:** written vs all ratings, scraper is unofficial, keyword and LLM accuracy, English/Hinglish
   only, uplift and what-ifs are illustrations.

---

## 6. Build order

| # | Item | Why this order |
|---|---|---|
| 1 | A1 precompute, A2 tabs, A3 glossary, B1 summary | Foundation; every later item lands in a tab |
| 2 | B4 action cards | Closes the biggest gap against the other submission |
| 3 | B5 benchmark | New insight; feeds the memo headline |
| 4 | B2 status, B3 uncertainty | Rigour; small |
| 5 | B6/B7 what-if planner | Turns analysis into targets |
| 6 | B8 reply assistant | Our strongest finding, made usable tomorrow |
| 7 | B9 digest, B10 weekly automation | Answers "we'll keep asking" for real |
| 8 | C1–C5 hardening, README, deploy | Ship |
| 9 | D1 memo, D2 method note (Heman), D5 video | With final numbers in hand |

Gemini budget: B5 and B10 are rules-only by default; B8 makes at most one call per click locally and none on the public
deploy. Expected extra spend: negligible.

---

## 7. Not doing
- Copying the other submission's layout, wording or scoring formula.
- A chatbot (dropped: the reply assistant is a more useful AI feature).
- Auto-posting replies, contacting reviewers, or any review gating.
- Claims about competitors beyond public numbers.

---

## 8. Interview narrative
1. *"My first hypothesis, a recent decline, was disproved by the full data, so I changed the story."*
2. *"MoveInSync already leads its category on store score. The real gap is written reviews: 3.83 vs 4.64."*
3. *"It's a sampling problem first: 1.5M daily riders, almost none asked at a good moment, and the unhappy ones get
   pop-ups. Fix how and when you ask, within Google's no-gating policy."*
4. *"Then answer the unhappy: replies worked before; they stopped in 2024."*
5. *"Then fix the app issues, down to specific problems, with owner, metric and verify step."*
6. *"And close the loop: the tracker shows whether a fix reduced complaints, and the weekly digest answers 'how are
   our ratings?' automatically."*
