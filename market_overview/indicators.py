"""Saf teknik gösterge hesaplamaları (pandas/numpy)."""

import numpy as np
import pandas as pd


def compute_ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def compute_mfi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Money Flow Index — hacim ağırlıklı RSI; para girişi/çıkışını ölçer."""
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    mf = tp * df["Volume"]
    pos = mf.where(tp > tp.shift(), 0.0)
    neg = mf.where(tp < tp.shift(), 0.0)
    pos_sum = pos.rolling(period).sum()
    neg_sum = neg.rolling(period).sum()
    mfr = pos_sum / neg_sum.replace(0, np.nan)
    return 100 - (100 / (1 + mfr))


def compute_obv(df: pd.DataFrame) -> pd.Series:
    """On-Balance Volume — hacmi fiyat yönüne göre toplar; birikim/dağıtım izi."""
    direction = np.sign(df["Close"].diff()).fillna(0)
    return (direction * df["Volume"]).cumsum()


def relative_volume(df: pd.DataFrame, window: int = 20) -> float:
    """Bugünkü hacim / son `window` günün ortalaması. >1.5 = olağandışı ilgi."""
    if len(df) < window + 1:
        return 1.0
    avg = df["Volume"].iloc[-window - 1:-1].mean()
    return float(df["Volume"].iloc[-1] / avg) if avg > 0 else 1.0


def compute_adr_pct(df: pd.DataFrame, period: int = 20) -> float:
    """Average Daily Range % — günlük volatilite (Qullamaggie/Minervini metriği)."""
    if len(df) < period + 1:
        period = max(2, len(df) - 1)
    dr = df["High"] / df["Low"]
    return float((dr.iloc[-period:].mean() - 1) * 100)


def momentum_score(df: pd.DataFrame) -> float:
    """IBD tarzı ağırlıklı getiri (göreli güç ham puanı)."""
    c = df["Close"]
    def ret(n):
        return c.iloc[-1] / c.iloc[-n] - 1 if len(c) > n else c.iloc[-1] / c.iloc[0] - 1
    return 0.4 * ret(63) + 0.3 * ret(126) + 0.2 * ret(189) + 0.1 * ret(252)


def trend_template(df: pd.DataFrame) -> dict:
    """Minervini Trend Template kontrolleri + Qullamaggie EMA bulutu durumu."""
    c = df["Close"]
    price = float(c.iloc[-1])
    ema10 = compute_ema(c, 10).iloc[-1]
    ema20 = compute_ema(c, 20).iloc[-1]
    sma50 = c.rolling(50).mean().iloc[-1] if len(c) >= 50 else c.mean()
    sma150 = c.rolling(150).mean().iloc[-1] if len(c) >= 150 else c.mean()
    sma200 = c.rolling(200).mean().iloc[-1] if len(c) >= 200 else c.mean()
    sma200_prev = c.rolling(200).mean().iloc[-21] if len(c) >= 221 else sma200
    high52 = float(c.iloc[-252:].max()) if len(c) >= 60 else float(c.max())
    low52 = float(c.iloc[-252:].min()) if len(c) >= 60 else float(c.min())

    checks = {
        "Fiyat > 50MA": price > sma50,
        "50MA > 150MA": sma50 > sma150,
        "150MA > 200MA": sma150 > sma200,
        "200MA yükseliyor": sma200 > sma200_prev,
        "52H zirvenin %25'i içinde": price >= high52 * 0.75,
        "52H dipten %30+ yukarı": price >= low52 * 1.30,
        "Bulut üstünde (EMA10>EMA20)": price > ema10 and ema10 > ema20,
    }
    return {
        "passed": sum(checks.values()),
        "total": len(checks),
        "checks": checks,
        "above_cloud": price > ema10 > ema20,
        "above_50": price > sma50,
        "pct_from_high": round((price / high52 - 1) * 100, 1),
        "high52": round(high52, 2),
    }


def wilder_atr(df: pd.DataFrame, period: int) -> pd.Series:
    """TradingView atr() ile uyumlu Wilder (RMA) ATR."""
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()
