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

import pandas as pd

from src import config
from src.classifier import category_name, classify_df, fixable_by

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
    return df


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


def issue_summary(df: pd.DataFrame, trend_days: int = 90) -> pd.DataFrame:
    """One row per issue category, ranked by rating impact. Safety is pinned to the top."""
    total = len(df)
    complaints = df[df["is_complaint"] & df["is_substantive"]]
    n_comp = len(complaints)
    cut = df["review_date"].max() - pd.Timedelta(days=trend_days) if total else None
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


def top_fixes(summary: pd.DataFrame, n: int = 3) -> pd.DataFrame:
    """Highest rating impact among issues MoveInSync can act on (safety is handled separately)."""
    if summary.empty:
        return summary
    return summary[summary["fixable_by"] != "Review"].head(n).reset_index(drop=True)


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
