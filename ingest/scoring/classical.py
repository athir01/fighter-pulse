"""Free, local sentiment scorer (VADER) — the zero-cost eval baseline.

Scores the whole article's sentiment and assigns it identically to every
mentioned fighter, since VADER has no way to attribute sentiment to a specific
entity. That's the exact gap the LLM scorer (llm.py) exists to close — this
class stays in the codebase as the free-tier comparison point in eval/.
"""

from __future__ import annotations

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from ..models import FighterMention, ScoredMention
from .base import SentimentScorer

_analyzer = SentimentIntensityAnalyzer()


class VaderScorer(SentimentScorer):
    name = "vader"

    def score(self, article_text: str, mentions: list[FighterMention]) -> list[ScoredMention]:
        compound = _analyzer.polarity_scores(article_text)["compound"]
        return [
            ScoredMention(
                fighter_slug=m.fighter_slug,
                sentiment_score=compound,
                confidence=None,
                rationale="whole-article sentiment; no entity attribution",
                scorer=self.name,
            )
            for m in mentions
        ]
