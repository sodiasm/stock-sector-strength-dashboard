"""breadth.py pure-function tests (network-free)."""
import numpy as np
import pandas as pd

from market_overview.breadth import (
    classify_quadrant,
    count_distribution_days,
    pct_series_above_ma,
    rrg_components,
)


def _series(values, start="2024-01-01"):
    idx = pd.date_range(start, periods=len(values), freq="D")
    return pd.Series(values, index=idx)


def test_classify_quadrant_all_four():
    assert classify_quadrant(101, 101) == "Leading"
    assert classify_quadrant(101, 99) == "Weakening"
    assert classify_quadrant(99, 99) == "Lagging"
    assert classify_quadrant(99, 101) == "Improving"


def test_classify_quadrant_boundary_is_leading():
    # 100/100 siniri Leading tarafina dahil (>=)
    assert classify_quadrant(100, 100) == "Leading"


def test_pct_above_ma_half_when_one_up_one_down():
    idx = pd.date_range("2024-01-01", periods=260, freq="D")
    up = pd.Series(np.linspace(100, 200, 260), index=idx)
    down = pd.Series(np.linspace(200, 100, 260), index=idx)
    df = pd.DataFrame({"UP": up, "DOWN": down})
    pct = pct_series_above_ma(df, 200)
    assert abs(float(pct.iloc[-1]) - 50.0) < 1e-9


def test_pct_above_ma_all_when_all_rising():
    idx = pd.date_range("2024-01-01", periods=260, freq="D")
    df = pd.DataFrame({
        "A": pd.Series(np.linspace(100, 200, 260), index=idx),
        "B": pd.Series(np.linspace(50, 150, 260), index=idx),
    })
    pct = pct_series_above_ma(df, 200)
    assert float(pct.iloc[-1]) == 100.0


def test_distribution_days_counts_down_on_higher_volume():
    # daily decline plus rising volume makes every session a distribution day
    close = _series([100 - i for i in range(30)])
    volume = _series([1000 + i * 10 for i in range(30)])
    out = count_distribution_days(close, volume, lookback=10)
    assert out["count"] == 10
    assert out["lookback"] == 10


def test_distribution_days_zero_when_rising():
    close = _series([100 + i for i in range(30)])
    volume = _series([1000 + i * 10 for i in range(30)])
    assert count_distribution_days(close, volume, lookback=10)["count"] == 0


def test_rrg_components_returns_aligned_frame():
    idx = pd.date_range("2024-01-01", periods=260, freq="D")
    etf = pd.Series(np.linspace(100, 200, 260), index=idx)
    bench = pd.Series(np.linspace(200, 100, 260), index=idx)
    comp = rrg_components(etf, bench)
    assert list(comp.columns) == ["rs_ratio", "rs_mom"]
    assert not comp.isna().any().any()
    assert len(comp) > 100
