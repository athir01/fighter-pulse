"""Enforces the hard LLM spend ceiling (Settings.llm_cost_cap_usd).

Persisted via the DB (sum of ingest_runs.llm_cost_usd across all runs) so the
cap survives across separate pipeline invocations, not just within one run.
"""

from __future__ import annotations

from dataclasses import dataclass

# claude-haiku-4-5 pricing, $/token (see Anthropic API pricing).
_HAIKU_INPUT_PER_TOKEN = 1.00 / 1_000_000
_HAIKU_OUTPUT_PER_TOKEN = 5.00 / 1_000_000


def estimate_call_cost(input_tokens: int, output_tokens: int) -> float:
    return input_tokens * _HAIKU_INPUT_PER_TOKEN + output_tokens * _HAIKU_OUTPUT_PER_TOKEN


class CostCapExceeded(Exception):
    """Raised when a call would push cumulative spend past the configured cap."""


@dataclass
class CostTracker:
    cap_usd: float
    spent_usd: float = 0.0
    """Spend from prior runs, loaded by the caller before the run starts."""

    def remaining(self) -> float:
        return max(0.0, self.cap_usd - self.spent_usd)

    def check_and_reserve(self, estimated_cost: float) -> None:
        """Raise CostCapExceeded if this call would exceed the cap; else no-op.

        Call before making the LLM request. Call ``record`` after with the
        actual cost once the response's real usage is known.
        """
        if self.spent_usd + estimated_cost > self.cap_usd:
            raise CostCapExceeded(
                f"LLM cost cap reached: ${self.spent_usd:.4f} spent, "
                f"${self.cap_usd:.2f} cap, ${estimated_cost:.4f} more requested."
            )

    def record(self, actual_cost: float) -> None:
        self.spent_usd += actual_cost
