"""Offline tests for the rule classifier. All review text here is synthetic."""

import pandas as pd

from src import config
from src.classifier import classify_df, classify_text, normalize


def test_booking_complaint():
    r = classify_text("Unable to book a cab for tomorrow, the slot disappears")
    assert r.primary == "booking"
    assert "book" in r.matched_keywords["booking"]


def test_otp_complaint():
    assert classify_text("OTP never arrives so I can't get in").primary == "login"


def test_hinglish_cab_not_coming():
    r = classify_text("Roz cab nahi aayi, bahut problem hai")
    assert "cab_delay" in r.categories


def test_multiple_issues_keep_all_categories_and_one_primary():
    r = classify_text("Tracking shows wrong ETA and the OTP for login is never delivered")
    assert {"login", "tracking"} <= set(r.categories)
    assert r.primary == "login"  # login is earlier in the priority order than tracking


def test_word_boundaries_avoid_false_positives():
    # "mapping" must not trigger the "map" keyword, "beta" must not trigger "eta",
    # "latest" must not trigger "late"
    r = classify_text("Joined the beta programme, latest mapping feature is good overall")
    assert "tracking" not in r.categories
    assert "cab_delay" not in r.categories


def test_safety_is_flagged_and_takes_priority():
    r = classify_text("Driver was drunk and the cab was late")
    assert r.is_safety
    assert r.primary == "safety"
    assert "cab_delay" in r.categories


def test_repeated_prompts():
    assert classify_text("Why must I accept the transport policy every time I open it").primary == "prompts"


def test_empty_text_is_rating_only():
    assert classify_text("").primary == config.NO_TEXT
    assert classify_text(None).primary == config.NO_TEXT
    assert classify_text(float("nan")).primary == config.NO_TEXT


def test_short_text_without_keywords_is_low_info():
    assert classify_text("nice app").primary == config.LOW_INFO


def test_longer_text_without_keywords_is_other():
    assert classify_text("I really do not like this thing at all honestly").primary == config.OTHER


def test_curly_apostrophes_are_normalised():
    assert normalize("Doesn’t   work") == "doesn't work"
    assert "stability" in classify_text("It doesn’t work").categories


def test_classify_df_adds_columns_and_handles_missing_text():
    df = pd.DataFrame({"review_text": ["cab is always late", None, "good"], "rating": [1, 5, 5]})
    out = classify_df(df)
    assert list(out["primary_category"]) == ["cab_delay", config.NO_TEXT, config.LOW_INFO]
    assert out.loc[0, "label_source"] == "rule"
    assert out.loc[0, "matched_keywords"] == "cab_delay: late"
    assert "primary_category" not in df.columns  # input untouched


def test_classification_is_deterministic():
    text = "App crashes after the new update and booking fails"
    assert classify_text(text) == classify_text(text)


def test_every_category_has_an_owner_and_keywords():
    ids = [c["id"] for c in config.CATEGORIES]
    assert len(ids) == len(set(ids))
    for c in config.CATEGORIES:
        assert c["fixable_by"] in {"App", "Ops", "Review"}
        assert c["keywords"]
