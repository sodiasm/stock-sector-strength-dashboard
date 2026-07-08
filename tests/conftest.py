"""Ortak test fixture'ları — tümü deterministik, ağ erişimi yok."""
import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def ohlcv() -> pd.DataFrame:
    """Deterministik ~60 barlık yükselen trend OHLCV.

    Çoğunlukla artan, her 6. barda küçük düşüş içerir; böylece RSI hesabında
    ``avg_loss > 0`` olur (saf monoton artışta RSI NaN olurdu).
    """
    n = 60
    steps = np.array([-0.5 if i % 6 == 0 else 1.0 for i in range(n)])
    close = 100 + np.cumsum(steps)          # net yükselen, hep pozitif
    high = close * 1.02
    low = close * 0.98
    open_ = close * 0.995
    volume = np.full(n, 1_000_000.0)
    volume[-1] = 3_000_000.0                # son barda hacim sıçraması
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=idx,
    )
