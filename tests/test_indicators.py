"""indicators.py saf hesaplama testleri (ağsız)."""
import numpy as np

from market_overview.indicators import (
    compute_adr_pct,
    compute_rsi,
    trend_template,
    wilder_atr,
)


def test_rsi_stays_within_bounds(ohlcv):
    rsi = compute_rsi(ohlcv["Close"]).dropna()
    assert ((rsi >= 0) & (rsi <= 100)).all()


def test_rsi_high_in_uptrend(ohlcv):
    rsi_last = float(compute_rsi(ohlcv["Close"]).iloc[-1])
    assert rsi_last > 70  # güçlü yükselişte RSI yüksek olmalı


def test_adr_pct_is_positive(ohlcv):
    adr = compute_adr_pct(ohlcv)
    assert adr > 0


def test_wilder_atr_length_matches(ohlcv):
    atr = wilder_atr(ohlcv, 14)
    assert len(atr) == len(ohlcv)


def test_wilder_atr_last_positive(ohlcv):
    atr_last = float(wilder_atr(ohlcv, 14).iloc[-1])
    assert atr_last > 0


def test_trend_template_has_expected_keys(ohlcv):
    tt = trend_template(ohlcv)
    for key in ("passed", "total", "checks", "pct_from_high", "high52"):
        assert key in tt


def test_trend_template_checks_are_bool(ohlcv):
    tt = trend_template(ohlcv)
    assert isinstance(tt["checks"], dict)
    assert all(isinstance(v, (bool, np.bool_)) for v in tt["checks"].values())
    assert tt["passed"] == sum(tt["checks"].values())
