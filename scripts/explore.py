"""M3 exploratory analysis: writes docs/exploration.md and data/reading_sample.csv.

    python -m scripts.explore

Everything here is descriptive (counts, averages). No classification yet.
"""

import re
from collections import Counter

import pandas as pd

from src import config
from src.collector import load_reviews

EMPLOYEE_APP = "com.moveinsync.ets"
OUT_MD = config.ROOT / "docs" / "exploration.md"
OUT_SAMPLE = config.DATA_DIR / "reading_sample.csv"
SAMPLE_SIZE = 100
MIN_WORDS_FOR_SAMPLE = 8
MIN_VERSION_REVIEWS = 30

STOPWORDS = set("""
a an the and or but if to of in on at for with from by is are was were be been being am
i me my we our you your it its this that these those they them their he she his her
not no nor so too very can could will would should do does did done have has had
app application please just also even only all any some more most much many one get got
there here what when where which who why how than then as up out into about after before
""".split())


def load_employee_reviews() -> pd.DataFrame:
    df = load_reviews()
    df = df[df["app_id"] == EMPLOYEE_APP].copy()
    df["review_date"] = pd.to_datetime(df["review_date"])
    df["reply_date"] = pd.to_datetime(df["reply_date"])
    df["words"] = df["review_text"].fillna("").str.split().str.len()
    df["quarter"] = df["review_date"].dt.to_period("Q").astype(str)
    return df


def md_table(df: pd.DataFrame) -> str:
    if "reviews" in df.columns:
        df = df.astype({"reviews": int})
    # disable_numparse: otherwise version "12.10" is printed as the number 12.1
    return df.to_markdown(index=False, disable_numparse=True)


def summarise(g: pd.DataFrame) -> pd.Series:
    return pd.Series({
        "reviews": len(g),
        "avg_rating": round(g["rating"].mean(), 2),
        "pct_1_star": round((g["rating"] == 1).mean() * 100, 1),
        "pct_5_star": round((g["rating"] == 5).mean() * 100, 1),
        "pct_replied": round(g["has_reply"].mean() * 100, 1),
    })


def quarterly(df):
    recent = df[df["review_date"] >= "2022-01-01"]
    return recent.groupby("quarter").apply(summarise, include_groups=False).reset_index()


def by_version(df):
    """Major.minor version (e.g. 12.18) for the last two years, with enough reviews."""
    recent = df[(df["review_date"] >= "2024-10-01") & df["review_version"].notna()].copy()
    recent["version"] = recent["review_version"].str.extract(r"^(\d+\.\d+)")[0]
    stats = recent.groupby("version").apply(summarise, include_groups=False)
    first_seen = recent.groupby("version")["review_date"].min().dt.strftime("%Y-%m-%d")
    stats["first_review"] = first_seen
    stats = stats[stats["reviews"] >= MIN_VERSION_REVIEWS].reset_index()
    key = stats["version"].str.split(".", expand=True).astype(int)
    return stats.assign(_a=key[0], _b=key[1]).sort_values(["_a", "_b"]).drop(columns=["_a", "_b"])


def reply_effect(df):
    replied = df[df["has_reply"]]
    edited = replied[replied["review_date"] > replied["reply_date"]]
    dist = edited["rating"].value_counts().sort_index()
    return {
        "replied_total": len(replied),
        "edited_after_reply": len(edited),
        "edited_rating_dist": {int(k): int(v) for k, v in dist.items()},
        "edited_pct_4_5": round(edited["rating"].isin([4, 5]).mean() * 100, 1) if len(edited) else 0,
    }


def length_vs_rating(df):
    bins = pd.cut(df["words"], [0, 3, 10, 30, 1000], labels=["1-3 words", "4-10", "11-30", "31+"])
    return df.groupby(bins, observed=True).apply(summarise, include_groups=False).reset_index().rename(
        columns={"words": "review_length"})


def top_phrases(df, n=25):
    """Most common 2-word phrases in recent 1-2 star reviews (stopwords removed)."""
    low = df[(df["rating"] <= 2) & (df["review_date"] >= "2024-10-01")]
    counts = Counter()
    for text in low["review_text"].fillna(""):
        tokens = [t for t in re.findall(r"[a-z]+", text.lower()) if t not in STOPWORDS and len(t) > 1]
        counts.update(set(zip(tokens, tokens[1:])))  # count each phrase once per review
    return pd.DataFrame([(" ".join(k), v) for k, v in counts.most_common(n)],
                        columns=["phrase", "reviews_containing"])


def reading_sample(df):
    """100 recent, substantive 1-3 star reviews for manual reading. Fixed seed = reproducible."""
    pool = df[(df["rating"] <= 3) & (df["words"] >= MIN_WORDS_FOR_SAMPLE)
              & (df["review_date"] >= "2025-10-01")]
    sample = pool.sample(n=min(SAMPLE_SIZE, len(pool)), random_state=42).sort_values("review_date")
    out = sample[["review_id", "review_date", "rating", "review_version", "thumbs_up", "review_text"]].copy()
    out["review_date"] = out["review_date"].dt.strftime("%Y-%m-%d")
    out["my_theme"] = ""
    out["fixable_by"] = ""
    out["notes"] = ""
    return out, len(pool)


def main():
    df = load_employee_reviews()
    q, v, r = quarterly(df), by_version(df), reply_effect(df)
    lengths, phrases = length_vs_rating(df), top_phrases(df)
    sample, pool_size = reading_sample(df)
    snap = pd.read_csv(config.SNAPSHOTS_CSV)
    snap = snap[snap["app_id"] == EMPLOYEE_APP].iloc[-1]
    store_1_star = snap["stars_1"] / snap["ratings"] * 100

    lines = [
        "# Exploration: employee app (com.moveinsync.ets)",
        "",
        f"Generated by `scripts/explore.py` from {len(df):,} text reviews "
        f"({df['review_date'].min():%b %Y} to {df['review_date'].max():%d %b %Y}).",
        "",
        "## 1. Store rating vs written reviews",
        "",
        "| | Store listing (all ratings) | Written reviews (all time) | Written reviews (last 12 months) |",
        "|---|---|---|---|",
        f"| Count | {int(snap['ratings']):,} | {len(df):,} | {(df['review_date'] >= df['review_date'].max() - pd.Timedelta(days=365)).sum():,} |",
        f"| Average | {snap['score']:.2f} | {df['rating'].mean():.2f} | "
        f"{df[df['review_date'] >= df['review_date'].max() - pd.Timedelta(days=365)]['rating'].mean():.2f} |",
        f"| 1★ share | {store_1_star:.1f}% | {(df['rating'] == 1).mean() * 100:.1f}% | "
        f"{(df[df['review_date'] >= df['review_date'].max() - pd.Timedelta(days=365)]['rating'] == 1).mean() * 100:.1f}% |",
        "",
        "## 2. Quarterly trend (since 2022)",
        "",
        md_table(q),
        "",
        f"## 3. By app version (reviews since Oct 2024, versions with ≥{MIN_VERSION_REVIEWS} reviews)",
        "",
        md_table(v),
        "",
        "## 4. Developer replies and edited reviews",
        "",
        f"- Reviews with a developer reply: {r['replied_total']:,}",
        f"- Of those, edited by the reviewer after the reply: {r['edited_after_reply']:,}",
        f"- Current ratings of those edited reviews: {r['edited_rating_dist']} "
        f"({r['edited_pct_4_5']}% are now 4-5★)",
        "- Caveat: Google only shows the latest version of a review, so the original rating is unknown. "
        "This suggests replies can prompt rating changes; it does not prove it.",
        "",
        "## 5. Review length vs rating",
        "",
        md_table(lengths),
        "",
        "## 6. Most common phrases in 1-2★ reviews (since Oct 2024)",
        "",
        md_table(phrases),
        "",
        "## 7. Reading sample",
        "",
        f"`data/reading_sample.csv`: {len(sample)} random 1-3★ reviews since Oct 2025 with "
        f"≥{MIN_WORDS_FOR_SAMPLE} words (from a pool of {pool_size:,}; seed 42). "
        "Fill in `my_theme`, `fixable_by` (App / Ops / Policy / Unclear) and `notes`.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    sample.to_csv(OUT_SAMPLE, index=False, encoding="utf-8-sig")  # utf-8-sig opens cleanly in Excel
    print(f"Wrote {OUT_MD.relative_to(config.ROOT)} and {OUT_SAMPLE.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
