"""Free fighter-name resolution: fuzzy-match article text against the roster.

This is the zero-cost first pass (Story: no-LLM entity resolution). It's
intentionally crude compared to the LLM scorer — it finds *which* fighters are
plausibly mentioned; the LLM scorer (scoring/llm.py) does the harder job of
disambiguating *which sentence* targets *which* fighter when an article
mentions more than one.
"""

from __future__ import annotations

import json
from pathlib import Path

from rapidfuzz import fuzz, process

from .models import FighterMention

_FIGHTERS_SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "fighters_seed.json"
_MATCH_THRESHOLD = 85.0


def load_roster(path: Path = _FIGHTERS_SEED_PATH) -> list[dict[str, object]]:
    return json.loads(path.read_text())


def find_fighter_mentions(
    text: str, roster: list[dict[str, object]] | None = None
) -> list[FighterMention]:
    """Return every roster fighter whose name (or an alias) fuzzy-matches ``text``."""
    roster = roster if roster is not None else load_roster()

    mentions: list[FighterMention] = []
    for fighter in roster:
        names = [str(fighter["full_name"]), *[str(a) for a in fighter["aliases"]]]  # type: ignore[index]
        best = process.extractOne(
            query=str(fighter["full_name"]),
            choices=[text],
            scorer=fuzz.partial_ratio,
        )
        # partial_ratio against the whole article is a blunt instrument; scan
        # each candidate name individually and keep the best hit.
        best_score = 0.0
        for name in names:
            score = fuzz.partial_ratio(name.lower(), text.lower())
            best_score = max(best_score, score)

        if best_score >= _MATCH_THRESHOLD:
            mentions.append(
                FighterMention(
                    fighter_slug=str(fighter["slug"]),
                    fighter_full_name=str(fighter["full_name"]),
                    match_score=best_score,
                )
            )
    return mentions
