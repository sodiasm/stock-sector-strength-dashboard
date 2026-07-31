"""signals.py scoring/decision tests (network-free)."""
import pytest

from market_overview.signals import compute_score, system_decision


def test_compute_score_has_expected_keys(ohlcv):
    score = compute_score(ohlcv)
    for key in ("total", "trend", "ema", "rsi", "volume", "formation", "rsi_val"):
        assert key in score


def test_compute_score_total_in_range(ohlcv):
    total = compute_score(ohlcv)["total"]
    assert 0 <= total <= 100


def test_compute_score_total_is_component_sum(ohlcv):
    s = compute_score(ohlcv)
    assert s["total"] == s["trend"] + s["ema"] + s["rsi"] + s["volume"] + s["formation"]


@pytest.mark.parametrize(
    "score,expected",
    [
        (100, "Suitable for BUY"),
        (70, "Suitable for BUY"),
        (69, "Wait / worth watching"),
        (40, "Wait / worth watching"),
        (39, "Entering a trade is risky"),
        (0, "Entering a trade is risky"),
    ],
)
def test_system_decision_thresholds(score, expected):
    assert system_decision(score) == expected
