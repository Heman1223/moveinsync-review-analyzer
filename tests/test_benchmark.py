"""Offline tests for the benchmark (fake store data, no network)."""

from datetime import datetime
from types import SimpleNamespace

import pandas as pd

from src import benchmark, config


def fake_app(app_id, **kw):
    return {"score": 4.5, "ratings": 1000, "reviews": 200, "installs": "10,000+"}


def fake_reviews_factory(rows):
    def fetch(app_id, **kw):
        return rows, SimpleNamespace(token=None)
    return fetch


def review(i, score, text="The cab is always late", reply=None):
    return {"reviewId": f"r{i}", "score": score, "at": datetime(2026, 10, 1), "content": text,
            "replyContent": reply, "repliedAt": datetime(2026, 10, 2) if reply else None}


def test_measure_app_computes_like_for_like_metrics():
    rows = [review(1, 1, reply="Sorry"), review(2, 2), review(3, 5, "great"), review(4, 4, "good app")]
    m = benchmark.measure_app("x", {"name": "X", "group": "Employee transport"}, n=10,
                              fetch_app=fake_app, fetch_reviews=fake_reviews_factory(rows), pause=0)
    assert m["written_avg"] == 3.0
    assert m["pct_1_star"] == 25.0
    assert m["reply_rate_unhappy"] == 50.0          # 1 of the two 1–2★ reviews has a reply
    assert m["pct_ratings_with_text"] == 20.0       # 200 written of 1000 ratings
    assert m["ratings_per_100_installs"] == 10.0    # 1000 / 10,000
    assert m["top_complaints"].startswith("Cab late or no-show")
    assert "review_text" not in m                   # only aggregates are kept


def test_run_survives_one_failing_app(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "BENCHMARK_CSV", tmp_path / "b.csv")

    def flaky_app(app_id, **kw):
        if app_id == "bad":
            raise ConnectionError("down")
        return fake_app(app_id)

    monkeypatch.setattr(config, "MAX_RETRIES", 1)
    apps = {"good": {"name": "Good", "group": "Employee transport"},
            "bad": {"name": "Bad", "group": "Employee transport"}}
    new = benchmark.run(n=5, apps=apps, log=lambda m: None, fetch_app=flaky_app,
                        fetch_reviews=fake_reviews_factory([review(1, 1)]), pause=0)
    assert new.set_index("app_id").loc["bad", "error"].startswith("ConnectionError")
    latest = benchmark.latest(tmp_path / "b.csv")
    assert list(latest["app_id"]) == ["good"]       # failures never replace good data


def test_headline_states_rank_bar_and_reply_gap():
    df = pd.DataFrame([
        {"app_id": "com.moveinsync.ets", "name": "MoveInSync", "group": "MoveInSync", "store_score": 4.64,
         "written_avg": 3.78, "reply_rate_unhappy": 1.0},
        {"app_id": "r", "name": "Routematic", "group": "Employee transport", "store_score": 4.34,
         "written_avg": 3.56, "reply_rate_unhappy": 100.0},
        {"app_id": "e", "name": "eFmFm", "group": "Employee transport", "store_score": 2.81,
         "written_avg": 2.62, "reply_rate_unhappy": 2.0},
        {"app_id": "u", "name": "Uber", "group": "Ride-hailing (reference)", "store_score": 4.73,
         "written_avg": 3.73, "reply_rate_unhappy": 0.0},
    ])
    text = " ".join(benchmark.headline(df))
    assert "#1 of 3" in text and "For 4 of 4 apps" in text
    assert "Uber 4.73★, only 0.09★ higher" in text
    assert "Routematic answers 100%" in text and "MoveInSync answers 1%" in text
