"""Free fighter-name resolution: find which roster fighters an article mentions.

This is the zero-cost first pass. It answers "which fighters are plausibly in
this text?"; the LLM scorer (scoring/llm.py) does the harder job of deciding
which sentence targets which fighter.

Matching strategy — exact token matching on normalized text, not fuzzy scores:

* Text and names are normalized the same way: accents stripped
  ("Procházka" -> "Prochazka"), punctuation collapsed to spaces
  ("O'Malley" / "O’Malley" -> "O Malley"). Matching is then a whole-token
  substring check, so "Alex Pereira" can no longer match "Alex Perez" — the
  false positive the previous fuzzy ``partial_ratio`` approach produced.
* Full names and multi-word aliases match case-insensitively.
* Single-word aliases ("Chaos", "Rocky", "Bullet") match case-sensitively,
  because as lowercase words they are ordinary English and would flood the
  pipeline with false positives.

Surname-only mentions ("Jones vs Aspinall") are deliberately NOT matched here:
surnames collide across the roster, and a wrong match costs an LLM call plus a
wrong VADER row. Precision over recall for the cheap pass.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from .models import FighterMention

_FIGHTERS_SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "fighters_seed.json"
_TOKEN = re.compile(r"[A-Za-z0-9]+")


class RosterEntry(TypedDict):
    slug: str
    full_name: str
    aliases: list[str]


def load_roster(path: Path = _FIGHTERS_SEED_PATH) -> list[RosterEntry]:
    raw = json.loads(path.read_text())
    return [
        RosterEntry(
            slug=str(f["slug"]),
            full_name=str(f["full_name"]),
            aliases=[str(a) for a in f.get("aliases", [])],
        )
        for f in raw
    ]


def normalize(text: str, *, lower: bool = True) -> str:
    """Strip accents and punctuation; pad with spaces so `in` is a whole-token match."""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    tokens = _TOKEN.findall(ascii_only.lower() if lower else ascii_only)
    return f" {' '.join(tokens)} "


@dataclass(frozen=True)
class _Pattern:
    slug: str
    full_name: str
    needle: str
    case_sensitive: bool


class FighterMatcher:
    """Pre-normalizes the roster once so each article costs one pass per pattern."""

    def __init__(self, roster: Sequence[RosterEntry]) -> None:
        patterns: list[_Pattern] = []
        for f in roster:
            for name in (f["full_name"], *f["aliases"]):
                case_sensitive = len(name.split()) == 1 and name != f["full_name"]
                needle = normalize(name, lower=not case_sensitive)
                if needle.strip():
                    patterns.append(_Pattern(f["slug"], f["full_name"], needle, case_sensitive))
        self._patterns = patterns

    def find(self, text: str) -> list[FighterMention]:
        lowered = normalize(text)
        cased = normalize(text, lower=False)
        found: dict[str, FighterMention] = {}
        for p in self._patterns:
            if p.slug in found:
                continue
            haystack = cased if p.case_sensitive else lowered
            if p.needle in haystack:
                found[p.slug] = FighterMention(
                    fighter_slug=p.slug, fighter_full_name=p.full_name, match_score=100.0
                )
        return list(found.values())


def find_fighter_mentions(
    text: str, roster: Sequence[RosterEntry] | None = None
) -> list[FighterMention]:
    """Convenience wrapper; build a FighterMatcher once instead when matching many texts."""
    return FighterMatcher(roster if roster is not None else load_roster()).find(text)
