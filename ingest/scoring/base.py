"""Scorer interface — lets classical and LLM scoring be compared/swapped freely."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import FighterMention, ScoredMention


class SentimentScorer(ABC):
    name: str

    @abstractmethod
    def score(self, article_text: str, mentions: list[FighterMention]) -> list[ScoredMention]:
        """Score sentiment toward each mentioned fighter in ``article_text``."""
        raise NotImplementedError
