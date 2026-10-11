"""Fetch public Google Play reviews and app-level rating snapshots.

Uses the unofficial `google-play-scraper` library (it calls the same endpoints the
Play Store website uses; it is not an official Google API).

Design rules:
- Never fabricate data. If a fetch fails, report it and keep the last good data.
- Incremental: later runs only fetch reviews newer than what we already have.
- No personal data: reviewer names and photos are dropped at collection time.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pandas as pd
from google_play_scraper import Sort, app as gp_app, reviews as gp_reviews

from src import config

# How far back past our newest stored review an incremental fetch keeps reading.
# Covers reviews that were edited (an edit moves a review to the top with a new date).
INCREMENTAL_OVERLAP = timedelta(days=2)


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------
def _fmt_date(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")


def _clean_text(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def normalize_review(raw: dict, app_id: str, lang: str) -> dict | None:
    """Convert one raw scraper record into our schema. Returns None if unusable."""
    review_id = raw.get("reviewId")
    rating = raw.get("score")
    if not review_id or rating not in (1, 2, 3, 4, 5):
        return None  # malformed record: skip rather than guess

    reply_text = _clean_text(raw.get("replyContent"))
    return {
        "app_id": app_id,
        "review_id": review_id,
        "review_text": _clean_text(raw.get("content")),
        "rating": int(rating),
        "review_date": _fmt_date(raw.get("at")),
        "review_version": raw.get("reviewCreatedVersion") or None,
        "thumbs_up": int(raw.get("thumbsUpCount") or 0),
        "reply_text": reply_text or None,
        "reply_date": _fmt_date(raw.get("repliedAt")),
        "has_reply": bool(reply_text),
        "fetched_lang": lang,
    }


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------
def _with_retries(fn, *args, **kwargs):
    """Call fn, retrying with increasing waits (2s, 4s, 8s...) on failure."""
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except Exception:
            if attempt == config.MAX_RETRIES:
                raise
            time.sleep(2 ** attempt)


def fetch_reviews(
    app_id: str,
    lang: str,
    since: datetime | None = None,
    fetch_fn=gp_reviews,
    pause: float = config.PAUSE_SECONDS,
) -> list[dict]:
    """Page through reviews newest-first.

    since=None  -> full history.
    since=date  -> stop once reviews are older than `since` (incremental refresh).
    Raises on network/source errors so the caller can keep the last good data.
    """
    rows: list[dict] = []
    token = None
    while True:
        batch, token = _with_retries(
            fetch_fn,
            app_id,
            lang=lang,
            country=config.COUNTRY,
            sort=Sort.NEWEST,
            count=config.BATCH_SIZE,
            continuation_token=token,
        )
        reached_old = False
        for raw in batch:
            if since is not None and raw.get("at") is not None and raw["at"] < since:
                reached_old = True
                break
            row = normalize_review(raw, app_id, lang)
            if row:
                rows.append(row)

        no_more_pages = not batch or token is None or getattr(token, "token", None) is None
        if reached_old or no_more_pages:
            return rows
        time.sleep(pause)


def fetch_snapshot(app_id: str, fetch_fn=gp_app) -> dict:
    """Store-level numbers shown on the listing (includes ratings without text)."""
    info = _with_retries(fetch_fn, app_id, lang="en", country=config.COUNTRY)
    hist = info.get("histogram") or [None] * 5
    return {
        "snapshot_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "app_id": app_id,
        "score": info.get("score"),
        "ratings": info.get("ratings"),
        "reviews": info.get("reviews"),
        "stars_1": hist[0],
        "stars_2": hist[1],
        "stars_3": hist[2],
        "stars_4": hist[3],
        "stars_5": hist[4],
        "current_version": info.get("version"),
        "installs": info.get("installs"),
    }


# ---------------------------------------------------------------------------
# Merging and storage
# ---------------------------------------------------------------------------
def merge_reviews(existing: pd.DataFrame, new_rows: list[dict]) -> tuple[pd.DataFrame, dict]:
    """Combine stored and newly fetched reviews, one row per review_id.

    If a review appears twice (edited review, or fetched under both languages),
    the copy with the latest review_date wins.
    """
    new = pd.DataFrame(new_rows, columns=config.REVIEW_COLUMNS)
    before_ids = set(existing["review_id"]) if not existing.empty else set()
    new_ids = set(new["review_id"])

    combined = pd.concat([existing, new], ignore_index=True)
    combined = (
        combined.sort_values("review_date", kind="stable")
        .drop_duplicates(subset="review_id", keep="last")
        .sort_values(["app_id", "review_date"], ascending=[True, False])
        .reset_index(drop=True)
    )
    stats = {
        "fetched_rows": len(new),
        "new_reviews": len(new_ids - before_ids),
        "duplicates_removed": len(existing) + len(new) - len(combined),
    }
    return combined[config.REVIEW_COLUMNS], stats


def load_reviews(path=config.REVIEWS_CSV) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=config.REVIEW_COLUMNS)
    return pd.read_csv(path, dtype={"review_version": "string", "review_id": "string"})


def _atomic_write_csv(df: pd.DataFrame, path) -> None:
    """Write to a temp file then swap it in, so a crash never leaves a half-written CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    df.to_csv(tmp, index=False, encoding="utf-8")
    tmp.replace(path)


def _append_csv(row_dicts: list[dict], path) -> None:
    if not row_dicts:
        return
    df = pd.DataFrame(row_dicts)
    if path.exists():
        df = pd.concat([pd.read_csv(path), df], ignore_index=True)
    _atomic_write_csv(df, path)


# ---------------------------------------------------------------------------
# One-call refresh used by the CLI and the dashboard button
# ---------------------------------------------------------------------------
def refresh(full: bool = False, apps: dict | None = None, log=print) -> dict:
    """Fetch new reviews and a rating snapshot for every configured app.

    Each app/language is fetched independently. If one fails, its partial results
    are discarded (a partial newest-first fetch would leave a silent gap) and the
    stored data for it is left untouched.
    """
    apps = apps or config.APPS
    existing = load_reviews()
    run_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    all_new: list[dict] = []
    log_rows, snapshots, errors = [], [], []

    for app_id, meta in apps.items():
        stored = existing[existing["app_id"] == app_id]
        since = None
        if not full and not stored.empty:
            since = pd.to_datetime(stored["review_date"]).max().to_pydatetime() - INCREMENTAL_OVERLAP

        for lang in config.LANGUAGES:
            mode = "full" if since is None else f"since {since:%Y-%m-%d}"
            log(f"Fetching {meta['name']} [{lang}] ({mode})...")
            try:
                rows = fetch_reviews(app_id, lang, since=since)
                all_new.extend(rows)
                log(f"  got {len(rows)} reviews")
                log_rows.append({"run_time": run_time, "app_id": app_id, "lang": lang,
                                 "mode": mode, "rows": len(rows), "error": None})
            except Exception as exc:  # network, rate limit, Google changed the page...
                msg = f"{type(exc).__name__}: {exc}"
                log(f"  FAILED ({msg}); keeping previously saved data for this app")
                errors.append(f"{meta['name']} [{lang}]: {msg}")
                log_rows.append({"run_time": run_time, "app_id": app_id, "lang": lang,
                                 "mode": mode, "rows": 0, "error": msg})

        try:
            snapshots.append(fetch_snapshot(app_id))
        except Exception as exc:
            errors.append(f"{meta['name']} snapshot: {type(exc).__name__}: {exc}")

    merged, stats = merge_reviews(existing, all_new)
    if all_new:
        _atomic_write_csv(merged, config.REVIEWS_CSV)
    _append_csv(snapshots, config.SNAPSHOTS_CSV)
    _append_csv(log_rows, config.FETCH_LOG_CSV)

    summary = {
        "run_time": run_time,
        "total_reviews_stored": len(merged),
        **stats,
        "per_app": merged.groupby("app_id").size().to_dict() if not merged.empty else {},
        "errors": errors,
    }
    return summary
