"""LLM scorer: combined entity disambiguation + per-fighter sentiment in one call.

Uses Claude Haiku 4.5 with structured output so the response is always a
validated list of {fighter_slug, sentiment_score, confidence, rationale} — no
free-text parsing. Every call is cost-checked against CostTracker before it's
made and recorded against it after, using the *actual* token usage returned
by the API (not the pre-call estimate).
"""

from __future__ import annotations

import json
import logging

import anthropic

from ..cost_tracker import CostTracker, estimate_call_cost
from ..models import FighterMention, ScoredMention
from .base import SentimentScorer

_MODEL = "claude-haiku-4-5"

log = logging.getLogger("fighter_pulse")

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "scores": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "fighter_slug": {"type": "string"},
                    "sentiment_score": {
                        "type": "number",
                        "description": "-1.0 (very negative) to 1.0 (very positive)",
                    },
                    "confidence": {"type": "number", "description": "0.0 to 1.0"},
                    "rationale": {
                        "type": "string",
                        "description": "One sentence: which text this score is based on",
                    },
                },
                "required": ["fighter_slug", "sentiment_score", "confidence", "rationale"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["scores"],
    "additionalProperties": False,
}


class LlmScorer(SentimentScorer):
    name = _MODEL

    def __init__(
        self, cost_tracker: CostTracker, client: anthropic.Anthropic | None = None
    ) -> None:
        self.cost_tracker = cost_tracker
        self.client = client if client is not None else anthropic.Anthropic()

    def score(self, article_text: str, mentions: list[FighterMention]) -> list[ScoredMention]:
        if not mentions:
            return []

        fighter_list = ", ".join(f"{m.fighter_slug} ({m.fighter_full_name})" for m in mentions)
        prompt = (
            "This article mentions these fighters: "
            f"{fighter_list}.\n\n"
            "For EACH fighter, determine the sentiment specifically directed at "
            "them (not the article's overall tone) and score it from -1.0 "
            "(very negative) to 1.0 (very positive). If the text mentions "
            "multiple fighters, attribute sentiment to the correct one — e.g. "
            '"Jones would destroy Ngannou" is positive for jon-jones and '
            "negative for the opponent, not neutral for both. Use the exact "
            "slugs listed. If a listed fighter is not actually referenced (a "
            "name collision or a nickname used as an ordinary word), omit "
            "them.\n\n"
            f"Article:\n{article_text}"
        )

        # Rough pre-call estimate to fail fast before spending anything;
        # replaced by the real cost from response.usage below.
        estimated_input = len(prompt) // 4
        estimated_output = 150 * len(mentions)
        self.cost_tracker.check_and_reserve(
            estimate_call_cost(estimated_input, estimated_output)
        )

        response = self.client.messages.create(
            model=_MODEL,
            max_tokens=1024,
            output_config={"format": {"type": "json_schema", "schema": _RESPONSE_SCHEMA}},
            messages=[{"role": "user", "content": prompt}],
        )

        actual_cost = estimate_call_cost(
            response.usage.input_tokens, response.usage.output_tokens
        )
        self.cost_tracker.record(actual_cost)

        if response.stop_reason != "end_turn":
            # max_tokens => truncated JSON; refusal => no JSON. Either way, skip
            # rather than crash on json.loads.
            log.warning("llm_unusable_response stop_reason=%s", response.stop_reason)
            return []

        text_block = next(b for b in response.content if b.type == "text")
        parsed = json.loads(text_block.text)

        # Trust boundary: only accept slugs we asked about. A hallucinated or
        # cross-wired slug would otherwise write a score for a fighter the
        # article never mentioned.
        allowed = {m.fighter_slug for m in mentions}
        scored: list[ScoredMention] = []
        for s in parsed["scores"]:
            if s["fighter_slug"] not in allowed:
                log.warning("llm_unknown_slug slug=%s", s["fighter_slug"])
                continue
            scored.append(
                ScoredMention(
                    fighter_slug=s["fighter_slug"],
                    sentiment_score=_clamp(float(s["sentiment_score"]), -1.0, 1.0),
                    confidence=_clamp(float(s["confidence"]), 0.0, 1.0),
                    rationale=s.get("rationale"),
                    scorer=self.name,
                )
            )
        return scored


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))
