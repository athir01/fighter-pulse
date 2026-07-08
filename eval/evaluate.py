"""Compares VADER vs. LLM scorer against a hand-labeled gold set.

Fill in eval/gold_set.csv (article_url, fighter_slug, human_sentiment_score)
before running. Reports mean absolute error per scorer against the human
labels — this is the artifact that turns "a pipeline that produces
plausible-looking numbers" into "a pipeline with measured accuracy."
"""

from __future__ import annotations

import csv
from pathlib import Path

_GOLD_SET_PATH = Path(__file__).parent / "gold_set.csv"


def load_gold_set() -> list[dict[str, str]]:
    with _GOLD_SET_PATH.open() as f:
        return list(csv.DictReader(f))


def mean_absolute_error(predicted: list[float], actual: list[float]) -> float:
    if not predicted:
        raise ValueError("no predictions to evaluate")
    return sum(abs(p - a) for p, a in zip(predicted, actual, strict=True)) / len(predicted)


def main() -> None:
    gold = load_gold_set()
    if not gold:
        print(f"No labeled rows in {_GOLD_SET_PATH} yet — nothing to evaluate.")
        return
    print(f"Loaded {len(gold)} gold-labeled rows. TODO: score each row with both scorers.")


if __name__ == "__main__":
    main()
