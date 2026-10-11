"""Offline tests for metrics and ranking. Synthetic reviews; expected values worked out by hand."""

import pandas as pd
import pytest

from src import analysis, config

EMPTY_LLM = pd.DataFrame(columns=["review_id", "llm_category", "llm_secondary", "llm_is_safety",
                                  "llm_reason", "llm_model", "labelled_at"])


def make(rows):
    """rows: (review_id, text, rating, date, has_reply)"""
    df = pd.DataFrame(rows, columns=["review_id", "review_text", "rating", "review_date", "has_reply"])
    df["app_id"] = "com.moveinsync.ets"
    df["review_version"] = None
    df["thumbs_up"] = 0
    df["reply_text"] = df["has_reply"].map(lambda r: "Sorry" if r else None)
    df["reply_date"] = df.apply(lambda r: r["review_date"] if r["has_reply"] else None, axis=1)
    df["fetched_lang"] = "en"
    return analysis.prepare(df, EMPTY_LLM)


@pytest.fixture
def sample():
    return make([
        ("a", "OTP never arrives, cannot sign in", 1, "2026-09-01", False),
        ("b", "OTP not received again today", 2, "2026-09-02", True),
        ("c", "The cab is always late in the evening", 1, "2026-09-03", False),
        ("d", "Driver was drunk and drove dangerously", 1, "2026-09-04", False),
        ("e", "good", 5, "2026-09-05", False),
        ("f", "Very useful for daily office commute", 5, "2026-09-06", False),
        ("g", "Tracking is a bit slow but works overall okay", 3, "2026-09-07", False),
        ("h", "", 4, "2026-09-08", False),
    ])


def test_uplift_matches_hand_calculation(sample):
    s = analysis.issue_summary(sample).set_index("category")
    # login: ratings 1 and 2 -> (4-1)+(4-2)=5 over 8 written reviews
    assert s.loc["login", "uplift"] == pytest.approx(5 / 8, abs=1e-3)
    # cab_delay: one 1-star -> 3/8
    assert s.loc["cab_delay", "uplift"] == pytest.approx(3 / 8, abs=1e-3)
    # 3-star reviews count as complaints but add no uplift
    assert s.loc["tracking", "uplift"] == 0


def test_ranking_pins_safety_then_sorts_by_impact(sample):
    s = analysis.issue_summary(sample)
    assert s.iloc[0]["category"] == "safety"
    assert list(s["category"][1:3]) == ["login", "cab_delay"]


def test_top_fixes_excludes_safety(sample):
    top = analysis.top_fixes(analysis.issue_summary(sample), n=2)
    assert "safety" not in set(top["category"])
    assert top.iloc[0]["category"] == "login"


def test_low_info_and_empty_text_are_not_issues(sample):
    s = analysis.issue_summary(sample)
    assert s["reviews"].sum() == 5          # a, b, c, d, g ; not e/f(5 star) or h(no text)
    cov = analysis.uncategorised(sample)
    assert cov["complaints"] == 5 and cov["unclassified"] == 0


def test_kpis_and_reply_rate(sample):
    k = analysis.kpis(sample)
    assert k["reviews"] == 8
    assert k["avg_rating"] == pytest.approx((1 + 2 + 1 + 1 + 5 + 5 + 3 + 4) / 8, abs=0.01)
    assert k["pct_1_star"] == 37.5
    assert k["reply_rate_unhappy"] == 25.0   # 1 of the 4 reviews rated 1-2 has a reply


def test_examples_show_lowest_rated_first(sample):
    ex = analysis.examples(sample, "login", n=5, min_words=1)
    assert list(ex["rating"]) == [1, 2]


def test_version_table_sorts_numerically_and_flags_small_versions():
    df = make([("a", "slow app", 1, "2026-01-01", False), ("b", "slow app", 2, "2026-01-02", False),
               ("c", "slow app", 3, "2026-01-03", False)])
    df["review_version"] = ["12.9.1", "12.10.0", "12.10.2"]
    vt = analysis.version_table(df, min_reviews=2)
    assert list(vt["version"]) == ["12.9", "12.10"]
    assert list(vt["enough_data"]) == [False, True]


def test_missing_optional_fields_do_not_break_analysis(sample):
    sample = sample.assign(review_version=None, thumbs_up=0)
    assert not analysis.issue_summary(sample).empty
    assert analysis.version_table(sample).empty
    analysis.reply_health(sample)
    analysis.monthly_trend(sample)


def test_empty_period_is_handled():
    empty = make([("a", "slow app", 1, "2026-01-01", False)]).iloc[0:0]
    assert analysis.issue_summary(empty).empty
    assert analysis.kpis(empty)["reviews"] == 0


def test_period_start_anchors_on_newest_review(sample):
    assert analysis.period_start(sample, 7) == pd.Timestamp("2026-09-01")
    assert analysis.period_start(sample, None) is None


def test_results_are_deterministic(sample):
    a = analysis.issue_summary(sample)
    b = analysis.issue_summary(sample)
    pd.testing.assert_frame_equal(a, b)


def test_trend_is_hidden_when_too_few_complaints(sample):
    s = analysis.issue_summary(sample)
    assert s["share_before"].isna().all() and s["share_last_period"].isna().all()
