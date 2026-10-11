"""Weekly digest: "How are our Play Store ratings?" answered in one page, readable in a minute.

Built from saved data only (no network, no LLM). The weekly GitHub Action writes it to
docs/weekly_digest.md and keeps a dated copy in docs/digests/.
"""

from __future__ import annotations

import os

import pandas as pd

from src import analysis, benchmark, config, fix_tracker
from src.classifier import category_name

PRIMARY_APP = next(a for a, m in config.APPS.items() if m.get("primary"))
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "")


def _window(df: pd.DataFrame, end, days: int, offset: int = 0) -> pd.DataFrame:
    hi = end - pd.Timedelta(days=offset)
    return df[(df["review_date"] > hi - pd.Timedelta(days=days)) & (df["review_date"] <= hi)]


def _week_numbers(d: pd.DataFrame) -> dict:
    unhappy = d[d["rating"] <= 2]
    return {"reviews": len(d),
            "avg": d["rating"].mean() if len(d) else None,
            "pct1": (d["rating"] == 1).mean() * 100 if len(d) else None,
            "replied": int(unhappy["has_reply"].sum()), "unhappy": len(unhappy)}


def _fmt(v, spec, suffix=""):
    return "–" if v is None or pd.isna(v) else f"{v:{spec}}{suffix}"


def store_change(snapshots: pd.DataFrame | None, app_id: str, min_days: int = 6) -> str:
    """Store rating now vs the latest snapshot at least `min_days` older."""
    if snapshots is None or snapshots.empty:
        return "Store rating: no snapshot yet."
    s = snapshots[snapshots["app_id"] == app_id].copy()
    if s.empty:
        return "Store rating: no snapshot yet."
    s["snapshot_time"] = pd.to_datetime(s["snapshot_time"])
    now = s.iloc[-1]
    older = s[s["snapshot_time"] <= now["snapshot_time"] - pd.Timedelta(days=min_days)]
    line = f"Store rating: **{now['score']:.3f}★** from {int(now['ratings']):,} ratings"
    if older.empty:
        return line + " (week-on-week change will show once there's a snapshot from a week ago)."
    prev = older.iloc[-1]
    return (line + f" ({now['score'] - prev['score']:+.3f}★ and {int(now['ratings'] - prev['ratings']):+,} ratings "
                   f"since {prev['snapshot_time']:%d %b})")


def build(data: pd.DataFrame, snapshots: pd.DataFrame | None, tracker: pd.DataFrame | None = None,
          bench: pd.DataFrame | None = None, app_id: str = PRIMARY_APP) -> str:
    app = analysis.filter_period(data, app_id)
    if app.empty:
        return "# Weekly ratings digest\n\nNo reviews yet."
    end = app["review_date"].max()
    this_week, last_week = _week_numbers(_window(app, end, 7)), _week_numbers(_window(app, end, 7, offset=7))
    quarter = _window(app, end, 90)
    status = analysis.weekly_status(app)
    tracker = tracker if tracker is not None else pd.DataFrame(columns=["category", "status", "since", "note"])
    tracked = set(tracker["category"])
    name = config.APPS[app_id]["name"]

    lines = [f"# MoveInSync Play Store ratings: week to {end:%d %b %Y}",
             "",
             f"*{name} · written reviews up to {end:%d %b %Y} · generated automatically from public Google Play data*",
             "",
             f"## Status: {status['status']}",
             ""]
    lines += [f"- {r}" for r in status["reasons"]]

    lines += ["", "## This week in numbers", "",
              "| | This week | Last week |", "|---|---|---|",
              f"| New written reviews | {this_week['reviews']} | {last_week['reviews']} |",
              f"| Average stars | {_fmt(this_week['avg'], '.2f', '★')} | {_fmt(last_week['avg'], '.2f', '★')} |",
              f"| 1★ share | {_fmt(this_week['pct1'], '.0f', '%')} | {_fmt(last_week['pct1'], '.0f', '%')} |",
              f"| 1–2★ reviews answered | {this_week['replied']} of {this_week['unhappy']} | "
              f"{last_week['replied']} of {last_week['unhappy']} |",
              "", store_change(snapshots, app_id),
              ""]
    if this_week["reviews"] < 30:
        lines += [f"_One week is a small sample ({this_week['reviews']} reviews), so week-to-week moves are mostly "
                  f"noise. The status above uses 30–90 day windows._", ""]

    lines += ["## What to fix (last 90 days)", ""]
    summary = analysis.issue_summary(quarter)
    top = analysis.top_fixes(summary, n=3, exclude=tracked)
    for i, r in top.iterrows():
        bd = analysis.sub_issue_breakdown(quarter, r["category"])
        spec = bd[bd["actionable"]] if not bd.empty else bd
        start = f" Start with: **{spec.iloc[0]['problem']}** ({spec.iloc[0]['owner']})." if not spec.empty else ""
        lines.append(f"{i + 1}. **{r['issue']}**: {r['pct_of_complaints']:.0f}% of complaints.{start}")
    if top.empty:
        lines.append("Nothing new to rank (all top issues are in the fix tracker).")

    if not tracker.empty:
        lines += ["", "## Fixes in progress", ""]
        for t in tracker.itertuples():
            p = analysis.fix_progress(app, t.category, t.since)
            lines.append(f"- **{category_name(t.category)}** ({t.status.lower()} since {pd.Timestamp(t.since):%d %b}): "
                         f"{_fmt(p['per_100_before'], '.1f')} → {_fmt(p['per_100_after'], '.1f')} complaints per 100 "
                         f"reviews. **{p['verdict']}**.")

    if bench is not None and not bench.empty:
        rival = bench[bench["name"] == "Routematic"]
        mis = bench[bench["app_id"] == app_id]
        if len(rival) and len(mis) and pd.notna(rival.iloc[0]["reply_rate_unhappy"]):
            lines += ["", "## Against the competition", "",
                      f"Store rating {mis.iloc[0]['store_score']:.2f}★ vs Routematic {rival.iloc[0]['store_score']:.2f}★. "
                      f"Routematic answers {rival.iloc[0]['reply_rate_unhappy']:.0f}% of its unhappy reviews; "
                      f"MoveInSync {mis.iloc[0]['reply_rate_unhappy']:.0f}% "
                      f"(measured {pd.to_datetime(bench['fetched_at']).max():%d %b})."]

    week = _window(app, end, 7)
    quotes = week[(week["rating"] <= 2) & (week["review_text"].fillna("").str.split().str.len() >= 8)]
    quotes = quotes.sort_values(["thumbs_up", "review_date"], ascending=False).head(3)
    if len(quotes):
        lines += ["", "## In their words (this week)", ""]
        for q in quotes.itertuples():
            text = str(q.review_text).replace("\n", " ")
            lines.append(f"> {q.rating}★ · {q.issue_name}: \"{text[:220]}{'…' if len(text) > 220 else ''}\"")
            lines.append("")

    lines += ["", "---", f"Full detail: {DASHBOARD_URL}" if DASHBOARD_URL else
              "Full detail: open the dashboard (`streamlit run app.py`).",
              "Reviews describe experiences, not proven causes; confirm in MoveInSync's own data before building."]
    return "\n".join(lines).replace("\n\n\n", "\n\n") + "\n"


def write(text: str, end) -> tuple:
    """Save as docs/weekly_digest.md (latest) and docs/digests/<date>.md (history)."""
    latest = config.ROOT / "docs" / "weekly_digest.md"
    dated = config.ROOT / "docs" / "digests" / f"{pd.Timestamp(end):%Y-%m-%d}.md"
    dated.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text(text, encoding="utf-8")
    dated.write_text(text, encoding="utf-8")
    return latest, dated


def load_inputs():
    from src import pipeline
    data = pipeline.load_labelled()
    snaps = pd.read_csv(config.SNAPSHOTS_CSV) if config.SNAPSHOTS_CSV.exists() else None
    return data, snaps, fix_tracker.load(PRIMARY_APP), benchmark.latest()
