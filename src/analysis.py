"""Metrics, issue ranking and evidence. Pure pandas: no Streamlit, no network, no LLM calls.

Every number the dashboard or memo shows is computed here, so it can be tested
and reproduced from the saved CSVs.

Key idea, "rating impact" (uplift) for an issue category c:

    uplift_c = sum(4 - rating) over reviews whose main issue is c and rating <= 2
               -------------------------------------------------------------
                       number of written reviews in the period

"If those unhappy reviewers had been satisfied enough to give 4 stars, the average
written-review rating would rise by about +uplift_c." It is a what-if for ranking,
not a forecast. Written reviews are a subset of all ratings, so the effect on the
store score would be smaller.
"""

from __future__ import annotations

import re

import pandas as pd

from src import config
from src.classifier import category_name, classify_df, fixable_by, normalize
from src.playbook import SUB_ISSUES

SPECIAL = {config.OTHER, config.LOW_INFO, config.NO_TEXT}
UPLIFT_TARGET = 4
SATISFIED_MIN, UNHAPPY_MAX = 4, 2


# ---------------------------------------------------------------------------
# Preparation and filtering
# ---------------------------------------------------------------------------
def prepare(reviews: pd.DataFrame, llm_labels: pd.DataFrame | None = None) -> pd.DataFrame:
    """Rules first, then cached LLM labels for what rules missed. Adds helper columns."""
    from src.llm_assist import apply_llm_labels  # local import keeps analysis usable without the SDK

    df = classify_df(reviews)
    df = apply_llm_labels(df, llm_labels)
    df["review_date"] = pd.to_datetime(df["review_date"])
    df["reply_date"] = pd.to_datetime(df["reply_date"])
    df["has_reply"] = df["has_reply"].astype(bool)
    df["is_complaint"] = df["rating"] <= config.COMPLAINT_MAX_RATING
    df["is_substantive"] = ~df["primary_category"].isin({config.LOW_INFO, config.NO_TEXT})
    df["issue_name"] = df["primary_category"].map(lambda c: c if c in SPECIAL else category_name(c))
    df["fixable_by"] = df["primary_category"].map(lambda c: "" if c in SPECIAL else fixable_by(c))
    df["month"] = df["review_date"].dt.to_period("M").dt.to_timestamp()
    df["sub_issue"] = [assign_sub_issue(t, c) for t, c in zip(df["review_text"], df["primary_category"])]
    return df


# ---------------------------------------------------------------------------
# Sub-issues (playbook): what exactly inside an issue, and a first step
# ---------------------------------------------------------------------------
OTHER_SUB = "other"
_SUB_RX = {
    cat: [(sub, re.compile(r"\b(?:" + "|".join(sub["keywords"]) + r")\b")) for sub in subs]
    for cat, subs in SUB_ISSUES.items()
}


def assign_sub_issue(text, category: str) -> str | None:
    """First matching sub-issue for this review's main category ('other' if none; None if no playbook)."""
    if category not in _SUB_RX:
        return None
    norm = normalize(text)
    for sub, rx in _SUB_RX[category]:
        if rx.search(norm):
            return sub["id"]
    return OTHER_SUB


def sub_issue_name(category: str, sub_id: str) -> str:
    for sub in SUB_ISSUES.get(category, []):
        if sub["id"] == sub_id:
            return sub["name"]
    return "Other / not specific"


def sub_issue_breakdown(df: pd.DataFrame, category: str) -> pd.DataFrame:
    """Sub-problems inside one issue, largest first, each with its suggested first step."""
    rows = df[df["is_complaint"] & (df["primary_category"] == category)]
    total = len(df)
    out = []
    for sub in SUB_ISSUES.get(category, []) + [{"id": OTHER_SUB, "name": "Other / not specific", "action": ""}]:
        r = rows[rows["sub_issue"] == sub["id"]]
        if r.empty:
            continue
        out.append({"sub_issue": sub["id"], "problem": sub["name"], "complaints": len(r),
                    "share": round(len(r) / len(rows) * 100, 1), "avg_rating": round(r["rating"].mean(), 2),
                    "uplift": round(_uplift(r, total), 3), "first_step": sub["action"],
                    "owner": sub.get("owner", ""), "effort": sub.get("effort"),
                    "measure": sub.get("measure", ""), "check_first": sub.get("check_first", ""),
                    "actionable": sub["id"] != OTHER_SUB and not sub.get("vague", False),
                    "latest": r["review_date"].max()})
    res = pd.DataFrame(out)
    if res.empty:
        return res
    res["_other"] = res["sub_issue"] == OTHER_SUB  # keep the catch-all last
    return res.sort_values(["_other", "complaints"], ascending=[True, False]).drop(columns="_other").reset_index(drop=True)


def filter_period(df: pd.DataFrame, app_id: str | None = None,
                  start=None, end=None) -> pd.DataFrame:
    out = df
    if app_id:
        out = out[out["app_id"] == app_id]
    if start is not None:
        out = out[out["review_date"] >= pd.Timestamp(start)]
    if end is not None:
        out = out[out["review_date"] <= pd.Timestamp(end)]
    return out


def period_start(df: pd.DataFrame, days: int | None):
    """Start date for 'last N days', anchored on the newest review (not today), so
    results don't silently shift if data is a few days old."""
    if days is None or df.empty:
        return None
    return df["review_date"].max() - pd.Timedelta(days=days)


# ---------------------------------------------------------------------------
# Headline numbers
# ---------------------------------------------------------------------------
def kpis(df: pd.DataFrame, snapshot: dict | None = None) -> dict:
    n = len(df)
    unhappy = df[df["rating"] <= UNHAPPY_MAX]
    return {
        "reviews": n,
        "avg_rating": round(df["rating"].mean(), 2) if n else None,
        "pct_1_star": round((df["rating"] == 1).mean() * 100, 1) if n else None,
        "pct_5_star": round((df["rating"] == 5).mean() * 100, 1) if n else None,
        "complaints": int(df["is_complaint"].sum()),
        "reply_rate_unhappy": round(unhappy["has_reply"].mean() * 100, 1) if len(unhappy) else None,
        "store_score": round(snapshot["score"], 2) if snapshot else None,
        "store_ratings": int(snapshot["ratings"]) if snapshot else None,
        "store_pct_1_star": round(snapshot["stars_1"] / snapshot["ratings"] * 100, 1) if snapshot else None,
        "date_from": df["review_date"].min() if n else None,
        "date_to": df["review_date"].max() if n else None,
    }


def monthly_trend(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["month", "reviews", "avg_rating", "pct_1_star", "pct_replied"])
    g = df.groupby("month")
    return pd.DataFrame({
        "reviews": g.size(),
        "avg_rating": g["rating"].mean().round(2),
        "pct_1_star": g["rating"].apply(lambda s: (s == 1).mean() * 100).round(1),
        "pct_replied": g["has_reply"].mean().mul(100).round(1),
    }).reset_index()


def version_table(df: pd.DataFrame, min_reviews: int = 30) -> pd.DataFrame:
    """Rating by major.minor app version, oldest first. Small versions are flagged, not hidden."""
    d = df[df["review_version"].notna()].copy()
    if d.empty:
        return pd.DataFrame(columns=["version", "reviews", "avg_rating", "pct_1_star", "first_review", "enough_data"])
    d["version"] = d["review_version"].astype(str).str.extract(r"^(\d+\.\d+)")[0]
    d = d[d["version"].notna()]
    g = d.groupby("version")
    out = pd.DataFrame({
        "reviews": g.size(),
        "avg_rating": g["rating"].mean().round(2),
        "pct_1_star": g["rating"].apply(lambda s: (s == 1).mean() * 100).round(1),
        "first_review": g["review_date"].min(),
    }).reset_index()
    out["enough_data"] = out["reviews"] >= min_reviews
    key = out["version"].str.split(".", expand=True).astype(int)
    return out.assign(_a=key[0], _b=key[1]).sort_values(["_a", "_b"]).drop(columns=["_a", "_b"]).reset_index(drop=True)


def reply_health(df: pd.DataFrame) -> dict:
    unhappy = df[df["rating"] <= UNHAPPY_MAX]
    replied = df[df["has_reply"]]
    delay = (replied["reply_date"] - replied["review_date"]).dt.total_seconds() / 86400
    # edited after reply: Google shows the latest edit date, so review_date > reply_date
    edited = replied[replied["review_date"] > replied["reply_date"]]
    return {
        "unhappy_reviews": len(unhappy),
        "unhappy_replied": int(unhappy["has_reply"].sum()),
        "reply_rate_unhappy": round(unhappy["has_reply"].mean() * 100, 1) if len(unhappy) else None,
        "median_reply_days": round(delay[delay >= 0].median(), 1) if len(replied) else None,
        "edited_after_reply": len(edited),
        "edited_now_4_5": int((edited["rating"] >= SATISFIED_MIN).sum()),
    }


# ---------------------------------------------------------------------------
# Issue ranking
# ---------------------------------------------------------------------------
def _uplift(rows: pd.DataFrame, total_reviews: int) -> float:
    unhappy = rows[rows["rating"] <= UNHAPPY_MAX]
    return float((UPLIFT_TARGET - unhappy["rating"]).sum() / total_reviews) if total_reviews else 0.0


MIN_TREND_COMPLAINTS = 20   # both comparison windows need this many complaints for a trend to mean anything


def issue_summary(df: pd.DataFrame, trend_days: int = 90) -> pd.DataFrame:
    """One row per issue category, ranked by rating impact. Safety is pinned to the top.

    share_before / share_last_period compare the last `trend_days` with the rest of the
    period; they are left empty when either window has too few complaints."""
    total = len(df)
    complaints = df[df["is_complaint"] & df["is_substantive"]]
    n_comp = len(complaints)
    cut = df["review_date"].max() - pd.Timedelta(days=trend_days) if total else None
    if cut is not None:
        n_recent = int((complaints["review_date"] > cut).sum())
        if min(n_recent, n_comp - n_recent) < MIN_TREND_COMPLAINTS:
            cut = None
    rows = []
    for cat in config.CATEGORIES:
        cid = cat["id"]
        main = complaints[complaints["primary_category"] == cid]
        mentions = complaints[complaints["categories"].fillna("").str.split("|").map(lambda c: cid in c)]
        if main.empty and mentions.empty:
            continue
        recent_share = prev_share = None
        if cut is not None:
            rc, pc = complaints[complaints["review_date"] > cut], complaints[complaints["review_date"] <= cut]
            recent_share = (rc["primary_category"] == cid).mean() * 100 if len(rc) else None
            prev_share = (pc["primary_category"] == cid).mean() * 100 if len(pc) else None
        rows.append({
            "category": cid,
            "issue": cat["name"],
            "fixable_by": cat["fixable_by"],
            "reviews": len(main),
            "mentions": len(mentions),
            "pct_of_complaints": round(len(main) / n_comp * 100, 1) if n_comp else 0.0,
            "avg_rating": round(main["rating"].mean(), 2) if len(main) else None,
            "pct_1_star": round((main["rating"] == 1).mean() * 100, 1) if len(main) else None,
            "thumbs_up": int(main["thumbs_up"].sum()),
            "uplift": round(_uplift(main, total), 3),
            "share_last_period": round(recent_share, 1) if recent_share is not None else None,
            "share_before": round(prev_share, 1) if prev_share is not None else None,
            "llm_labelled": int((main["label_source"] == "llm").sum()),
            "safety_flags": int(complaints.loc[mentions.index, "is_safety"].sum()) if len(mentions) else 0,
        })
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["pinned"] = out["category"] == "safety"
    out = out.sort_values(["pinned", "uplift", "reviews"], ascending=[False, False, False])
    return out.drop(columns="pinned").reset_index(drop=True)


def top_fixes(summary: pd.DataFrame, n: int = 3, exclude: set[str] | None = None) -> pd.DataFrame:
    """Highest rating impact among issues MoveInSync can act on.

    Safety is handled separately. `exclude` removes issues already being fixed, so the
    list always shows what to work on next."""
    if summary.empty:
        return summary
    keep = (summary["fixable_by"] != "Review") & ~summary["category"].isin(exclude or set())
    return summary[keep].head(n).reset_index(drop=True)


def fix_progress(df: pd.DataFrame, category: str, since, window_days: int = 90) -> dict:
    """Did complaints about an issue drop after a fix shipped?

    Compares complaints per 100 written reviews in the `window_days` before `since`
    with the period after it. Reviews lag behind fixes, so small samples are reported
    as 'too early' rather than as a verdict."""
    since = pd.Timestamp(since)
    before = df[(df["review_date"] < since) & (df["review_date"] >= since - pd.Timedelta(days=window_days))]
    after = df[df["review_date"] >= since]

    def rate(d):
        return (d["is_complaint"] & (d["primary_category"] == category)).sum() / len(d) * 100 if len(d) else None

    rb, ra = rate(before), rate(after)
    n_after = int((after["is_complaint"] & (after["primary_category"] == category)).sum())
    if len(after) < 50:
        verdict = "Too early: fewer than 50 reviews since the fix"
    elif rb is None or rb == 0:
        verdict = "No baseline to compare"
    elif ra <= rb * 0.7:
        verdict = "Improving"
    elif ra >= rb * 1.3:
        verdict = "Getting worse"
    else:
        verdict = "No clear change yet"
    return {"per_100_before": round(rb, 1) if rb is not None else None,
            "per_100_after": round(ra, 1) if ra is not None else None,
            "reviews_after": len(after), "complaints_after": n_after, "verdict": verdict}


def uncategorised(df: pd.DataFrame) -> dict:
    complaints = df[df["is_complaint"]]
    sub = complaints[complaints["is_substantive"]]
    return {
        "complaints": len(complaints),
        "low_info": int((~complaints["is_substantive"]).sum()),
        "unclassified": int((sub["primary_category"] == config.OTHER).sum()),
        "pct_unclassified": round((sub["primary_category"] == config.OTHER).mean() * 100, 1) if len(sub) else None,
        "by_rules": int((sub["label_source"] == "rule").sum()),
        "by_llm": int((sub["label_source"] == "llm").sum()),
    }


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------
def examples(df: pd.DataFrame, category: str, n: int = 5, min_words: int = 6) -> pd.DataFrame:
    """Representative complaints: lowest rating first, then most thumbs-up, then most recent."""
    rows = df[df["is_complaint"] & (df["primary_category"] == category)].copy()
    words = rows["review_text"].fillna("").str.split().str.len()
    rows = rows[words >= min_words]
    rows = rows.sort_values(["rating", "thumbs_up", "review_date"], ascending=[True, False, False])
    cols = ["review_date", "rating", "review_version", "thumbs_up", "review_text",
            "label_source", "matched_keywords", "llm_reason", "is_safety"]
    return rows[[c for c in cols if c in rows.columns]].head(n).reset_index(drop=True)


def safety_reviews(df: pd.DataFrame) -> pd.DataFrame:
    rows = df[df["is_complaint"] & df["is_safety"].astype(bool)]
    return rows.sort_values("review_date", ascending=False)[
        ["review_date", "rating", "review_text", "label_source", "matched_keywords"]
    ].reset_index(drop=True)


def compare_apps(df: pd.DataFrame, snapshots: pd.DataFrame | None, start=None) -> pd.DataFrame:
    rows = []
    for app_id, meta in config.APPS.items():
        d = filter_period(df, app_id, start)
        snap = latest_snapshot(snapshots, app_id)
        k = kpis(d, snap)
        rows.append({"app": meta["name"], "reviews": k["reviews"], "avg_rating": k["avg_rating"],
                     "pct_1_star": k["pct_1_star"], "reply_rate_unhappy": k["reply_rate_unhappy"],
                     "store_score": k["store_score"], "store_ratings": k["store_ratings"]})
    return pd.DataFrame(rows)


def latest_snapshot(snapshots: pd.DataFrame | None, app_id: str) -> dict | None:
    if snapshots is None or snapshots.empty:
        return None
    s = snapshots[snapshots["app_id"] == app_id]
    return None if s.empty else s.iloc[-1].to_dict()


# ---------------------------------------------------------------------------
# Plain-English summary (top of the dashboard)
# ---------------------------------------------------------------------------
LOW_DATA_REVIEWS = 30
REPLY_GOOD = 50


def plain_summary(df: pd.DataFrame, snapshot: dict | None = None, exclude: set[str] | None = None) -> list[str]:
    """Three or four short sentences a non-technical reader can act on. Every number comes from df."""
    k = kpis(df, snapshot)
    if k["reviews"] == 0:
        return ["No written reviews in this period. Pick a longer period."]
    out = []
    if k["reviews"] < LOW_DATA_REVIEWS:
        out.append(f"Only {k['reviews']} written reviews in this period, so treat everything below as anecdotes.")
    if k["store_score"]:
        out.append(f"The store rating ({k['store_score']:.2f}★) looks healthy, but people who write reviews average "
                   f"{k['avg_rating']:.2f}★, and {k['pct_1_star']:.0f}% of them give 1★. Those written reviews are "
                   f"what other users read.")
    else:
        out.append(f"People who write reviews average {k['avg_rating']:.2f}★; {k['pct_1_star']:.0f}% give 1★.")

    summary = issue_summary(df)
    top = top_fixes(summary, n=1, exclude=exclude)
    if not top.empty:
        t = top.iloc[0]
        sentence = (f"The biggest fixable cause is {t['issue']} ({t['pct_of_complaints']:.0f}% of complaints, "
                    f"{'an app' if t['fixable_by'] == 'App' else 'an operations'} fix)")
        bd = sub_issue_breakdown(df, t["category"])
        specific = bd[bd["actionable"]] if not bd.empty else bd
        if not specific.empty:
            s = specific.iloc[0]
            sentence += f", mostly \"{s['problem']}\" ({s['share']:.0f}% of those)"
        out.append(sentence + ". Start there.")

        # rising issues are reported by weekly_status(), shown just above this summary

    rh = reply_health(df)
    if rh["reply_rate_unhappy"] is not None and rh["reply_rate_unhappy"] < REPLY_GOOD:
        out.append(f"Only {rh['reply_rate_unhappy']:.0f}% of 1–2★ reviews get a reply. Restarting replies is the "
                   f"cheapest win: it needs no code.")
    return out


# ---------------------------------------------------------------------------
# Uncertainty: "plausible range" for small samples
# ---------------------------------------------------------------------------
def share_range(hits: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    """Plausible range (95%, Wilson method) for a share like '1★ share', in percent.

    With 10 reviews, 3 one-stars could easily be anything from ~11% to ~60%; with 1,000
    reviews the range is tight. Used to grey out or caveat small samples."""
    if n == 0:
        return None, None
    p = hits / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return round(max(0.0, centre - half) * 100, 1), round(min(1.0, centre + half) * 100, 1)


def mean_range(values: pd.Series, z: float = 1.96) -> tuple[float | None, float | None]:
    """Plausible range (95%) for an average star rating."""
    n = len(values)
    if n < 2:
        return None, None
    half = z * values.std(ddof=1) / n ** 0.5
    return round(max(1.0, values.mean() - half), 2), round(min(5.0, values.mean() + half), 2)


def monthly_ranges(df: pd.DataFrame) -> pd.DataFrame:
    """monthly_trend plus plausible ranges for the average rating."""
    trend = monthly_trend(df)
    if trend.empty:
        return trend.assign(avg_lo=[], avg_hi=[])
    ranges = df.groupby("month")["rating"].apply(mean_range)
    trend["avg_lo"] = trend["month"].map(lambda m: ranges[m][0])
    trend["avg_hi"] = trend["month"].map(lambda m: ranges[m][1])
    return trend


def version_ranges(df: pd.DataFrame, min_reviews: int = 30) -> pd.DataFrame:
    """version_table plus plausible ranges for each version's 1★ share."""
    vt = version_table(df, min_reviews)
    if vt.empty:
        return vt.assign(pct_1_lo=[], pct_1_hi=[])
    lo_hi = [share_range(round(p / 100 * n), n) for p, n in zip(vt["pct_1_star"], vt["reviews"])]
    vt["pct_1_lo"] = [x[0] for x in lo_hi]
    vt["pct_1_hi"] = [x[1] for x in lo_hi]
    return vt


# ---------------------------------------------------------------------------
# Weekly status: OK / WATCH / ALERT, with the reasons in words
# ---------------------------------------------------------------------------
STATUS_RULES = {
    "alert_1star_jump": 8,      # 1★ share in last 30 days up this many points vs the 90 days before → ALERT
    "watch_1star_jump": 4,      # … up this many points → WATCH
    "min_recent_reviews": 40,   # below this, the 30-day comparison is skipped (too noisy)
    "watch_issue_rise": 5,      # an issue's share of complaints up this many points (last 90 days vs before)
    "watch_reply_rate": 20,     # reply rate to 1–2★ reviews in the last 30 days below this %
    "min_unhappy_reviews": 5,   # …only checked when there are at least this many 1–2★ reviews
    "watch_release_jump": 5,    # newest version's 1★ share this many points above the previous version
}


def weekly_status(app_df: pd.DataFrame) -> dict:
    """Status for one app across all its data, anchored on the newest review.

    Simple, published rules (STATUS_RULES) so anyone can check why the status is what it is."""
    R = STATUS_RULES
    if app_df.empty:
        return {"status": "OK", "reasons": ["No reviews yet."], "checks": {}}
    end = app_df["review_date"].max()
    last30 = app_df[app_df["review_date"] > end - pd.Timedelta(days=30)]
    prev90 = app_df[(app_df["review_date"] <= end - pd.Timedelta(days=30))
                    & (app_df["review_date"] > end - pd.Timedelta(days=120))]
    alerts, watches, fine = [], [], []
    short = []   # 3–6 word versions of each reason, for one-line headlines

    if len(last30) >= R["min_recent_reviews"] and len(prev90):
        now, before = (last30["rating"] == 1).mean() * 100, (prev90["rating"] == 1).mean() * 100
        jump = now - before
        line = f"1★ share in the last 30 days is {now:.0f}% vs {before:.0f}% in the 90 days before"
        if jump >= R["alert_1star_jump"]:
            alerts.append(line + ".")
            short.insert(0, "1★ reviews jumped this month")
        elif jump >= R["watch_1star_jump"]:
            watches.append(line + ".")
            short.append("1★ reviews are creeping up")
        else:
            fine.append(line + " (no real change).")

    year = app_df[app_df["review_date"] > end - pd.Timedelta(days=365)]
    summary = issue_summary(year)
    if not summary.empty:
        rising = summary[summary["share_before"].notna() & summary["share_last_period"].notna()].copy()
        rising["change"] = rising["share_last_period"] - rising["share_before"]
        for r in rising[rising["change"] >= R["watch_issue_rise"]].itertuples():
            watches.append(f"{r.issue} complaints are rising: {r.share_before:.0f}% → {r.share_last_period:.0f}% "
                           f"of complaints in the last 90 days.")
            short.append(f"{r.issue.split(',')[0].split(' and ')[0].lower()} complaints are rising")

    unhappy = last30[last30["rating"] <= UNHAPPY_MAX]
    if len(unhappy) >= R["min_unhappy_reviews"]:
        rate = unhappy["has_reply"].mean() * 100
        if rate < R["watch_reply_rate"]:
            watches.append(f"Only {rate:.0f}% of 1–2★ reviews in the last 30 days got a reply "
                           f"({int(unhappy['has_reply'].sum())} of {len(unhappy)}).")
            short.append("unhappy reviewers aren't getting replies")

    vt = version_ranges(year)
    vt = vt[vt["enough_data"]]
    if len(vt) >= 2:
        newest, previous = vt.iloc[-1], vt.iloc[-2]
        jump = newest["pct_1_star"] - previous["pct_1_star"]
        if jump >= R["watch_release_jump"]:
            clear = newest["pct_1_lo"] > previous["pct_1_hi"]
            watches.append(f"The newest version (v{newest['version']}) has {newest['pct_1_star']:.0f}% 1★ reviews vs "
                           f"{previous['pct_1_star']:.0f}% on v{previous['version']}"
                           + (". The difference is clear, not chance." if clear else
                              f" ({newest['reviews']} reviews so far, so it could still be chance; keep watching)."))
            short.append(f"v{newest['version']} may be worse")

    status = "ALERT" if alerts else "WATCH" if watches else "OK"
    return {"status": status, "reasons": alerts + watches or fine or ["Nothing unusual."],
            "short": short or ["nothing unusual"], "as_of": end, "reviews_last_30": len(last30)}
