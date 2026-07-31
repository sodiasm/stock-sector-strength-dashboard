"""Simple backtest and trade-plan generation/rendering."""

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
            trades.append({"Date": idx[i], "Type": "BUY", "Price": round(price, 2),
                           "Shares": round(qty, 4), "P&L %": None})
        elif sells[i] and position > 0:
            cash = position * price * (1 - fee)
            pnl = (price - entry_price) / entry_price * 100
            trades.append({"Date": idx[i], "Type": "SELL", "Price": round(price, 2),
                           "Shares": round(position, 4), "P&L %": round(pnl, 2)})
            position = 0.0
        equity_curve.append(cash + position * price)

    final = cash + position * closes[-1]
    total_ret = (final - initial_cash) / initial_cash * 100
    closed = [t for t in trades if t["Type"] == "SELL"]
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
    df: ut_bot_signals output ('stop' ve 'atr' kolonlari must be).
    side: 'BUY' (long) or 'SELL' (short).
    Returns all parameters for a real trade plan.
    """
    last = df.iloc[-1]
    entry = float(last["Close"])
    atr = float(last["atr"]) if not pd.isna(last["atr"]) else entry * 0.02
    ut_stop = float(last["stop"])

    if side == "BUY":   # LONG
        # Stop: UT stop ile ATR bazli stop'tan hangisi daha koruyucuysa (daha yakin olan degil,
        # Choose the more conservative stop and leave a reasonable buffer.
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

    # Trend filter when enough data is available for EMA50
    ema50 = compute_ema(df["Close"], 50)
    trend = "—"
    if len(df) >= 50:
        if entry > ema50.iloc[-1] and ema50.iloc[-1] > ema50.iloc[-5]:
            trend = "Up (EMA50 ustunde ve yukseliyor)"
        elif entry < ema50.iloc[-1] and ema50.iloc[-1] < ema50.iloc[-5]:
            trend = "Down (EMA50 altinda ve falling)"
        else:
            trend = "Sideways / uncertain"

    # Trend alignment warning
    aligned = (side == "BUY" and "Up" in trend) or (side == "SELL" and "Down" in trend)

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
    """Render the trade plan as a Streamlit card."""
    side_txt = " LONG (BUY)" if plan["side"] == "BUY" else " SHORT (SELL)"
    st.markdown(f"##### Trade Plan — {side_txt}")
    c = st.columns(4)
    c[0].metric("Entry", f"${plan['entry']}")
    c[1].metric(" Stop-Loss", f"${plan['stop']}", delta=f"{plan['stop_pct']}%")
    c[2].metric(" Target 1 (1.5R)", f"${plan['tp1']}", delta=f"{plan['tp1_pct']}%")
    c[3].metric(" Target 2 (3R)", f"${plan['tp2']}", delta=f"{plan['tp2_pct']}%")

    c2 = st.columns(4)
    c2[0].metric("Position (shares)", f"{plan['shares']} shares")
    c2[1].metric("Position Value", f"${plan['position_value']:,.0f}")
    c2[2].metric("Risk Amount", f"${plan['risk_amount']:,.0f}")
    c2[3].metric("Risk/Reward", plan["rr"])

    if plan["trend"] != "—":
        if plan["aligned"]:
            st.success(f" Trend-aligned: {plan['trend']} — trade with the trend.")
        else:
            st.warning(f" Trend caution: {plan['trend']} — the trade may go against the trend and risk is high.")
    st.caption(f"Calculation: ATR ${plan['atr']} • Stock per-share risk ${plan['risk_per_share']} • "
               "Stop'a degerse kaybin 'Risk Amount' tutaridir. Bu bir emir degildir, plan sablonudur.")
