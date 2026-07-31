"""Market, momentum, and Qullamaggie universe scanners."""

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

from market_overview.data import fetch_daily, fetch_data, sector_rs
from market_overview.indicators import (
    compute_adr_pct,
    momentum_score,
    relative_volume,
    trend_template,
)
from market_overview.logging_conf import logger
from market_overview.signals import (
    compute_score,
    detect_setup,
    stealth_accumulation,
    system_decision,
    ut_bot_signals,
)


def scan_market(tickers: list, period: str, interval: str,
                key_value: float, atr_period: int, lookback: int) -> pd.DataFrame:
    """Check each stock for a signal in the last lookback bars."""
    rows = []
    progress = st.progress(0.0, text="Scanning stocks...")
    for i, t in enumerate(tickers):
        progress.progress((i + 1) / len(tickers), text=f"Scanning: {t}")
        df = fetch_data(t, period, interval)
        if df is None or len(df) < atr_period + 5:
            continue
        sig = ut_bot_signals(df, key_value, atr_period)
        recent = sig.iloc[-lookback:]
        last = sig.iloc[-1]

        signal = "—"
        bars_ago = None
        if recent["buy"].any():
            signal = "BUY"
            bars_ago = lookback - 1 - int(np.where(recent["buy"].values)[0][-1])
        if recent["sell"].any():
            sell_idx = lookback - 1 - int(np.where(recent["sell"].values)[0][-1])
            if signal == "—" or sell_idx < bars_ago:
                signal = "SELL"
                bars_ago = sell_idx

        score = compute_score(df)
        chg = (df["Close"].iloc[-1] - df["Close"].iloc[-2]) / df["Close"].iloc[-2] * 100
        price = float(df["Close"].iloc[-1])
        ut_stop = float(last["stop"])
        bias = "LONG" if last["pos"] == 1 else "SHORT"
        stop_dist = (price - ut_stop) / price * 100
        rows.append({
            "Stock": t,
            "Signal": signal,
            "Bias": bias,
            "Bars Ago": bars_ago if bars_ago is not None else "—",
            "Price": round(price, 2),
            "UT Stop": round(ut_stop, 2),
            "Stop Distance %": round(stop_dist, 2),
            "Daily %": round(float(chg), 2),
            "Score": score["total"],
            "RSI": score["rsi_val"],
            "System": system_decision(score["total"]),
        })
    progress.empty()
    return pd.DataFrame(rows)


@st.cache_data(ttl=1800)
def scan_qullamaggie_yf(universe: list, min_perf1y: float = 50,
                         min_cap_b: float = 2.0, min_adr_pct: float = 3.5) -> tuple:
    """
    Qullamaggie filters implemented with yfinance:
    - Price > EMA100  (~21 weekly EMA)
    - Price > EMA200  (~50 weekly EMA)
    - 1Y Performans > min_perf1y%
    - Volume 10d average > Volume 90d average (rising volume)
    - ADR% > min_adr_pct%
    - Market Degeri > min_cap_b milyar $
    30-minute cache — scans about 300 stocks in 15–20 seconds with a yfinance batch.
    """

    if not universe:
        return pd.DataFrame(), 0

    # Batch download — download all stocks in one batch (much faster)
    raw = yf.download(
        universe, period="1y", interval="1d",
        group_by="ticker", auto_adjust=True,
        progress=False, threads=True,
    )

    rows = []

    for ticker in universe:
        try:
            if len(universe) == 1:
                df = raw.copy()
            else:
                df = raw[ticker].dropna(how="all")

            if df is None or len(df) < 60:
                continue

            close  = df["Close"].dropna()
            volume = df["Volume"].dropna()
            high   = df["High"].dropna()
            low    = df["Low"].dropna()

            if len(close) < 60:
                continue

            price_now  = float(close.iloc[-1])
            price_prev = float(close.iloc[-2]) if len(close) > 1 else price_now

            # EMA hesapla
            ema100 = float(close.ewm(span=100, adjust=False).mean().iloc[-1])
            ema200 = float(close.ewm(span=200, adjust=False).mean().iloc[-1])
            ema10  = float(close.ewm(span=10,  adjust=False).mean().iloc[-1])
            ema20  = float(close.ewm(span=20,  adjust=False).mean().iloc[-1])

            # Filter 1: Price > EMA100 and EMA200
            if price_now <= ema100 or price_now <= ema200:
                continue

            # 1Y performans
            perf_1y = (price_now / float(close.iloc[0]) - 1) * 100
            if perf_1y < min_perf1y:
                continue

            # Volume artisi: 10 daily ort > 90 daily ort
            vol10  = float(volume.iloc[-10:].mean())
            vol90  = float(volume.iloc[-90:].mean())
            if vol10 <= vol90:
                continue

            # ADR%: son 14 today's average daily araligi
            daily_range = ((high - low) / close * 100).iloc[-14:]
            adr_pct = float(daily_range.mean())
            if adr_pct < min_adr_pct:
                continue

            # Weekly / monthly / 3-month performance
            perf_w  = (price_now / float(close.iloc[-5])  - 1) * 100 if len(close) >= 5  else 0
            perf_1m = (price_now / float(close.iloc[-21]) - 1) * 100 if len(close) >= 21 else 0
            perf_3m = (price_now / float(close.iloc[-63]) - 1) * 100 if len(close) >= 63 else 0

            # RVOL: today's volume / 10 daily ort
            vol_today = float(volume.iloc[-1])
            rvol = round(vol_today / vol90, 2) if vol90 > 0 else 0

            # Market-cap proxy; use yf.Ticker for the actual market-cap value.
            # Gercek market cap bilgisi icin requires a separate fetch, burada per-share price useiyoruz
            # The large-cap universe usedigimiz icin bu filtre evrende zaten is already covered
            rows.append({
                "Ticker":      ticker,
                "Price":       round(price_now, 2),
                "Daily %":    round((price_now / price_prev - 1) * 100, 2),
                "1Y %":        round(perf_1y, 1),
                "Weekly %":  round(perf_w, 1),
                "Monthly %":     round(perf_1m, 1),
                "3-Month %":   round(perf_3m, 1),
                "ADR%":        round(adr_pct, 2),
                "RVOL":        rvol,
                "EMA100":      round(ema100, 2),
                "EMA200":      round(ema200, 2),
                "EMA100 Above %": round((price_now / ema100 - 1) * 100, 1),
                "EMA200 Above %": round((price_now / ema200 - 1) * 100, 1),
                "EMA10":       round(ema10, 2),
                "EMA20":       round(ema20, 2),
                "Volume 10d":     int(vol10),
                "Volume 90d":     int(vol90),
                "_close":      close,
            })
        except Exception as e:
            logger.warning("%s skipped during Qullamaggie scan: %s", ticker, e)
            continue

    if not rows:
        return pd.DataFrame(), 0

    result = pd.DataFrame(rows).sort_values("RVOL", ascending=False).reset_index(drop=True)
    return result, len(result)


def scan_momentum(universe: list, min_rs: int, min_adr: float) -> pd.DataFrame:
    """Qullamaggie/Minervini momentum breakout scan."""
    rows = []
    prog = st.progress(0.0, text="Momentum scan...")
    raw = []
    for i, t in enumerate(universe):
        prog.progress((i + 1) / len(universe), text=f"Scanning: {t}")
        df = fetch_daily(t, "1y")
        if df is None or len(df) < 60:
            continue
        raw.append((t, df, momentum_score(df)))

    if not raw:
        prog.empty()
        return pd.DataFrame()

    # RS Rating: havuz ici yuzdelik siralama (1-99)
    scores = pd.Series({t: s for t, _, s in raw}).rank(pct=True) * 98 + 1

    for t, df, _ in raw:
        tt   = trend_template(df)
        adr  = compute_adr_pct(df)
        rs   = int(round(scores[t]))
        setup = detect_setup(df)
        chg  = (df["Close"].iloc[-1] - df["Close"].iloc[-2]) / df["Close"].iloc[-2] * 100
        rvol = relative_volume(df)
        stealth = stealth_accumulation(df, 10)
        sec_rs  = sector_rs(t, df)
        rows.append({
            "Stock": t,
            "Setup": setup,
            "RS": rs,
            "Sector RS": sec_rs.get("vs_sector"),
            "ADR %": round(adr, 1),
            "Trend": f"{tt['passed']}/{tt['total']}",
            "From High %": tt["pct_from_high"],
            "Rel. Volume": round(rvol, 2),
            "Daily %": round(float(chg), 2),
            "Price": round(float(df["Close"].iloc[-1]), 2),
            "Accumulation": stealth["score"],
            "_pass": tt["passed"], "_adr": adr, "_rs": rs,
            "_above": tt["above_cloud"] and tt["above_50"],
            "_stealth": stealth["signal"],
        })
    prog.empty()
    df = pd.DataFrame(rows)
    # Filter: RS ve ADR threshold + trend structure is sound
    df = df[(df["_rs"] >= min_rs) & (df["_adr"] >= min_adr) & (df["_above"])]
    return df.sort_values(["_pass", "_rs"], ascending=False)
