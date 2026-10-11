"""Refresh the review data from the command line.

    python refresh.py          # incremental: only reviews newer than what we have
    python refresh.py --full   # re-fetch full history for every app
"""

import argparse
import sys

from src.collector import refresh


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch MoveInSync Play Store reviews.")
    parser.add_argument("--full", action="store_true", help="re-fetch full review history")
    args = parser.parse_args()

    summary = refresh(full=args.full)

    print("\nDone.")
    print(f"  New reviews:        {summary['new_reviews']}")
    print(f"  Duplicates removed: {summary['duplicates_removed']}")
    print(f"  Stored per app:     {summary['per_app']}")
    if summary["errors"]:
        print("  Problems (previous data kept):")
        for err in summary["errors"]:
            print(f"    - {err}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
