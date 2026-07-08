import pytest

from ingest.cost_tracker import CostCapExceeded, CostTracker, estimate_call_cost


def test_estimate_call_cost_matches_haiku_pricing():
    # 1M input tokens should cost exactly $1.00; 1M output exactly $5.00.
    assert estimate_call_cost(1_000_000, 0) == pytest.approx(1.00)
    assert estimate_call_cost(0, 1_000_000) == pytest.approx(5.00)


def test_check_and_reserve_allows_under_cap():
    tracker = CostTracker(cap_usd=5.00, spent_usd=4.00)
    tracker.check_and_reserve(0.50)  # should not raise


def test_check_and_reserve_blocks_over_cap():
    tracker = CostTracker(cap_usd=5.00, spent_usd=4.90)
    with pytest.raises(CostCapExceeded):
        tracker.check_and_reserve(0.50)


def test_record_accumulates_spend():
    tracker = CostTracker(cap_usd=5.00, spent_usd=1.00)
    tracker.record(0.25)
    assert tracker.spent_usd == pytest.approx(1.25)
    assert tracker.remaining() == pytest.approx(3.75)
