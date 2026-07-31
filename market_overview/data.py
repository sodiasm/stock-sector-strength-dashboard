"""Yahoo Finance data fetching helpers."""

import functools
import time
import pandas as pd
import streamlit as st
import yfinance as yf

from market_overview.config import STOCK_SECTOR_MAP
from market_overview.logging_conf import logger


def retry(attempts: int = 3, base_delay: float = 0.5):
    """Retry network calls with exponential backoff (0.5s, 1s, 2s).

    Retry only on exceptions. If all attempts fail, log the error and return
    ``None`` so callers retain the existing behavior.
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            delay = base_delay
            for attempt in range(attempts):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:  # noqa: BLE001 — intentionally broad catch
                    if attempt == attempts - 1:
                        logger.warning("%s failed after %d attempts: %s", fn.__name__, attempts, e)
                        return None
                    time.sleep(delay)
                    delay *= 2
            return None
        return wrapper
    return decorator


@st.cache_data(ttl=3600)
def get_float_shares(ticker: str) -> float | None:
    """Fetch the stock's circulating float share count in millions."""
    try:
        info = yf.Ticker(ticker).info
        fs = info.get("floatShares") or info.get("sharesOutstanding")
        return round(fs / 1e6, 1) if fs else None
    except Exception as e:
        logger.warning("%s float data could not be fetched: %s", ticker, e)
        return None


def sector_rs(ticker: str, df: pd.DataFrame) -> dict:
    """
    Calculate the stock's relative strength against its sector ETF.
    A positive result means the stock is stronger than its sector ETF.
    """
    # Which sector?
    sector_etf = None
    for etf, stocks in STOCK_SECTOR_MAP.items():
        if ticker in stocks:
            sector_etf = etf
            break
    if not sector_etf:
        return {"vs_sector": None, "sector_etf": None}

    etf_df = fetch_daily(sector_etf, "3mo")
    if etf_df is None or len(etf_df) < 20:
        return {"vs_sector": None, "sector_etf": sector_etf}

    # Trailing 3-month return: stock vs ETF
    stock_ret = (float(df["Close"].iloc[-1]) / float(df["Close"].iloc[-63]) - 1) * 100 if len(df) >= 63 else 0
    etf_ret   = (float(etf_df["Close"].iloc[-1]) / float(etf_df["Close"].iloc[-63]) - 1) * 100 if len(etf_df) >= 63 else 0
    vs_sector = round(stock_ret - etf_ret, 1)

    return {"vs_sector": vs_sector, "sector_etf": sector_etf,
            "stock_ret": round(stock_ret, 1), "etf_ret": round(etf_ret, 1)}


@st.cache_data(ttl=180, show_spinner=False)
@retry()
def fetch_daily(ticker: str, period: str = "3mo") -> pd.DataFrame | None:
    """Daily data for Market Pulse with a short cache for near-live data.

    Network errors are retried three times with :func:`retry`; permanent errors
    return ``None``.
    """
    df = yf.download(ticker, period=period, interval="1d",
                     progress=False, auto_adjust=True)
    if df is None or len(df) < 2:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna()


@st.cache_data(ttl=300, show_spinner=False)
@retry()
def fetch_data(ticker: str, period: str, interval: str) -> pd.DataFrame | None:
    """Fetch data for the requested period and interval; retry on network errors."""
    df = yf.download(ticker, period=period, interval=interval,
                     progress=False, auto_adjust=True)
    if df is None or len(df) < 30:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna()


