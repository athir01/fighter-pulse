import json
from types import SimpleNamespace
from typing import Any

import pytest

from ingest.cost_tracker import CostCapExceeded, CostTracker
from ingest.models import FighterMention
from ingest.scoring.llm import LlmScorer

MENTIONS = [
    FighterMention(fighter_slug="jon-jones", fighter_full_name="Jon Jones", match_score=100),
    FighterMention(fighter_slug="tom-aspinall", fighter_full_name="Tom Aspinall", match_score=100),
]


class FakeClient:
    """Stands in for anthropic.Anthropic — no network, no spend."""

    def __init__(self, payload: dict[str, Any], stop_reason: str = "end_turn") -> None:
        self.calls = 0
        response = SimpleNamespace(
            stop_reason=stop_reason,
            usage=SimpleNamespace(input_tokens=1000, output_tokens=200),
            content=[SimpleNamespace(type="text", text=json.dumps(payload))],
        )

        def create(**_: Any) -> Any:
            self.calls += 1
            return response

        self.messages = SimpleNamespace(create=create)


def _score(s: str, v: float, c: float = 0.9) -> dict[str, Any]:
    return {"fighter_slug": s, "sentiment_score": v, "confidence": c, "rationale": "r"}


def test_drops_slugs_that_were_not_mentioned():
    client = FakeClient({"scores": [_score("jon-jones", 0.8), _score("francis-ngannou", -0.5)]})
    scorer = LlmScorer(CostTracker(cap_usd=5.0), client=client)  # type: ignore[arg-type]
    assert [s.fighter_slug for s in scorer.score("text", MENTIONS)] == ["jon-jones"]


def test_clamps_out_of_range_scores():
    client = FakeClient({"scores": [_score("jon-jones", 1.7, 1.2)]})
    scorer = LlmScorer(CostTracker(cap_usd=5.0), client=client)  # type: ignore[arg-type]
    [scored] = scorer.score("text", MENTIONS)
    assert scored.sentiment_score == 1.0
    assert scored.confidence == 1.0


def test_truncated_response_returns_nothing_instead_of_crashing():
    client = FakeClient({"scores": []}, stop_reason="max_tokens")
    scorer = LlmScorer(CostTracker(cap_usd=5.0), client=client)  # type: ignore[arg-type]
    assert scorer.score("text", MENTIONS) == []


def test_records_actual_cost_and_blocks_when_over_cap():
    tracker = CostTracker(cap_usd=5.0)
    client = FakeClient({"scores": [_score("jon-jones", 0.1)]})
    LlmScorer(tracker, client=client).score("text", MENTIONS)  # type: ignore[arg-type]
    assert tracker.spent_usd == pytest.approx(1000 * 1e-6 + 200 * 5e-6)

    broke = LlmScorer(CostTracker(cap_usd=5.0, spent_usd=5.0), client=client)  # type: ignore[arg-type]
    with pytest.raises(CostCapExceeded):
        broke.score("text", MENTIONS)
    assert client.calls == 1  # the capped scorer never hit the API
