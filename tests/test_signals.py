"""signals.py skorlama/karar testleri (ağsız)."""
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
        (100, "AL için uygun"),
        (70, "AL için uygun"),
        (69, "Bekle / izlemeye değer"),
        (40, "Bekle / izlemeye değer"),
        (39, "İşleme girmek riskli"),
        (0, "İşleme girmek riskli"),
    ],
)
def test_system_decision_thresholds(score, expected):
    assert system_decision(score) == expected
