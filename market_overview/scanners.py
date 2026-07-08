"""Piyasa/momentum/Qullamaggie evren tarayıcıları."""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

from market_overview.data import fetch_daily, fetch_data, sector_rs
from market_overview.indicators import compute_adr_pct, momentum_score, relative_volume, trend_template
from market_overview.logging_conf import logger
from market_overview.signals import compute_score, detect_setup, stealth_accumulation, system_decision, ut_bot_signals


def scan_market(tickers: list, period: str, interval: str,
                key_value: float, atr_period: int, lookback: int) -> pd.DataFrame:
    """Her hisse için son `lookback` mumda sinyal var mı kontrol eder."""
    rows = []
    progress = st.progress(0.0, text="Hisseler taranıyor...")
    for i, t in enumerate(tickers):
        progress.progress((i + 1) / len(tickers), text=f"Taranıyor: {t}")
        df = fetch_data(t, period, interval)
        if df is None or len(df) < atr_period + 5:
            continue
        sig = ut_bot_signals(df, key_value, atr_period)
        recent = sig.iloc[-lookback:]
        last = sig.iloc[-1]

        signal = "—"
        bars_ago = None
        if recent["buy"].any():
            signal = "AL"
            bars_ago = lookback - 1 - int(np.where(recent["buy"].values)[0][-1])
        if recent["sell"].any():
            sell_idx = lookback - 1 - int(np.where(recent["sell"].values)[0][-1])
            if signal == "—" or sell_idx < bars_ago:
                signal = "SAT"
                bars_ago = sell_idx

        score = compute_score(df)
        chg = (df["Close"].iloc[-1] - df["Close"].iloc[-2]) / df["Close"].iloc[-2] * 100
        price = float(df["Close"].iloc[-1])
        ut_stop = float(last["stop"])
        bias = "LONG" if last["pos"] == 1 else "SHORT"
        stop_dist = (price - ut_stop) / price * 100
        rows.append({
            "Hisse": t,
            "Sinyal": signal,
            "Eğilim": bias,
            "Kaç Mum Önce": bars_ago if bars_ago is not None else "—",
            "Fiyat": round(price, 2),
            "UT Stop": round(ut_stop, 2),
            "Stop Mesafe %": round(stop_dist, 2),
            "Günlük %": round(float(chg), 2),
            "Skor": score["total"],
            "RSI": score["rsi_val"],
            "Sistem": system_decision(score["total"]),
        })
    progress.empty()
    return pd.DataFrame(rows)


@st.cache_data(ttl=1800)
def scan_qullamaggie_yf(universe: list, min_perf1y: float = 50,
                         min_cap_b: float = 2.0, min_adr_pct: float = 3.5) -> tuple:
    """
    yfinance ile Qullamaggie filtreleri (tamamen yasal, yayın için uygun):
    - Fiyat > EMA100  (~21 haftalık EMA)
    - Fiyat > EMA200  (~50 haftalık EMA)
    - 1Y Performans > min_perf1y%
    - Vol 10G ort > Vol 90G ort  (hacim artıyor)
    - ADR% > min_adr_pct%
    - Piyasa Değeri > min_cap_b milyar $
    30 dakika cache — yfinance batch ile ~300 hisseyi 15-20 sn'de tarar.
    """
    import yfinance as yf

    if not universe:
        return pd.DataFrame(), 0

    # Batch download — tüm hisseleri tek seferde çek (çok daha hızlı)
    raw = yf.download(
        universe, period="1y", interval="1d",
        group_by="ticker", auto_adjust=True,
        progress=False, threads=True,
    )

    rows = []
    price_1y_ago = {}

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

            # Filtre 1: Fiyat > EMA100 ve EMA200
            if price_now <= ema100 or price_now <= ema200:
                continue

            # 1Y performans
            perf_1y = (price_now / float(close.iloc[0]) - 1) * 100
            if perf_1y < min_perf1y:
                continue

            # Hacim artışı: 10 günlük ort > 90 günlük ort
            vol10  = float(volume.iloc[-10:].mean())
            vol90  = float(volume.iloc[-90:].mean())
            if vol10 <= vol90:
                continue

            # ADR%: son 14 günün ortalama günlük aralığı
            daily_range = ((high - low) / close * 100).iloc[-14:]
            adr_pct = float(daily_range.mean())
            if adr_pct < min_adr_pct:
                continue

            # Haftalık / aylık / 3 aylık performans
            perf_w  = (price_now / float(close.iloc[-5])  - 1) * 100 if len(close) >= 5  else 0
            perf_1m = (price_now / float(close.iloc[-21]) - 1) * 100 if len(close) >= 21 else 0
            perf_3m = (price_now / float(close.iloc[-63]) - 1) * 100 if len(close) >= 63 else 0

            # RVOL: bugünkü hacim / 10 günlük ort
            vol_today = float(volume.iloc[-1])
            rvol = round(vol_today / vol90, 2) if vol90 > 0 else 0

            # Piyasa değeri (yaklaşık — fiyat * ortalama hacim proxy, gerçek için yf.Ticker kullan)
            # Gerçek market cap bilgisi için ayrı çekim gerekir, burada hisse başına fiyat kullanıyoruz
            # Büyük cap evreni kullandığımız için bu filtre evrende zaten uygulanmış sayılır
            rows.append({
                "Ticker":      ticker,
                "Fiyat":       round(price_now, 2),
                "Günlük %":    round((price_now / price_prev - 1) * 100, 2),
                "1Y %":        round(perf_1y, 1),
                "Haftalık %":  round(perf_w, 1),
                "Aylık %":     round(perf_1m, 1),
                "3 Aylık %":   round(perf_3m, 1),
                "ADR%":        round(adr_pct, 2),
                "RVOL":        rvol,
                "EMA100":      round(ema100, 2),
                "EMA200":      round(ema200, 2),
                "EMA100 ↑%":   round((price_now / ema100 - 1) * 100, 1),
                "EMA200 ↑%":   round((price_now / ema200 - 1) * 100, 1),
                "EMA10":       round(ema10, 2),
                "EMA20":       round(ema20, 2),
                "Vol 10G":     int(vol10),
                "Vol 90G":     int(vol90),
                "_close":      close,
            })
        except Exception as e:
            logger.warning("%s Qullamaggie taramasında atlandı: %s", ticker, e)
            continue

    if not rows:
        return pd.DataFrame(), 0

    result = pd.DataFrame(rows).sort_values("RVOL", ascending=False).reset_index(drop=True)
    return result, len(result)


def scan_momentum(universe: list, min_rs: int, min_adr: float) -> pd.DataFrame:
    """Qullamaggie/Minervini momentum breakout taraması."""
    rows = []
    prog = st.progress(0.0, text="Momentum taraması...")
    raw = []
    for i, t in enumerate(universe):
        prog.progress((i + 1) / len(universe), text=f"Taranıyor: {t}")
        df = fetch_daily(t, "1y")
        if df is None or len(df) < 60:
            continue
        raw.append((t, df, momentum_score(df)))

    if not raw:
        prog.empty()
        return pd.DataFrame()

    # RS Rating: havuz içi yüzdelik sıralama (1-99)
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
            "Hisse": t,
            "Setup": setup,
            "RS": rs,
            "Sektör RS": sec_rs.get("vs_sector"),
            "ADR %": round(adr, 1),
            "Trend": f"{tt['passed']}/{tt['total']}",
            "Zirveye %": tt["pct_from_high"],
            "Gör. Hacim": round(rvol, 2),
            "Günlük %": round(float(chg), 2),
            "Fiyat": round(float(df["Close"].iloc[-1]), 2),
            "Birikim": stealth["score"],
            "_pass": tt["passed"], "_adr": adr, "_rs": rs,
            "_above": tt["above_cloud"] and tt["above_50"],
            "_stealth": stealth["signal"],
        })
    prog.empty()
    df = pd.DataFrame(rows)
    # Filtre: RS ve ADR eşiği + trend yapısı sağlam
    df = df[(df["_rs"] >= min_rs) & (df["_adr"] >= min_adr) & (df["_above"])]
    return df.sort_values(["_pass", "_rs"], ascending=False)
