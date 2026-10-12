"""The labelled table is rebuilt whenever data or rules change, and read back identically."""

import pandas as pd

from src import analysis, pipeline

EMPTY_LLM = pd.DataFrame(columns=["review_id", "llm_category", "llm_secondary", "llm_is_safety",
                                  "llm_reason", "llm_model", "labelled_at"])


def small_reviews():
    return pd.DataFrame({
        "app_id": ["com.moveinsync.ets"] * 3, "review_id": ["a", "b", "c"],
        "review_text": ["OTP never arrives", "good", "Cab is always late in the evening"],
        "rating": [1, 5, 2], "review_date": ["2026-09-01 10:00:00", "2026-09-02 10:00:00", "2026-09-03 10:00:00"],
        "review_version": ["12.10.1", None, "12.9"], "thumbs_up": [0, 0, 3],
        "reply_text": [None, None, "Sorry"], "reply_date": [None, None, "2026-09-04 10:00:00"],
        "has_reply": [False, False, True], "fetched_lang": ["en"] * 3,
    })


def test_rebuilds_when_inputs_change_and_round_trips(tmp_path, monkeypatch):
    rules = tmp_path / "rules.py"
    rules.write_text("v1")
    monkeypatch.setattr(pipeline, "LABELLED_CSV", tmp_path / "labelled.csv")
    monkeypatch.setattr(pipeline, "FINGERPRINT", tmp_path / "fp.json")
    monkeypatch.setattr(pipeline, "INPUTS", [rules])
    monkeypatch.setattr(pipeline, "load_reviews", small_reviews)
    original_prepare = analysis.prepare
    monkeypatch.setattr(analysis, "prepare", lambda df: original_prepare(df, EMPTY_LLM))  # no real LLM cache

    assert not pipeline.is_fresh()
    built = pipeline.build_labelled()
    assert pipeline.is_fresh()

    loaded = pipeline.load_labelled()
    assert list(loaded["primary_category"]) == list(built["primary_category"])
    assert loaded["has_reply"].dtype == bool and loaded["review_date"].dtype.kind == "M"
    assert loaded.loc[loaded["review_id"] == "c", "review_version"].iloc[0] == "12.9"  # stays text

    rules.write_text("v2")
    assert not pipeline.is_fresh()


def test_public_demo_switches_llm_off(monkeypatch):
    monkeypatch.setattr(pipeline.llm_assist, "is_available", lambda: True)
    monkeypatch.delenv("DISABLE_LLM", raising=False)
    monkeypatch.delenv("PUBLIC_DEMO", raising=False)
    assert pipeline.llm_allowed()
    monkeypatch.setenv("PUBLIC_DEMO", "1")
    assert pipeline.public_demo() and not pipeline.llm_allowed()
