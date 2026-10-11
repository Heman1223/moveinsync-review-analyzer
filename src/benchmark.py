"""Benchmark: how MoveInSync compares with similar apps, using public Play Store data only.

For every app in config.BENCHMARK_APPS (MoveInSync included, measured the same way):
  - store numbers from the listing: rating, number of ratings, written reviews, installs
  - from its newest N written reviews: average stars, 1★ share, how often 1–2★ reviews get a
    reply, and the most common complaint themes (keyword rules only; no LLM)

Only aggregates are saved (data/benchmark.csv); no review text, no reviewer data.
Each run appends one row per app, so the history builds up week by week.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pandas as pd
from google_play_scraper import Sort, app as gp_app, reviews as gp_reviews

from src import config
from src.classifier import category_name, classify_text
from src.collector import _with_retries, normalize_review

SPECIAL = {config.OTHER, config.LOW_INFO, config.NO_TEXT}


def _installs_floor(text) -> int | None:
    """'1,000,000+' -> 1000000 (the Play Store only shows a lower bound)."""
    try:
        return int(str(text).replace(",", "").replace("+", ""))
    except ValueError:
        return None


def _newest_reviews(app_id: str, n: int, fetch_fn, pause: float) -> list[dict]:
    rows, token = [], None
    while len(rows) < n:
        batch, token = _with_retries(fetch_fn, app_id, lang="en", country=config.COUNTRY, sort=Sort.NEWEST,
                                     count=min(config.BATCH_SIZE, n - len(rows)), continuation_token=token)
        rows += [r for r in (normalize_review(x, app_id, "en") for x in batch) if r]
        if not batch or token is None or getattr(token, "token", None) is None:
            break
        time.sleep(pause)
    return rows[:n]


def top_themes(texts_and_ratings: list[tuple[str, int]], k: int = 3) -> list[tuple[str, float]]:
    """Most common complaint themes among 1–3★ reviews, as (theme name, % of those complaints)."""
    cats = [classify_text(t).primary for t, r in texts_and_ratings if r <= config.COMPLAINT_MAX_RATING]
    cats = [c for c in cats if c not in SPECIAL]
    if not cats:
        return []
    counts = pd.Series(cats).value_counts()
    return [(category_name(c), round(v / len(cats) * 100)) for c, v in counts.head(k).items()]


def measure_app(app_id: str, meta: dict, n: int, fetch_app=gp_app, fetch_reviews=gp_reviews,
                pause: float = config.PAUSE_SECONDS) -> dict:
    info = _with_retries(fetch_app, app_id, lang="en", country=config.COUNTRY)
    revs = pd.DataFrame(_newest_reviews(app_id, n, fetch_reviews, pause))
    ratings = info.get("ratings") or 0
    row = {
        "app_id": app_id, "name": meta["name"], "group": meta["group"],
        "store_score": round(info.get("score") or 0, 2) or None,
        "store_ratings": ratings,
        "written_reviews_total": info.get("reviews"),
        "installs": info.get("installs"),
        "pct_ratings_with_text": round(info["reviews"] / ratings * 100, 1) if ratings and info.get("reviews") else None,
        "ratings_per_100_installs": (round(ratings / _installs_floor(info.get("installs")) * 100, 1)
                                     if _installs_floor(info.get("installs")) else None),
        "sample_n": len(revs),
    }
    if revs.empty:
        return row | {"written_avg": None, "pct_1_star": None, "reply_rate_unhappy": None,
                      "sample_from": None, "sample_to": None, "top_complaints": ""}
    unhappy = revs[revs["rating"] <= 2]
    themes = top_themes(list(zip(revs["review_text"], revs["rating"])))
    return row | {
        "written_avg": round(revs["rating"].mean(), 2),
        "pct_1_star": round((revs["rating"] == 1).mean() * 100, 1),
        "reply_rate_unhappy": round(unhappy["has_reply"].mean() * 100, 1) if len(unhappy) else None,
        "sample_from": revs["review_date"].min(), "sample_to": revs["review_date"].max(),
        "top_complaints": "; ".join(f"{name} {pct}%" for name, pct in themes),
    }


def run(n: int = config.BENCHMARK_SAMPLE, apps: dict | None = None, log=print, **fetchers) -> pd.DataFrame:
    """Measure every app and append to data/benchmark.csv. One failing app doesn't stop the rest."""
    apps = apps or config.BENCHMARK_APPS
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for app_id, meta in apps.items():
        log(f"Benchmark: {meta['name']}…")
        try:
            rows.append({"fetched_at": fetched_at, **measure_app(app_id, meta, n, **fetchers), "error": None})
        except Exception as exc:
            rows.append({"fetched_at": fetched_at, "app_id": app_id, "name": meta["name"], "group": meta["group"],
                         "error": f"{type(exc).__name__}: {exc}"})
            log(f"  failed: {type(exc).__name__}")
    new = pd.DataFrame(rows)
    path = config.BENCHMARK_CSV
    out = pd.concat([pd.read_csv(path), new], ignore_index=True) if path.exists() else new
    out.to_csv(path, index=False, encoding="utf-8")
    return new


def latest(path=None) -> pd.DataFrame:
    """Most recent successful measurement per app."""
    path = path or config.BENCHMARK_CSV
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    df = df[df["error"].isna()] if "error" in df else df
    return df.sort_values("fetched_at").groupby("app_id").tail(1).reset_index(drop=True)


def headline(df: pd.DataFrame) -> list[str]:
    """Plain-English takeaways. Every number comes from df."""
    if df.empty or "com.moveinsync.ets" not in set(df["app_id"]):
        return []
    mis = df[df["app_id"] == "com.moveinsync.ets"].iloc[0]
    others = df[df["app_id"] != mis["app_id"]]
    peers = others[others["group"] == "Employee transport"]
    refs = others[others["group"] == "Ride-hailing (reference)"].sort_values("store_score", ascending=False)
    rival = others[others["name"] == "Routematic"]
    out = []

    if len(peers):
        rank = int((peers["store_score"] > mis["store_score"]).sum()) + 1
        out.append(f"Store rating: MoveInSync ({mis['store_score']:.2f}★) is #{rank} of {len(peers) + 1} "
                   f"employee-transport apps (their average: {peers['store_score'].mean():.2f}★).")
    if len(refs):
        best = refs.iloc[0]
        diff = best["store_score"] - mis["store_score"]
        out.append(f"The bar above it is consumer ride apps: {best['name']} {best['store_score']:.2f}★"
                   + (f", only {diff:.2f}★ higher." if diff > 0 else "; MoveInSync is already level or above."))

    if pd.notna(mis.get("written_avg")):
        compare = pd.concat([rival, refs])
        compare = compare[compare["written_avg"].notna()]
        if len(compare):
            parts = ", ".join(f"{r['name']} {r['written_avg']:.2f}★" for _, r in compare.iterrows())
            gaps = (df["store_score"] - df["written_avg"]).dropna()
            below = int((gaps > 0).sum())
            out.append(f"Written reviews: MoveInSync's newest average {mis['written_avg']:.2f}★ ({parts}). "
                       f"For {below} of {len(gaps)} apps the written reviews sit below the store rating (typically by "
                       f"{gaps.median():.1f}★), so that gap is normal, not a MoveInSync-only problem.")

    if pd.notna(mis.get("reply_rate_unhappy")):
        if len(rival) and pd.notna(rival.iloc[0].get("reply_rate_unhappy")):
            out.append(f"Replies: Routematic answers {rival.iloc[0]['reply_rate_unhappy']:.0f}% of its recent 1–2★ "
                       f"reviews; MoveInSync answers {mis['reply_rate_unhappy']:.0f}%. This is the clearest gap with "
                       f"its direct competitor, and it needs no code to close.")
        else:
            out.append(f"Replies: MoveInSync answers {mis['reply_rate_unhappy']:.0f}% of recent 1–2★ reviews.")
    return out
