"""Offline tests for the LLM step. The model is replaced by a fake; no key or network needed."""

import json

import pandas as pd

from src import config, llm_assist
from src.classifier import classify_df


def reviews(rows):
    df = pd.DataFrame(rows, columns=["review_id", "review_text", "rating"])
    return classify_df(df)


def fake_model(answers):
    """Returns a generate(prompt, schema) that answers with a fixed label per review_id."""
    calls = []

    def generate(prompt, schema):
        calls.append(prompt)
        ids = [r["review_id"] for r in json.loads(prompt[prompt.index("["):])]
        return json.dumps([{"review_id": i, "category": answers.get(i, "other"), "secondary": "none",
                            "is_safety": False, "reason": "test"} for i in ids])

    generate.calls = calls
    return generate


def test_parse_labels_validates_output():
    raw = [
        {"review_id": "a", "category": "booking", "secondary": "booking", "is_safety": False, "reason": "x"},
        {"review_id": "b", "category": "made_up", "secondary": "none", "is_safety": False, "reason": "y"},
        {"review_id": "zzz", "category": "login", "secondary": "none", "is_safety": False, "reason": "z"},
        {"review_id": "a", "category": "login", "secondary": "none", "is_safety": False, "reason": "dup"},
    ]
    out = {r["review_id"]: r for r in llm_assist.parse_labels(raw, ["a", "b"], "m")}
    assert set(out) == {"a", "b"}                     # unknown id dropped, duplicate ignored
    assert out["a"]["llm_category"] == "booking"
    assert out["a"]["llm_secondary"] is None          # same as primary -> dropped
    assert out["b"]["llm_category"] == "other"        # invented category -> other


def test_only_unclassified_complaints_are_sent_and_cache_is_reused(tmp_path):
    df = reviews([
        ("r1", "The cab is always late", 1),                        # rules handle it
        ("r2", "Sab bekaar hai, kuch bhi theek se nahi hota yaar", 1),  # rules miss it
        ("r3", "Lovely people and a wonderful experience every day", 5),  # not a complaint
    ])
    path = tmp_path / "labels.csv"
    gen = fake_model({"r2": "stability"})

    first = llm_assist.label_unclassified(df, generate=gen, pause=0, path=path)
    assert first["to_label"] == 1 and first["labelled"] == 1
    assert '"r2"' in gen.calls[0] and '"r1"' not in gen.calls[0] and '"r3"' not in gen.calls[0]

    second = llm_assist.label_unclassified(df, generate=gen, pause=0, path=path)
    assert second["to_label"] == 0 and len(gen.calls) == 1   # cached: no new call


def test_apply_llm_labels_never_overrides_rules():
    df = reviews([("r1", "The cab is always late", 1),
                  ("r2", "Sab bekaar hai, kuch bhi theek se nahi hota yaar", 1),
                  ("r3", "Honestly this whole thing is a joke and a total waste", 2)])
    labels = pd.DataFrame(llm_assist.parse_labels([
        {"review_id": "r1", "category": "login", "secondary": "none", "is_safety": False, "reason": "x"},
        {"review_id": "r2", "category": "stability", "secondary": "tracking", "is_safety": False, "reason": "y"},
        {"review_id": "r3", "category": "other", "secondary": "none", "is_safety": False, "reason": "vague"},
    ], ["r1", "r2", "r3"], "m"))
    out = llm_assist.apply_llm_labels(df, labels).set_index("review_id")

    assert out.loc["r1", "primary_category"] == "cab_delay" and out.loc["r1", "label_source"] == "rule"
    assert out.loc["r2", "primary_category"] == "stability" and out.loc["r2", "label_source"] == "llm"
    assert out.loc["r2", "categories"] == "stability|tracking"
    assert out.loc["r3", "primary_category"] == config.OTHER     # LLM said vague: stays Other


def test_failed_batch_is_skipped_without_losing_data(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_assist.time, "sleep", lambda s: None)
    df = reviews([("r2", "Sab bekaar hai, kuch bhi theek se nahi hota yaar", 1)])

    def broken(prompt, schema):
        raise ConnectionError("network down")

    summary = llm_assist.label_unclassified(df, generate=broken, pause=0, path=tmp_path / "l.csv")
    assert summary["failed_batches"] == 1 and summary["labelled"] == 0


def test_score_keyword_measures_matches_and_precision():
    df = reviews([("a", "Seat belt popup again before the otp", 1),
                  ("b", "Waiting for the cab, otp never came", 1),
                  ("c", "The otp screen freezes", 2)])
    score = llm_assist.score_keyword("otp", "login", df)
    assert score["matches"] == 3
    assert 0 <= score["precision_vs_labels"] <= 1


def test_no_key_means_not_available(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(config, "ROOT", tmp_path)   # no .env there
    assert llm_assist.is_available() is False


def test_budget_guard_caps_requests_per_run(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LLM_BATCH_SIZE", 1)
    df = reviews([(f"r{i}", "Sab bekaar hai, kuch bhi theek se nahi hota yaar", 1) for i in range(5)])
    gen = fake_model({})
    summary = llm_assist.label_unclassified(df, generate=gen, pause=0, path=tmp_path / "l.csv", max_calls=2)
    assert len(gen.calls) == 2
    assert summary["held_back"] == 3
