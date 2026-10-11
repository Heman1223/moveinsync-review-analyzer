"""The weekly digest is built from saved data only and covers the essentials."""

import pandas as pd

from src import analysis, digest

EMPTY_LLM = pd.DataFrame(columns=["review_id", "llm_category", "llm_secondary", "llm_is_safety",
                                  "llm_reason", "llm_model", "labelled_at"])


def make(rows):
    df = pd.DataFrame(rows, columns=["review_id", "review_text", "rating", "review_date", "has_reply"])
    df["app_id"] = digest.PRIMARY_APP
    df["review_version"] = None
    df["thumbs_up"] = 0
    df["reply_text"] = None
    df["reply_date"] = None
    df["fetched_lang"] = "en"
    return analysis.prepare(df, EMPTY_LLM)


def test_digest_has_status_numbers_fixes_and_quotes():
    rows = [(f"o{i}", "Very useful for daily office commute", 5, f"2026-08-{1 + i % 28:02d}", False) for i in range(60)]
    rows += [(f"n{i}", "OTP never arrives so I cannot log in at all", 1, "2026-10-08", False) for i in range(5)]
    snaps = pd.DataFrame([
        {"snapshot_time": "2026-10-01 00:00:00", "app_id": digest.PRIMARY_APP, "score": 4.60, "ratings": 1000},
        {"snapshot_time": "2026-10-09 00:00:00", "app_id": digest.PRIMARY_APP, "score": 4.62, "ratings": 1050}])
    text = digest.build(make(rows), snaps)
    assert "## Status:" in text
    assert "| New written reviews | 5 |" in text
    assert "+0.020★ and +50 ratings" in text
    assert "Login, OTP and session" in text
    assert "In their words" in text and "OTP never arrives" in text


def test_store_change_without_history():
    snaps = pd.DataFrame([{"snapshot_time": "2026-10-09 00:00:00", "app_id": "x", "score": 4.5, "ratings": 10}])
    assert "will show once" in digest.store_change(snaps, "x")
    assert "no snapshot" in digest.store_change(None, "x")
