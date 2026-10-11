"""Refresh the review data from the command line.

    python refresh.py          # incremental: only reviews newer than what we have
    python refresh.py --full   # re-fetch full history for every app
    python refresh.py --no-llm # never call Gemini (rules only)

Fetches reviews, labels new unclassified complaints with Gemini when a key is set (capped
per run), and rebuilds data/reviews_labelled.csv, which the dashboard reads.
"""

import argparse
import sys

from src import pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch and label MoveInSync Play Store reviews.")
    parser.add_argument("--full", action="store_true", help="re-fetch full review history")
    parser.add_argument("--no-llm", action="store_true", help="skip Gemini; keyword rules only")
    args = parser.parse_args()

    summary = pipeline.run(full=args.full, use_llm=False if args.no_llm else None)

    print("\nDone.")
    print(f"  New reviews:        {summary['new_reviews']}")
    print(f"  Duplicates removed: {summary['duplicates_removed']}")
    print(f"  Stored per app:     {summary['per_app']}")
    if summary["llm"]:
        print(f"  Gemini labelled:    {summary['llm']['labelled']} (held back: {summary['llm']['held_back']})")
    if summary["errors"]:
        print("  Problems (previous data kept):")
        for err in summary["errors"]:
            print(f"    - {err}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
