"""Run the optional LLM step.

    python -m scripts.run_llm                # Job A: label unclassified complaints (cached)
    python -m scripts.run_llm --limit 25     # try it on a small batch first
    python -m scripts.run_llm --suggest      # Job B: write data/keyword_suggestions.csv
"""

import argparse
import sys

from src import config, llm_assist
from src.classifier import classify_df
from src.collector import load_reviews


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="label at most N reviews")
    parser.add_argument("--suggest", action="store_true", help="generate keyword suggestions")
    args = parser.parse_args()

    if not llm_assist.is_available():
        print("No GEMINI_API_KEY found in .env. The app works rules-only without it.")
        return 1

    classified = classify_df(load_reviews())
    if args.suggest:
        final = llm_assist.apply_llm_labels(classified)
        out = llm_assist.suggest_keywords(final)
        print(f"Wrote {len(out)} suggestions to {config.KEYWORD_SUGGESTIONS_CSV.relative_to(config.ROOT)}")
        print("Review them, then add the good ones to src/config.py by hand.")
        return 0

    print(f"Model: {config.LLM_MODEL}")
    summary = llm_assist.label_unclassified(classified, limit=args.limit)
    print(f"\nDone: {summary}")
    return 0 if summary["failed_batches"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
