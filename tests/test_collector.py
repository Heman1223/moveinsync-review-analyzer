"""Offline tests for the collector. All review data here is synthetic."""

from datetime import datetime
from types import SimpleNamespace

import pandas as pd

from src import config
from src.collector import fetch_reviews, merge_reviews, normalize_review


def raw(review_id, score=1, at=datetime(2026, 10, 1), text="Cab was late", **extra):
    return {"reviewId": review_id, "score": score, "at": at, "content": text,
            "userName": "Someone", "userImage": "http://img", **extra}


def fake_pages(pages):
    """Mimic gp_reviews: returns one page per call, then a token with token=None."""
    calls = {"n": 0}

    def _fetch(app_id, **kwargs):
        i = calls["n"]
        calls["n"] += 1
        last = i == len(pages) - 1
        return pages[i], SimpleNamespace(token=None if last else f"t{i}")

    _fetch.calls = calls
    return _fetch


# --- normalize -------------------------------------------------------------
def test_normalize_drops_personal_fields_and_handles_missing_optionals():
    row = normalize_review(raw("r1"), "app", "en")
    assert "userName" not in row and "userImage" not in row
    assert row["review_version"] is None
    assert row["reply_text"] is None and row["has_reply"] is False
    assert row["thumbs_up"] == 0
    assert row["review_date"] == "2026-10-01 00:00:00"


def test_normalize_keeps_reply_and_original_text():
    row = normalize_review(
        raw("r1", text="  Booking FAILED!! ", replyContent="Sorry, fixed", repliedAt=datetime(2026, 10, 2),
            reviewCreatedVersion="12.18.0", thumbsUpCount=7),
        "app", "en")
    assert row["review_text"] == "Booking FAILED!!"
    assert row["has_reply"] is True and row["reply_date"] == "2026-10-02 00:00:00"
    assert row["review_version"] == "12.18.0" and row["thumbs_up"] == 7


def test_normalize_rejects_malformed_records():
    assert normalize_review(raw(None), "app", "en") is None
    assert normalize_review(raw("r1", score=None), "app", "en") is None


def test_empty_text_is_kept_as_empty_string():
    assert normalize_review(raw("r1", text=None), "app", "en")["review_text"] == ""


# --- fetch / pagination ----------------------------------------------------
def test_full_fetch_reads_all_pages():
    fetch = fake_pages([[raw("a"), raw("b")], [raw("c")]])
    rows = fetch_reviews("app", "en", fetch_fn=fetch, pause=0)
    assert [r["review_id"] for r in rows] == ["a", "b", "c"]


def test_incremental_fetch_stops_at_older_reviews():
    pages = [[raw("new1", at=datetime(2026, 10, 9)), raw("new2", at=datetime(2026, 10, 8)),
              raw("old", at=datetime(2026, 9, 1))],
             [raw("older", at=datetime(2026, 8, 1))]]
    fetch = fake_pages(pages)
    rows = fetch_reviews("app", "en", since=datetime(2026, 10, 1), fetch_fn=fetch, pause=0)
    assert [r["review_id"] for r in rows] == ["new1", "new2"]
    assert fetch.calls["n"] == 1  # never requested the second page


def test_fetch_errors_propagate_so_caller_keeps_old_data(monkeypatch):
    monkeypatch.setattr(config, "MAX_RETRIES", 1)

    def broken(*a, **k):
        raise ConnectionError("network down")

    try:
        fetch_reviews("app", "en", fetch_fn=broken, pause=0)
        assert False, "expected an error"
    except ConnectionError:
        pass


# --- merge -----------------------------------------------------------------
def test_merge_deduplicates_and_keeps_latest_edit():
    existing = pd.DataFrame([normalize_review(raw("r1", score=1, at=datetime(2026, 9, 1)), "app", "en")])
    new = [
        normalize_review(raw("r1", score=4, at=datetime(2026, 10, 5), text="Edited: better now"), "app", "en"),
        normalize_review(raw("r1", score=4, at=datetime(2026, 10, 5), text="Edited: better now"), "app", "hi"),
        normalize_review(raw("r2"), "app", "en"),
    ]
    merged, stats = merge_reviews(existing, new)
    assert len(merged) == 2
    r1 = merged.set_index("review_id").loc["r1"]
    assert r1["rating"] == 4 and r1["review_text"] == "Edited: better now"
    assert stats["new_reviews"] == 1
    assert stats["duplicates_removed"] == 2


def test_merge_into_empty_store():
    merged, stats = merge_reviews(pd.DataFrame(columns=config.REVIEW_COLUMNS),
                                  [normalize_review(raw("r1"), "app", "en")])
    assert len(merged) == 1 and stats["new_reviews"] == 1
