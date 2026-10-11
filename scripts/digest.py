"""Write the weekly digest from saved data (no network, no LLM).

    python -m scripts.digest
"""

from src import analysis, digest


def main():
    data, snaps, tracker, bench = digest.load_inputs()
    text = digest.build(data, snaps, tracker, bench)
    end = analysis.filter_period(data, digest.PRIMARY_APP)["review_date"].max()
    latest, dated = digest.write(text, end)
    print(text)
    print(f"Saved {latest.name} and digests/{dated.name}")


if __name__ == "__main__":
    main()
