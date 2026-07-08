"""Pydantic records validated at every boundary: parse, don't validate."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ParsedArticle(BaseModel):
    """An article as parsed from an RSS/news source, before any DB write."""

    source: str
    guid: str
    url: str
    title: str
    summary: str | None = None
    published_at: datetime | None = None


class FighterMention(BaseModel):
    """One fighter's name found in an article's text, before scoring."""

    fighter_slug: str
    fighter_full_name: str
    match_score: float
    """Fuzzy-match confidence (0-100) that this mention refers to this fighter."""


class ScoredMention(BaseModel):
    """A fighter mention with a sentiment score attached."""

    fighter_slug: str
    sentiment_score: float
    """-1.0 (very negative) to 1.0 (very positive)."""
    confidence: float | None = None
    rationale: str | None = None
    scorer: str
    """Which scorer produced this: 'vader' or a model id like 'claude-haiku-4-5'."""
