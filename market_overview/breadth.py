"""Market health (decline radar) ve sector rotation (RRG) hesaplari.

Iki katman:
- Pure functions (network-free, testable): breadth percentage, distribution day
  counts, RRG components, and quadrant classification.
- Cached network wrappers: download yfinance batches and apply the functions above.
"""
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

from market_overview.config import SECTOR_ETFS, SP500_UNIVERSE
from market_overview.logging_conf import logger

# Cyclical (risk-on) ve defensive (risk-off) sector ETF'leri
CYCLIC_ETFS = ["XLK", "XLY", "XLI", "XLF"]
DEFENSIVE_ETFS = ["XLP", "XLU", "XLV"]

# RRG parameters (JdK methodology, daily data)
RRG_WINDOW = 14       # z-score normalizasyon penceresi
RRG_ROC_PERIOD = 20   # momentum lookback (~1 ay)
RRG_TAIL = 8          # kuyruk uzunlugu (son N nokta)


# ---------------------------------------------------------------------------
# PURE FUNCTIONS (network-free, testable)
# ---------------------------------------------------------------------------

def pct_series_above_ma(close_df: pd.DataFrame, ma: int) -> pd.Series:
    """For each date, among stocks with sufficient history `ma` daily
    the percentage of stocks above their moving average."""
    ma_df = close_df.rolling(ma).mean()
    valid = ma_df.notna()
    above = (close_df > ma_df) & valid
    counts = valid.sum(axis=1)
    pct = above.sum(axis=1) / counts.replace(0, np.nan) * 100
    return pct.dropna()


def count_distribution_days(close: pd.Series, volume: pd.Series,
                            lookback: int = 25, drop_pct: float = 0.2) -> dict:
    """O'Neil distribution day: close ≤ -drop_pct% and volume higher than the previous day.
    Count over the last lookback sessions (institutional selling indicator)."""
    chg = close.pct_change() * 100
    higher_vol = volume > volume.shift(1)
    dist = (chg <= -drop_pct) & higher_vol
    recent = dist.iloc[-lookback:]
    return {"count": int(recent.sum()), "lookback": int(min(lookback, len(dist)))}


def rrg_components(etf_close: pd.Series, bench_close: pd.Series,
                   roc_period: int = RRG_ROC_PERIOD, win: int = RRG_WINDOW) -> pd.DataFrame:
    """Return aligned JdK RS-Ratio and RS-Momentum series without NaNs."""
    rs = (etf_close / bench_close) * 100
    rs_ratio = (rs - rs.rolling(win).mean()) / rs.rolling(win).std() + 100
    roc = (rs_ratio / rs_ratio.shift(roc_period) - 1) * 100
    rs_mom = (roc - roc.rolling(win).mean()) / roc.rolling(win).std() + 100
    return pd.DataFrame({"rs_ratio": rs_ratio, "rs_mom": rs_mom}).dropna()


def classify_quadrant(rs_ratio: float, rs_mom: float) -> str:
    """RRG quadrant: Leading / Weakening / Lagging / Improving."""
    if rs_ratio >= 100 and rs_mom >= 100:
        return "Leading"
    if rs_ratio >= 100 and rs_mom < 100:
        return "Weakening"
    if rs_ratio < 100 and rs_mom < 100:
        return "Lagging"
    return "Improving"


# ---------------------------------------------------------------------------
# CACHED NETWORK WRAPPERS
# ---------------------------------------------------------------------------

@st.cache_data(ttl=1800, show_spinner=False)
def _batch_close(symbols_tuple: tuple, period: str = "1y") -> pd.DataFrame:
    """Download a batch and return an aligned DataFrame of Close series by symbol."""
    symbols = list(symbols_tuple)
    raw = yf.download(symbols, period=period, interval="1d", group_by="ticker",
                      auto_adjust=True, progress=False, threads=True)
    if raw is None or raw.empty:
        return pd.DataFrame()
    multi = isinstance(raw.columns, pd.MultiIndex)
    closes = {}
    for t in symbols:
        try:
            if multi:
                if t not in raw.columns.get_level_values(0):
                    continue
                s = raw[t]["Close"].dropna()
            else:  # single symbol with flat columns
                s = raw["Close"].dropna()
            if len(s) > 0:
                closes[t] = s
        except Exception as e:
            logger.warning("breadth/batch %s skipped: %s", t, e)
    if not closes:
        return pd.DataFrame()
    return pd.DataFrame(closes)


@st.cache_data(ttl=1800, show_spinner=False)
def _batch_close_range(symbols_tuple: tuple, start: str, end: str) -> pd.DataFrame:
    """Download aligned adjusted closes for an explicit historical date range."""
    symbols = list(symbols_tuple)
    raw = yf.download(symbols, start=start, end=end, interval="1d",
                      group_by="ticker", auto_adjust=True, progress=False,
                      threads=True)
    if raw is None or raw.empty:
        return pd.DataFrame()

    multi = isinstance(raw.columns, pd.MultiIndex)
    closes = {}
    for t in symbols:
        try:
            if multi:
                if t not in raw.columns.get_level_values(0):
                    continue
                s = raw[t]["Close"].dropna()
            else:
                s = raw["Close"].dropna()
            if len(s) > 0:
                closes[t] = s
        except Exception as e:
            logger.warning("breadth/range %s skipped: %s", t, e)
    if not closes:
        return pd.DataFrame()
    result = pd.DataFrame(closes)
    result.index = pd.DatetimeIndex(result.index).tz_localize(None).normalize()
    return result


@st.cache_data(ttl=1800, show_spinner=False)
def market_breadth(universe_tuple: tuple = tuple(SP500_UNIVERSE)) -> dict | None:
    """Percentage of the universe above the 50-day and 200-day MAs plus SPX divergence."""
    df = _batch_close(universe_tuple, "1y")
    if df.empty:
        return None

    out = {"total": int(df.shape[1]), "ma": {}}
    for ma in (50, 200):
        series = pct_series_above_ma(df, ma)
        if series.empty:
            continue
        now = float(series.iloc[-1])
        prev = float(series.iloc[-21]) if len(series) >= 21 else now
        out["ma"][ma] = {"now": now, "prev20": prev, "series": series}

    # Divergence: early warning when SPX rises for 20 days while 200MA breadth falls
    spx = _batch_close(("SPY",), "3mo")
    if not spx.empty and 200 in out["ma"]:
        spx_close = spx.iloc[:, 0]
        spx_chg20 = (spx_close.iloc[-1] / spx_close.iloc[-21] - 1) * 100 if len(spx_close) >= 21 else 0.0
        b = out["ma"][200]
        out["divergence"] = bool(spx_chg20 > 0 and b["now"] < b["prev20"] - 3)
        out["spx_chg20"] = float(spx_chg20)
    return out


@st.cache_data(ttl=1800, show_spinner=False)
def distribution_days(symbol: str = "SPY") -> dict | None:
    """Number of distribution days for SPY over the last 25 sessions (volume data is required)."""
    raw = yf.download(symbol, period="3mo", interval="1d", auto_adjust=True, progress=False)
    if raw is None or raw.empty:
        return None
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    return count_distribution_days(raw["Close"], raw["Volume"])


@st.cache_data(ttl=1800, show_spinner=False)
def defensive_cyclical() -> dict | None:
    """XLY/XLP ratio plus cyclical versus defensive 20-day return spread (risk-on/off)."""
    df = _batch_close(tuple(CYCLIC_ETFS + DEFENSIVE_ETFS), "6mo")
    if df.empty or "XLY" not in df or "XLP" not in df:
        return None

    ratio = (df["XLY"] / df["XLP"]).dropna()
    slope20 = (ratio.iloc[-1] / ratio.iloc[-21] - 1) * 100 if len(ratio) >= 21 else 0.0

    def avg_ret(cols):
        vals = []
        for c in cols:
            if c in df and len(df[c].dropna()) >= 21:
                s = df[c].dropna()
                vals.append((s.iloc[-1] / s.iloc[-21] - 1) * 100)
        return float(np.mean(vals)) if vals else 0.0

    cyc = avg_ret(CYCLIC_ETFS)
    deff = avg_ret(DEFENSIVE_ETFS)
    return {
        "ratio_slope20": float(slope20),
        "cyclical_ret20": cyc,
        "defensive_ret20": deff,
        "risk_on": bool(slope20 > 0 and cyc > deff),
        "ratio_series": ratio,
    }


@st.cache_data(ttl=1800, show_spinner=False)
def sector_rrg(as_of=None, benchmark: str = "SPY") -> dict | None:
    """RS-Ratio/RS-Momentum tail and current quadrant for each sector ETF."""
    today = pd.Timestamp.today().normalize()
    as_of_ts = today if as_of is None else pd.Timestamp(as_of).normalize()
    min_date = pd.Timestamp("2026-01-01")
    if as_of_ts < min_date or as_of_ts > today:
        raise ValueError(f"as_of must be between {min_date.date()} and {today.date()}")

    etfs = list(SECTOR_ETFS.keys())
    start = (as_of_ts - pd.DateOffset(years=1)).strftime("%Y-%m-%d")
    end = (as_of_ts + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    df = _batch_close_range(tuple([benchmark] + etfs), start, end)
    if df.empty or benchmark not in df:
        return None

    df = df.loc[df.index <= as_of_ts]

    bench = df[benchmark]
    out = {}
    for etf in etfs:
        if etf not in df:
            continue
        comp = rrg_components(df[etf].dropna(), bench)
        if len(comp) < 2:
            continue
        tail = comp.iloc[-RRG_TAIL:]
        x = float(tail["rs_ratio"].iloc[-1])
        y = float(tail["rs_mom"].iloc[-1])
        out[etf] = {
            "name": SECTOR_ETFS[etf],
            "x": x, "y": y,
            "as_of": tail.index[-1].date().isoformat(),
            "quadrant": classify_quadrant(x, y),
            "tail_x": tail["rs_ratio"].tolist(),
            "tail_y": tail["rs_mom"].tolist(),
        }
    return out or None
