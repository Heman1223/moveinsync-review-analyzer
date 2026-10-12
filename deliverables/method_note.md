# How I got there, and which tools I used

**Heman Sharma · MoveInSync FDE case study · 12 Oct 2026**

## Data
- **Source:** public Google Play reviews and listing pages, collected with `google-play-scraper` (an unofficial open-source library, not a Google API). No reviewer names or photos are stored.
- **Apps:** the MoveInSync employee app (24,317 written reviews, Mar 2014 – Oct 2026) and Partner Lite, the driver app (111 reviews). Driver Partner (an onboarding form), the Field app and Workplace were left out: they aren't part of the commute and have very few reviews.
- **Benchmark:** 10 comparable apps (Routematic, eFmFm, SMT, NeOffice, Commute, NxtTrans, Shuttl, Uber, Rapido, Ola), each measured the same way: listing numbers plus the newest 500 written reviews.

## Method
1. **Read first.** I fetched everything, looked at trends by quarter and app version, then had 100 random recent complaints read and labelled by theme (AI-assisted, with Claude) before writing any rules.
2. **Sort complaints with readable rules.** I built 13 issue categories from that reading, with English and Hinglish keywords, matched as whole words.
3. **AI only for what the rules missed.** Reviews the rules couldn't place (often Hinglish or vague) went to Google Gemini, which had to choose from the same 13 categories and give a one-line reason. Gemini also suggested new keywords. I only added the 12 that held up on the data, and I approved each one. Each review is sent at most once; the results are saved.
4. **Check accuracy honestly.** On 100 reviews not used to build anything: rules alone found the right main issue 63% of the time; rules plus Gemini 75% (90% counting a second issue). Unsorted complaints dropped from 19% to 4%. The reference labels for that check were made independently of Gemini, with a different AI model (Claude).
5. **Rank by impact, not by count.** Rating impact = for each issue, the sum of (4 − stars) over its 1–2★ reviews, divided by all written reviews. That is how much the average would rise if those reviewers had been satisfied. Safety complaints are always shown separately, however few.
6. **Turn issues into actions.** Each issue is split into specific problems (for example, Login → OTP not received, forced logout). Each problem has an action, owner, effort, a measure, and what to check in MoveInSync's own data.
7. **Make it repeatable.** A weekly GitHub Action refreshes the data and writes a one-page digest. A fix tracker compares complaints before and after a fix ships. Simple published rules give a weekly OK / WATCH / ALERT status, and charts show plausible ranges so small samples don't mislead.

## What changed my mind along the way
- **"Ratings dropped recently."** My first look at the newest 1,000 reviews suggested a recent decline. The full history showed written reviews have been at 3.5–3.9★ for years. The real change was replies stopping in 2024.
- **"Not enough users are asked to rate."** The benchmark showed MoveInSync already collects the most ratings per install of all 11 apps (11.5 per 100, against 2–5). So I dropped that idea and focused on replies and app fixes.

## Tools
- **Python** (pandas for analysis, Streamlit and Plotly for the dashboard, pytest for 68 automated tests)
- **google-play-scraper** for the data
- **Google Gemini** (`gemini-3.8-flash`) for sorting reviews the rules missed, suggesting keywords, and optional reply drafts
- **Claude Code** (Anthropic) as an AI assistant throughout: writing and testing the code, reading and labelling review samples, and drafting this memo and note. I set the direction, made the scope and design decisions, and reviewed the results
- **GitHub** and **GitHub Actions** for code, history and the weekly automatic update; **Streamlit Community Cloud** for the live dashboard

## Limits
Reviews show what people experienced, not proven causes. Written reviewers are more critical than people who only tap a star. Google shows only the latest version of an edited review. Keyword sorting can be confused by shift words such as "login cab" and "logout cab". Effort scores and targets are judgement calls, stated as such.
