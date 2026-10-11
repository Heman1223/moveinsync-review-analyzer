"""Measure MoveInSync against similar apps (public data, no LLM).

    python -m scripts.benchmark            # newest 500 reviews per app
    python -m scripts.benchmark --n 200    # smaller sample, faster
"""

import argparse

from src import benchmark


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=None, help="newest written reviews per app")
    args = parser.parse_args()
    new = benchmark.run(**({"n": args.n} if args.n else {}))
    cols = ["name", "store_score", "written_avg", "pct_1_star", "reply_rate_unhappy", "sample_n", "error"]
    print(new[[c for c in cols if c in new]].to_string(index=False))
    print()
    for line in benchmark.headline(benchmark.latest()):
        print("-", line)


if __name__ == "__main__":
    main()
