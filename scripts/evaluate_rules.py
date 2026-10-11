"""Measure the rule classifier on real data.

    python -m scripts.evaluate_rules

1. Coverage on all employee-app 1-3 star reviews: what % the rules can't place.
2. Agreement with the 100 manually labelled reviews (data/reading_sample_labelled.csv).
"""

import pandas as pd

from src import config
from src.classifier import category_name, classify_df
from src.collector import load_reviews

EMPLOYEE_APP = "com.moveinsync.ets"
LABELLED = config.DATA_DIR / "reading_sample_labelled.csv"

# Manual theme group (text before ":" in my_theme) -> classifier category id
GROUP_TO_ID = {
    "Login/OTP": "login", "Booking": "booking", "Stability": "stability",
    "Tracking": "tracking", "Prompts": "prompts", "Usability": "usability",
    "Notifications": "notifications", "Cab ops": "cab_delay", "Routing": "routing",
    "Driver": "driver", "Support": "support", "Safety": "safety", "Vague negative": None,
}


def coverage(df):
    comp = df[df["rating"] <= config.COMPLAINT_MAX_RATING]
    counts = comp["primary_category"].value_counts()
    n = len(comp)
    other = counts.get(config.OTHER, 0)
    low = counts.get(config.LOW_INFO, 0) + counts.get(config.NO_TEXT, 0)
    substantive = n - low
    print(f"1-3 star reviews: {n:,}")
    print(f"  low info / no text:   {low:,} ({low / n:.1%})")
    print(f"  unclassified (Other): {other:,} = {other / substantive:.1%} of substantive reviews")
    print("\nPrimary category share (substantive 1-3 star reviews):")
    for cid, c in counts.items():
        if cid in (config.LOW_INFO, config.NO_TEXT):
            continue
        print(f"  {category_name(cid):36s} {c:6,}  {c / substantive:6.1%}")

    recent = comp[pd.to_datetime(comp["review_date"]) >= "2025-10-01"]
    r_sub = recent[~recent["primary_category"].isin([config.LOW_INFO, config.NO_TEXT])]
    r_other = (r_sub["primary_category"] == config.OTHER).mean()
    print(f"\nLast 12 months: unclassified = {r_other:.1%} of {len(r_sub):,} substantive 1-3 star reviews")


def agreement(df):
    gold = pd.read_csv(LABELLED)
    gold["gold_id"] = gold["my_theme"].str.split(":").str[0].map(GROUP_TO_ID)
    merged = gold.merge(df[["review_id", "primary_category", "categories", "matched_keywords"]],
                        on="review_id", how="left")
    has_gold = merged[merged["gold_id"].notna()]
    primary_ok = (has_gold["gold_id"] == has_gold["primary_category"])
    any_ok = [g in str(c).split("|") for g, c in zip(has_gold["gold_id"], has_gold["categories"])]
    vague = merged[merged["gold_id"].isna()]
    print(f"\nAgreement with manual labels ({len(has_gold)} reviews with a specific theme):")
    print(f"  primary category matches manual theme: {primary_ok.mean():.0%}")
    print(f"  manual theme among matched categories: {sum(any_ok) / len(any_ok):.0%}")
    print(f"  rules found nothing:                   {(has_gold['primary_category'] == config.OTHER).mean():.0%}")
    print(f"  manually 'vague' reviews: {len(vague)}; rules left "
          f"{(vague['primary_category'] == config.OTHER).sum()} of them unclassified")

    misses = has_gold[[not a for a in any_ok]]
    if len(misses):
        print("\nMisses (manual theme not found by rules):")
        for _, r in misses.iterrows():
            print(f"  [{r['gold_id']:>13s} | rules: {r['categories'] or '-'}] {r['review_text'][:110]}")


def main():
    df = load_reviews()
    df = classify_df(df[df["app_id"] == EMPLOYEE_APP])
    coverage(df)
    agreement(df)


if __name__ == "__main__":
    main()
