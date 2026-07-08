"""Basit backtest ve trade planı üretimi/gösterimi."""

import numpy as np
import pandas as pd
import streamlit as st

from market_overview.indicators import compute_ema


def backtest(df: pd.DataFrame, initial_cash: float = 10000.0, fee_pct: float = 0.1) -> dict:
    cash, position, entry_price = initial_cash, 0.0, 0.0
    trades, equity_curve = [], []
    fee = fee_pct / 100.0
    closes = df["Close"].values
    buys, sells = df["buy"].values, df["sell"].values
    idx = df.index

    for i in range(len(df)):
        price = closes[i]
        if buys[i] and position == 0:
            qty = (cash * (1 - fee)) / price
            position, entry_price, cash = qty, price, 0.0
            trades.append({"Tarih": idx[i], "Tip": "AL", "Fiyat": round(price, 2),
                           "Adet": round(qty, 4), "P&L %": None})
        elif sells[i] and position > 0:
            cash = position * price * (1 - fee)
            pnl = (price - entry_price) / entry_price * 100
            trades.append({"Tarih": idx[i], "Tip": "SAT", "Fiyat": round(price, 2),
                           "Adet": round(position, 4), "P&L %": round(pnl, 2)})
            position = 0.0
        equity_curve.append(cash + position * price)

    final = cash + position * closes[-1]
    total_ret = (final - initial_cash) / initial_cash * 100
    closed = [t for t in trades if t["Tip"] == "SAT"]
    wins = [t for t in closed if t["P&L %"] and t["P&L %"] > 0]
    win_rate = len(wins) / len(closed) * 100 if closed else 0
    bh_ret = (closes[-1] - closes[0]) / closes[0] * 100
    eq = np.array(equity_curve)
    dd = (eq - np.maximum.accumulate(eq)) / np.maximum.accumulate(eq) * 100
    return {"final_equity": final, "total_return": total_ret, "bh_return": bh_ret,
            "n_trades": len(closed), "win_rate": win_rate,
            "max_dd": dd.min() if len(dd) else 0, "trades": trades,
            "equity_curve": equity_curve, "open_position": position > 0}


def build_trade_plan(df: pd.DataFrame, side: str,
                     account_size: float = 10000.0, risk_pct: float = 1.0) -> dict:
    """
    df: ut_bot_signals çıktısı ('stop' ve 'atr' kolonları olmalı).
    side: 'AL' (long) veya 'SAT' (short).
    Gerçek bir işlemde girilecek tüm parametreleri döner.
    """
    last = df.iloc[-1]
    entry = float(last["Close"])
    atr = float(last["atr"]) if not pd.isna(last["atr"]) else entry * 0.02
    ut_stop = float(last["stop"])

    if side == "AL":   # LONG
        # Stop: UT stop ile ATR bazlı stop'tan hangisi daha koruyucuysa (daha yakın olan değil,
        # mantıklı olan) — burada ikisinin daha düşüğünü alıp makul bir tampon bırakıyoruz.
        atr_stop = entry - 1.5 * atr
        stop = min(ut_stop, atr_stop) if ut_stop < entry else atr_stop
        risk_per_share = max(entry - stop, entry * 0.001)
        tp1 = entry + 1.5 * risk_per_share
        tp2 = entry + 3.0 * risk_per_share
    else:              # SHORT
        atr_stop = entry + 1.5 * atr
        stop = max(ut_stop, atr_stop) if ut_stop > entry else atr_stop
        risk_per_share = max(stop - entry, entry * 0.001)
        tp1 = entry - 1.5 * risk_per_share
        tp2 = entry - 3.0 * risk_per_share

    risk_amount = account_size * risk_pct / 100.0
    shares = risk_amount / risk_per_share if risk_per_share > 0 else 0
    position_value = shares * entry

    # Trend filtresi (yeterli veri varsa EMA50)
    ema50 = compute_ema(df["Close"], 50)
    trend = "—"
    if len(df) >= 50:
        if entry > ema50.iloc[-1] and ema50.iloc[-1] > ema50.iloc[-5]:
            trend = "Yukarı (EMA50 üstünde ve yükseliyor)"
        elif entry < ema50.iloc[-1] and ema50.iloc[-1] < ema50.iloc[-5]:
            trend = "Aşağı (EMA50 altında ve düşüyor)"
        else:
            trend = "Yatay / kararsız"

    # Trend uyumu uyarısı
    aligned = (side == "AL" and "Yukarı" in trend) or (side == "SAT" and "Aşağı" in trend)

    return {
        "side": side,
        "entry": round(entry, 2),
        "stop": round(stop, 2),
        "stop_pct": round((stop - entry) / entry * 100, 2),
        "tp1": round(tp1, 2),
        "tp2": round(tp2, 2),
        "tp1_pct": round((tp1 - entry) / entry * 100, 2),
        "tp2_pct": round((tp2 - entry) / entry * 100, 2),
        "risk_per_share": round(risk_per_share, 2),
        "rr": "1:1.5  /  1:3",
        "shares": int(shares),
        "position_value": round(position_value, 2),
        "risk_amount": round(risk_amount, 2),
        "atr": round(atr, 2),
        "trend": trend,
        "aligned": aligned,
    }


def render_trade_plan(plan: dict):
    """Trade planını Streamlit kartı olarak çizer."""
    side_txt = " LONG (AL)" if plan["side"] == "AL" else " SHORT (SAT)"
    st.markdown(f"##### Trade Planı — {side_txt}")
    c = st.columns(4)
    c[0].metric("Giriş", f"${plan['entry']}")
    c[1].metric(" Stop-Loss", f"${plan['stop']}", delta=f"{plan['stop_pct']}%")
    c[2].metric(" Hedef 1 (1.5R)", f"${plan['tp1']}", delta=f"{plan['tp1_pct']}%")
    c[3].metric(" Hedef 2 (3R)", f"${plan['tp2']}", delta=f"{plan['tp2_pct']}%")

    c2 = st.columns(4)
    c2[0].metric("Pozisyon (lot)", f"{plan['shares']} adet")
    c2[1].metric("Pozisyon Değeri", f"${plan['position_value']:,.0f}")
    c2[2].metric("Riske Atılan", f"${plan['risk_amount']:,.0f}")
    c2[3].metric("Risk/Ödül", plan["rr"])

    if plan["trend"] != "—":
        if plan["aligned"]:
            st.success(f" Trend uyumlu: {plan['trend']} — işlem trend yönünde.")
        else:
            st.warning(f" Trende dikkat: {plan['trend']} — işlemin trende karşı olabilir, risk yüksek.")
    st.caption(f"Hesaplama: ATR ${plan['atr']} • Hisse başı risk ${plan['risk_per_share']} • "
               "Stop'a değerse kaybın 'Riske Atılan' tutarıdır. Bu bir emir değildir, plan şablonudur.")
