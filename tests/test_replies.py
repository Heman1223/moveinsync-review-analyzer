"""Offline tests for the reply assistant (Gemini replaced by fakes)."""

import json

import pandas as pd

from src import replies
from src.playbook import SUB_ISSUES


def test_every_template_fits_google_play_limit_and_rules():
    for cat, subs in SUB_ISSUES.items():
        for sub in subs:
            text = replies.template_reply(cat, sub["id"])
            assert replies.check_reply(text) == [], (cat, sub["id"], text)
            assert replies.CONTACT in text
    assert replies.check_reply(replies.template_reply(None, None)) == []


def test_template_is_specific_to_the_problem():
    text = replies.template_reply("login", "otp_not_received")
    assert "OTP" in text


def test_check_reply_flags_long_or_risky_drafts():
    assert replies.check_reply("x" * 400)
    assert any("refund" in p for p in replies.check_reply("We will refund you."))


def test_llm_reply_saves_and_reuses_draft(tmp_path, monkeypatch):
    monkeypatch.setattr(replies, "DRAFTS_CSV", tmp_path / "drafts.csv")
    calls = []

    def fake(prompt, schema):
        calls.append(prompt)
        return json.dumps({"reply": "Sorry the OTP didn't arrive. Please write to us at [support email]. – Team MoveInSync"})

    first = replies.llm_reply("r1", "otp nahi aaya", 1, "login", "otp_not_received", "OTP not received", generate=fake)
    second = replies.llm_reply("r1", "otp nahi aaya", 1, "login", "otp_not_received", "OTP not received", generate=fake)
    assert first[1] == "gemini" and second[1] == "saved" and first[0] == second[0]
    assert len(calls) == 1                                   # the same review never costs twice


def test_llm_reply_falls_back_to_template_when_draft_breaks_rules(tmp_path, monkeypatch):
    monkeypatch.setattr(replies, "DRAFTS_CSV", tmp_path / "drafts.csv")
    bad = lambda prompt, schema: json.dumps({"reply": "We will refund your money right away!"})
    text, source = replies.llm_reply("r2", "cab late", 1, "cab_delay", "late", "Cab late", generate=bad)
    assert source == "template" and "refund" not in text.lower()

    def broken(prompt, schema):
        raise ConnectionError("down")
    assert replies.llm_reply("r3", "x", 1, None, None, "Other", generate=broken)[1] == "template"


def test_unanswered_lists_newest_unhappy_reviews_without_reply():
    df = pd.DataFrame({"review_id": ["a", "b", "c", "d"], "rating": [1, 2, 5, 1],
                       "has_reply": [False, True, False, False],
                       "review_text": ["bad otp", "late", "great", ""],
                       "review_date": pd.to_datetime(["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04"])})
    assert list(replies.unanswered(df)["review_id"]) == ["a"]
