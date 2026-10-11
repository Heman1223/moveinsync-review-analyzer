"""Honest accuracy check on a held-out set (data/validation_set.csv).

    python -m scripts.validate

The 100 validation reviews were drawn at random from recent substantive 1-3 star
reviews and were NOT used to design keywords. Each has a reference label
(gold_category, optional gold_secondary). Compares:
  - rules only
  - rules + LLM (LLM fills only what rules left unclassified)
"""

import pandas as pd

from src import config, llm_assist
from src.classifier import classify_df
from src.collector import load_reviews

VALIDATION = config.DATA_DIR / "validation_set.csv"
OTHER_IDS = {config.OTHER, "other"}


def score(pred: pd.DataFrame, gold: pd.DataFrame, name: str) -> dict:
    m = gold.merge(pred[["review_id", "primary_category", "categories"]], on="review_id")
    primary = m["primary_category"].where(~m["primary_category"].isin(OTHER_IDS), "other")
    exact = (primary == m["gold_category"]).mean()
    # lenient: gold main category appears anywhere in predicted categories,
    # or predicted primary equals gold secondary (multi-issue reviews)
    cats = m["categories"].fillna("").str.split("|")
    lenient = [
        (g in c) or (p == g) or (isinstance(s, str) and p == s)
        for g, s, p, c in zip(m["gold_category"], m["gold_secondary"], primary, cats)
    ]
    unclassified = (primary == "other").mean()
    return {"method": name, "primary_exact": f"{exact:.0%}",
            "primary_or_secondary": f"{sum(lenient) / len(m):.0%}",
            "left_unclassified": f"{unclassified:.0%}", "n": len(m)}


def main():
    gold = pd.read_csv(VALIDATION)
    reviews = load_reviews()
    rules = classify_df(reviews[reviews["review_id"].isin(gold["review_id"])])
    combined = llm_assist.apply_llm_labels(rules)

    rows = [score(rules, gold, "Rules only"), score(combined, gold, "Rules + LLM")]
    print(pd.DataFrame(rows).to_markdown(index=False))
    print(f"\nReference labels: {gold['gold_category'].ne('other').sum()} specific, "
          f"{gold['gold_category'].eq('other').sum()} vague.")

    m = gold.merge(combined[["review_id", "primary_category", "label_source"]], on="review_id")
    m["primary_category"] = m["primary_category"].replace({config.OTHER: "other"})
    wrong = m[m["primary_category"] != m["gold_category"]]
    print("\nDisagreements (reference -> predicted [source]):")
    for r in wrong.itertuples():
        print(f"  {r.gold_category:>12s} -> {r.primary_category:<12s} [{r.label_source or '-'}] "
              f"{str(r.review_text)[:90]}")


if __name__ == "__main__":
    main()
