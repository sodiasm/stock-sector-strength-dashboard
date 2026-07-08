"""Plotly grafik üreticileri."""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from market_overview.config import C_ACCENT, C_DOWN, C_GOLD, C_PURPLE, C_UP
from market_overview.indicators import compute_ema, compute_rsi
from market_overview.signals import detect_downtrend_line


def make_ut_chart(df: pd.DataFrame, title: str) -> go.Figure:
    ema21 = compute_ema(df["Close"], 21)
    ema50 = compute_ema(df["Close"], 50)
    rsi = compute_rsi(df["Close"])

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        row_heights=[0.6, 0.18, 0.22], vertical_spacing=0.03,
                        subplot_titles=("Fiyat & UT Bot", "Hacim", "RSI"))

    fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"],
                  low=df["Low"], close=df["Close"], name="Fiyat",
                  increasing_line_color=C_UP, decreasing_line_color=C_DOWN,
                  increasing_fillcolor=C_UP, decreasing_fillcolor=C_DOWN), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["stop"], name="UT Stop",
                  line=dict(color=C_PURPLE, width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=ema21, name="EMA21",
                  line=dict(color=C_GOLD, width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=ema50, name="EMA50",
                  line=dict(color=C_ACCENT, width=1)), row=1, col=1)

    buys, sells = df[df["buy"]], df[df["sell"]]
    fig.add_trace(go.Scatter(x=buys.index, y=buys["Low"] * 0.985, mode="markers",
                  name="AL", marker=dict(symbol="triangle-up", size=14, color=C_UP,
                  line=dict(color="white", width=1))), row=1, col=1)
    fig.add_trace(go.Scatter(x=sells.index, y=sells["High"] * 1.015, mode="markers",
                  name="SAT", marker=dict(symbol="triangle-down", size=14, color=C_DOWN,
                  line=dict(color="white", width=1))), row=1, col=1)

    colors = [C_UP if c >= o else C_DOWN for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="Hacim",
                  marker_color=colors, opacity=0.6), row=2, col=1)

    fig.add_trace(go.Scatter(x=df.index, y=rsi, name="RSI",
                  line=dict(color="#ff7043", width=1.4)), row=3, col=1)
    fig.add_hline(y=70, line=dict(color="rgba(234,57,67,0.5)", dash="dash"), row=3, col=1)
    fig.add_hline(y=30, line=dict(color="rgba(22,199,132,0.5)", dash="dash"), row=3, col=1)

    fig.update_layout(title=title, template="plotly_dark",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(13,17,28,1)",
                      height=640, xaxis_rangeslider_visible=False,
                      legend=dict(orientation="h", y=1.02, x=1, xanchor="right"),
                      margin=dict(l=10, r=10, t=50, b=10))
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.05)")
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.05)")
    return fig


def make_equity_chart(equity_curve, index) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=index, y=equity_curve, fill="tozeroy",
                  line=dict(color=C_ACCENT, width=2), name="Portföy"))
    fig.update_layout(title="Portföy Değeri (Equity Curve)", template="plotly_dark",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(13,17,28,1)",
                      height=260, margin=dict(l=10, r=10, t=40, b=10))
    return fig


def make_cloud_chart(df: pd.DataFrame, title: str) -> go.Figure:
    """Qullamaggie tarzı 10/20 EMA bulutu + 50/200 SMA + düşen trend çizgisi grafiği."""
    c = df["Close"]
    ema10, ema20 = compute_ema(c, 10), compute_ema(c, 20)
    sma50 = c.rolling(50).mean()
    sma200 = c.rolling(200).mean()

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.78, 0.22],
                        vertical_spacing=0.04, subplot_titles=(title, "Hacim"))

    # EMA bulutu (10-20 arası dolgu)
    fig.add_trace(go.Scatter(x=df.index, y=ema20, line=dict(width=0), showlegend=False,
                  hoverinfo="skip"), row=1, col=1)
    cloud_up = (ema10 >= ema20).iloc[-1]
    fig.add_trace(go.Scatter(x=df.index, y=ema10, fill="tonexty", name="EMA 10/20 Bulut",
                  line=dict(color="rgba(22,199,132,0.6)", width=1),
                  fillcolor="rgba(22,199,132,0.18)" if cloud_up else "rgba(234,57,67,0.18)"),
                  row=1, col=1)

    fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"],
                  close=df["Close"], name="Fiyat", increasing_line_color=C_UP,
                  decreasing_line_color=C_DOWN, increasing_fillcolor=C_UP,
                  decreasing_fillcolor=C_DOWN), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=sma50, name="SMA 50",
                  line=dict(color=C_ACCENT, width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=sma200, name="SMA 200",
                  line=dict(color="#ef5350", width=1.2)), row=1, col=1)

    # Düşen trend (direnç) çizgisi — TradingView'daki beyaz diyagonal
    dt = detect_downtrend_line(df)
    if dt:
        fig.add_trace(go.Scatter(x=[dt["x0"], dt["x1"]], y=[dt["y0"], dt["y1"]],
                      mode="lines", name="Düşen Trend Çizgisi",
                      line=dict(color="white", width=2, dash="solid")), row=1, col=1)

    colors = [C_UP if cl >= o else C_DOWN for cl, o in zip(df["Close"], df["Open"])]
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="Hacim",
                  marker_color=colors, opacity=0.55), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["Volume"].rolling(50).mean(), name="Hacim Ort.",
                  line=dict(color=C_GOLD, width=1)), row=2, col=1)

    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(13,17,28,1)", height=600, xaxis_rangeslider_visible=False,
                      legend=dict(orientation="h", y=1.03, x=1, xanchor="right", font=dict(size=11)),
                      margin=dict(l=10, r=10, t=50, b=10), hovermode="x unified")
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.05)")
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.04)")
    return fig
