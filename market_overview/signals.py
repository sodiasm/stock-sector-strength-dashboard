"""Setup tespiti, skorlama ve para akışı sinyalleri."""

import numpy as np
import pandas as pd
import streamlit as st

from market_overview.data import fetch_daily
from market_overview.indicators import (
    compute_adr_pct,
    compute_ema,
    compute_mfi,
    compute_obv,
    compute_rsi,
    relative_volume,
    wilder_atr,
)


def detect_setup(df: pd.DataFrame) -> str:
    """Qullamaggie'nin 3 temel setupını + trend/zayıf etiketini döner."""
    c = df["Close"]
    if len(c) < 25:
        return "Yetersiz veri"
    ema10 = compute_ema(c, 10)
    ema20 = compute_ema(c, 20)
    price  = float(c.iloc[-1])
    open_  = float(df["Open"].iloc[-1])
    above_cloud = price > ema10.iloc[-1] > ema20.iloc[-1]

    vol_now = float(df["Volume"].iloc[-1])
    vol_avg = float(df["Volume"].iloc[-20:].mean())
    rvol    = vol_now / vol_avg if vol_avg > 0 else 1.0

    # Episodic Pivot: gün içi gap %4+ ve hacim 2.5x+
    gap_pct = (open_ - float(c.iloc[-2])) / float(c.iloc[-2]) * 100 if len(c) >= 2 else 0
    if gap_pct >= 4.0 and rvol >= 2.5:
        return " Episodik Pivot"

    # Konsolidasyon + Kırılım
    recent = c.iloc[-10:]
    rng = (recent.max() - recent.min()) / recent.min() * 100
    adr = compute_adr_pct(df)
    cons_high = float(df["High"].iloc[-11:-1].max())
    tight = rng < adr * 2.0

    if above_cloud and price > cons_high and rvol >= 1.5:
        return " Kırılım"

    # EMA Geri Çekilme: EMA10/20'ye dokunup döndü
    low_last3 = float(df["Low"].iloc[-3:].min())
    touched_ema = ema10.iloc[-4] * 0.995 <= low_last3 <= ema20.iloc[-4] * 1.01
    bouncing = price > float(c.iloc[-2])
    if above_cloud and touched_ema and bouncing and not tight:
        return " EMA Geri Çekilme"

    if above_cloud and tight:
        return " Sıkışma (VCP)"
    if above_cloud:
        return " Trend"
    if price < ema20.iloc[-1]:
        return " Zayıf"
    return "↔ Belirsiz"


def explain_trade(setup: str, df: pd.DataFrame) -> dict:
    """
    Qullamaggie mantığıyla trade planı üretir.
    Döner: giriş, stop, hedef, risk/ödül, gerekçe, ne bekle.
    """
    c   = df["Close"]
    hi  = df["High"]
    lo  = df["Low"]
    price = float(c.iloc[-1])
    ema10 = float(compute_ema(c, 10).iloc[-1])
    ema20 = float(compute_ema(c, 20).iloc[-1])
    adr   = compute_adr_pct(df)

    if "Kırılım" in setup:
        entry  = round(price * 1.002, 2)
        stop   = round(ema10 * 0.985, 2)
        target = round(entry * (1 + adr / 100 * 5), 2)
        neden  = ("Hacimli kırılım: fiyat konsolidasyon tepesini yüksek hacimle geçti. "
                  "Kurumsal alım baskısı var.")
        bekle  = "Kapanış kırılım seviyesinin üstünde olmalı. Düşük hacimli kırılım = sahte."

    elif "Episodik" in setup:
        entry  = round(price, 2)
        stop   = round(float(lo.iloc[-1]) * 0.98, 2)
        target = round(entry * 1.25, 2)
        neden  = ("Episodik Pivot: büyük hacimli gap-up. Kurumlar hisseyi yeniden fiyatlıyor. "
                  "Birkaç günde %20-50 gelebilir.")
        bekle  = "Gap dolmazsa güçlü. Gap tamamen kapanırsa setup bozulmuş — çık."

    elif "EMA Geri" in setup:
        entry  = round(ema10 * 1.005, 2)
        stop   = round(ema20 * 0.985, 2)
        target = round(entry * (1 + adr / 100 * 4), 2)
        neden  = ("Trend sağlam, fiyat EMA10'a dokunup döndü. "
                  "Düşük riskli giriş — trend yönünde alım.")
        bekle  = "EMA'lar yukarı eğimli olmalı. Hacim geri çekilmede düşük, çıkışta yüksek."

    elif "Sıkışma" in setup:
        cons_high = float(hi.iloc[-21:-1].max())
        entry  = round(cons_high * 1.005, 2)
        stop   = round(ema20 * 0.985, 2)
        target = round(entry * (1 + adr / 100 * 5), 2)
        neden  = ("VCP sıkışması: hacim daralıyor, fiyat dar bantta. Kırılım öncesi birikim. "
                  f"Kırılım emri: ${entry} — henüz girme, tetiklenince gir.")
        bekle  = f"Kırılım seviyesi: ${entry}. Hacim 1.5x+ olmalı. Kırılım yoksa bekle."

    else:
        return {}

    rr = round((target - entry) / max(entry - stop, 0.01), 1)
    return {"entry": entry, "stop": stop, "target": target,
            "rr": rr, "neden": neden, "bekle": bekle, "setup": setup}


def stealth_accumulation(df: pd.DataFrame, days: int = 10) -> dict:
    """
    Fiyat hareket etmeden önce hacim artışını tespit eder.
    Smart money sessizce topluyor = fiyat flat, hacim yükseliyor.
    Skor 0-100. 70+ = güçlü birikim sinyali.
    """
    if len(df) < days + 5:
        return {"score": 0, "signal": False}

    recent = df.iloc[-days:]
    price_change = abs((float(recent["Close"].iloc[-1]) - float(recent["Close"].iloc[0]))
                       / float(recent["Close"].iloc[0]) * 100)

    # OBV eğimi — hacim birikim yönü
    obv = compute_obv(df)
    obv_recent = obv.iloc[-days:]
    x = np.arange(len(obv_recent))
    obv_slope = float(np.polyfit(x, obv_recent.values, 1)[0])
    obv_norm = obv_slope / (abs(float(obv_recent.mean())) + 1)

    # Hacim eğimi — artıyor mu?
    vol = recent["Volume"].values
    vol_slope = float(np.polyfit(x, vol, 1)[0])
    vol_norm = vol_slope / (float(vol.mean()) + 1)

    # MFI divergans: MFI yükseliyor, fiyat flat
    mfi = compute_mfi(df, 14)
    mfi_recent = mfi.iloc[-days:]
    mfi_slope = float(mfi_recent.iloc[-1]) - float(mfi_recent.iloc[0])

    # Stealth skor: fiyat flat iken hacim/OBV yükseliyorsa yüksek
    price_flat = price_change < 5.0
    obv_rising = obv_norm > 0
    vol_rising = vol_norm > 0
    mfi_rising = mfi_slope > 3

    score = 0
    if price_flat:   score += 20
    if obv_rising:   score += 30
    if vol_rising:   score += 25
    if mfi_rising:   score += 25
    score = min(100, score)

    return {
        "score": score,
        "signal": score >= 60 and price_flat,
        "price_chg_pct": round(price_change, 1),
        "obv_rising": obv_rising,
        "vol_rising": vol_rising,
        "mfi_rising": mfi_rising,
    }


def ut_bot_signals(df: pd.DataFrame, key_value: float = 1.0, atr_period: int = 10) -> pd.DataFrame:
    """UT Bot Alerts mantığı: ATR trailing stop + AL/SAT sinyalleri."""
    src = df["Close"].values
    atr = wilder_atr(df, atr_period).values
    n_loss = key_value * atr
    n = len(src)
    stop = np.zeros(n)

    for i in range(n):
        if i == 0 or np.isnan(atr[i]):
            stop[i] = src[i] - n_loss[i] if not np.isnan(n_loss[i]) else src[i]
            continue
        prev = stop[i - 1]
        if src[i] > prev and src[i - 1] > prev:
            stop[i] = max(prev, src[i] - n_loss[i])
        elif src[i] < prev and src[i - 1] < prev:
            stop[i] = min(prev, src[i] + n_loss[i])
        elif src[i] > prev:
            stop[i] = src[i] - n_loss[i]
        else:
            stop[i] = src[i] + n_loss[i]

    pos = np.zeros(n)
    for i in range(1, n):
        if src[i - 1] < stop[i - 1] and src[i] > stop[i - 1]:
            pos[i] = 1
        elif src[i - 1] > stop[i - 1] and src[i] < stop[i - 1]:
            pos[i] = -1
        else:
            pos[i] = pos[i - 1]

    ema = src  # EMA(src, 1) == src
    above = np.zeros(n, dtype=bool)
    below = np.zeros(n, dtype=bool)
    for i in range(1, n):
        above[i] = ema[i - 1] <= stop[i - 1] and ema[i] > stop[i]
        below[i] = stop[i - 1] <= ema[i - 1] and stop[i] > ema[i]

    out = df.copy()
    out["stop"] = stop
    out["atr"] = atr
    out["pos"] = pos
    out["buy"] = (src > stop) & above
    out["sell"] = (src < stop) & below
    return out


def detect_formation(df: pd.DataFrame) -> list:
    formations = []
    close, volume = df["Close"], df["Volume"]
    ema21, ema50 = compute_ema(close, 21), compute_ema(close, 50)
    last_close = close.iloc[-1]
    avg_vol = volume.iloc[-20:].mean()

    a21 = last_close > ema21.iloc[-1]
    a50 = last_close > ema50.iloc[-1]
    cross = ema21.iloc[-1] > ema50.iloc[-1]

    if a21 and a50 and cross:
        formations.append("Yükselen Trend")
    elif not a21 and not a50 and not cross:
        formations.append("Düşen Trend")
    else:
        formations.append("Yatay Piyasa")

    if last_close > df["High"].iloc[-21:-1].max():
        formations.append("Direnç Kırılımı")
    if last_close < df["Low"].iloc[-21:-1].min():
        formations.append("Destek Kırılımı")
    if volume.iloc[-1] > avg_vol * 1.5:
        formations.append("Hacimli Kırılım")
    if ema21.iloc[-2] < ema50.iloc[-2] and ema21.iloc[-1] > ema50.iloc[-1]:
        formations.append("EMA Altın Kesişim")
    if ema21.iloc[-2] > ema50.iloc[-2] and ema21.iloc[-1] < ema50.iloc[-1]:
        formations.append("EMA Ölüm Kesişimi")
    if df["Low"].iloc[-10:].is_monotonic_increasing:
        formations.append("Higher Low")
    if df["High"].iloc[-10:].is_monotonic_decreasing:
        formations.append("Lower High")
    return formations


def compute_score(df: pd.DataFrame) -> dict:
    close, volume = df["Close"], df["Volume"]
    ema21, ema50 = compute_ema(close, 21), compute_ema(close, 50)
    rsi = compute_rsi(close)
    last_close = close.iloc[-1]
    last_rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
    avg_vol = volume.iloc[-20:].mean()

    trend = 25 if (last_close > ema21.iloc[-1] and last_close > ema50.iloc[-1]) else (12 if last_close > ema21.iloc[-1] else 0)
    ema = 20 if ema21.iloc[-1] > ema50.iloc[-1] else 0
    rsi_s = 15 if last_rsi > 55 else (7 if last_rsi > 45 else 0)
    vol = 20 if volume.iloc[-1] > avg_vol else 0
    formations = detect_formation(df)
    form = min(20, len([f for f in formations if f not in ("Yatay Piyasa", "Düşen Trend", "Lower High", "EMA Ölüm Kesişimi", "Destek Kırılımı")]) * 7)
    total = trend + ema + rsi_s + vol + form
    return {"total": total, "trend": trend, "ema": ema, "rsi": rsi_s,
            "volume": vol, "formation": form, "formations": formations,
            "rsi_val": round(last_rsi, 1)}


def system_decision(score: int) -> str:
    if score >= 70:
        return "AL için uygun"
    elif score >= 40:
        return "Bekle / izlemeye değer"
    return "İşleme girmek riskli"


def detect_whale_activity(tickers: list) -> pd.DataFrame:
    """Havuzu tarar; olağandışı hacim + para akışı ile birikim/dağıtım tespiti."""
    rows = []
    prog = st.progress(0.0, text="Para akışı taranıyor...")
    for i, t in enumerate(tickers):
        prog.progress((i + 1) / len(tickers), text=f"İnceleniyor: {t}")
        df = fetch_daily(t, "3mo")
        if df is None or len(df) < 25:
            continue
        rvol = relative_volume(df)
        chg = (df["Close"].iloc[-1] - df["Close"].iloc[-2]) / df["Close"].iloc[-2] * 100
        mfi = compute_mfi(df).iloc[-1]
        mfi = round(float(mfi), 1) if not pd.isna(mfi) else 50.0
        obv = compute_obv(df)
        obv_slope = obv.iloc[-1] - obv.iloc[-6] if len(obv) > 6 else 0  # son 5 gün eğilim
        dollar_vol = df["Close"].iloc[-1] * df["Volume"].iloc[-1]

        # Yorum: birikim mi dağıtım mı?
        if rvol >= 1.5 and chg > 0 and mfi > 55 and obv_slope > 0:
            durum = " Birikim (Accumulation)"
        elif rvol >= 1.5 and chg < 0 and (mfi < 45 or obv_slope < 0):
            durum = " Dağıtım (Distribution)"
        elif rvol >= 2.0:
            durum = " Olağandışı Hacim"
        else:
            durum = "—"

        rows.append({
            "Hisse": t,
            "Durum": durum,
            "Göreli Hacim": round(rvol, 2),
            "Günlük %": round(float(chg), 2),
            "MFI": mfi,
            "OBV Eğilim": "↑ Yukarı" if obv_slope > 0 else ("↓ Aşağı" if obv_slope < 0 else "→"),
            "$ Hacim (M)": round(dollar_vol / 1e6, 1),
            "Fiyat": round(float(df["Close"].iloc[-1]), 2),
        })
    prog.empty()
    return pd.DataFrame(rows)


def detect_downtrend_line(df: pd.DataFrame, lookback: int = 45):
    """Konsolidasyondaki düşen direnç çizgisini (zirve → daha düşük tepe) bulur."""
    if len(df) < 10:
        return None
    gap = 4
    sub = df.iloc[-lookback:]
    highs = sub["High"].values
    idx = sub.index
    p1 = int(np.argmax(highs))                 # en yüksek tepe
    if p1 >= len(highs) - gap - 1:              # tepe çok yakınsa çizgi anlamsız
        return None
    after = highs[p1 + gap:]                     # zirveden en az `gap` mum sonra ikinci tepe
    if len(after) == 0:
        return None
    p2 = p1 + gap + int(np.argmax(after))
    if highs[p2] > highs[p1] or p2 == p1:        # ikinci tepe zirveyi aşmamalı (eşit/düşük olabilir)
        return None
    slope = (highs[p2] - highs[p1]) / (p2 - p1)
    x_end = len(highs) - 1
    y_end = highs[p1] + slope * (x_end - p1)
    return {"x0": idx[p1], "y0": float(highs[p1]),
            "x1": idx[x_end], "y1": float(y_end)}
