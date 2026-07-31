"""Shared deterministic test fixtures with no network access."""
import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def ohlcv() -> pd.DataFrame:
    """Deterministic ~60-bar rising-trend OHLCV fixture.

    Mostly rising, with a small dip every sixth bar so RSI calculation
    ``avg_loss > 0`` olur (saf monoton artista RSI NaN olurdu).
    """
    n = 60
    steps = np.array([-0.5 if i % 6 == 0 else 1.0 for i in range(n)])
    close = 100 + np.cumsum(steps)          # net rising, always positive
    high = close * 1.02
    low = close * 0.98
    open_ = close * 0.995
    volume = np.full(n, 1_000_000.0)
    volume[-1] = 3_000_000.0                # volume spike on the last bar
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=idx,
    )
