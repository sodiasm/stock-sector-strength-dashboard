"""Streamlit page and section rendering functions."""

from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from market_overview.breadth import (
    defensive_cyclical,
    distribution_days,
    market_breadth,
    sector_rrg,
)
from market_overview.charts import make_cloud_chart
from market_overview.config import (
    C_ACCENT,
    C_DOWN,
    C_GOLD,
    C_UP,
    GLOBAL_INDICES,
    GLOBAL_REGIONS,
    MACRO_ASSETS,
    MOMENTUM_UNIVERSE,
    NASDAQ100,
    SECTOR_ETFS,
    SP500_UNIVERSE,
)
from market_overview.data import fetch_daily
from market_overview.persistence import save_daily_sector_snapshot
from market_overview.scanners import scan_qullamaggie_yf
from market_overview.signals import detect_setup, explain_trade


def _render_qullamaggie_scan_section():
    """Qullamaggie filter scanner — fully yfinance-based and suitable for publication."""
    st.markdown("### " +  "Qullamaggie Filter Scanner")
    st.caption(
        "Filters: **Price > EMA100 (≈21 weeks) · Price > EMA200 (≈50 weeks) · "
        "1Y > 50% · Volume rising (10d avg > 90d avg) · ADR% > 3.5%** — "
        "Data: Yahoo Finance (yfinance) · 30 min cache")

    universe_options = ["S&P 500 + Momentum (~300)",
                  "Nasdaq-100",
                   "Momentum (fast, 40)"]
    fc = st.columns(4)
    selected_universe = fc[0].selectbox("Universe", universe_options, key="qs_universe")
    q_perf1y  = fc[1].slider("Min. 1Y %", 0, 300, 50, 10, key="qs_perf1y",
                               help=
                                      "1-year performance. Qullamaggie looks for 50%+.")
    q_adr     = fc[2].slider("Min. ADR %", 1.0, 10.0, 3.5, 0.5, key="qs_adr",
                               help=
                                      "Average daily range. 3.5%+ = active.")
    q_cap     = fc[3].slider( "Min. Market Cap ($B)", 0.0, 10.0, 2.0, 0.5,
                               key="qs_cap",
                               help=
                                      "0 = no filter. Prefer 2B+ for large-cap.")

    if selected_universe == universe_options[0]:
        universe = SP500_UNIVERSE
    elif selected_universe == universe_options[1]:
        universe = NASDAQ100
    else:
        universe = MOMENTUM_UNIVERSE

    st.caption(
        f" {len(universe)} stocks will be scanned · First scan ~20-30s (then 30 min cached)")

    if st.button( " Run Qullamaggie Scan", type="primary",
                 use_container_width=True, key="qs_scan_btn"):
        with st.spinner(
                          f"Downloading 1-year data for {len(universe)} stocks…"):
            df_q, count = scan_qullamaggie_yf(universe, float(q_perf1y), float(q_cap), float(q_adr))
            st.session_state["qs_result"] = df_q
            st.session_state["qs_count"]  = count

    df_tv = st.session_state.get("qs_result")
    count  = st.session_state.get("qs_count", 0)

    if df_tv is None:
        st.info( " Press the 'Run Qullamaggie Scan' button.")
        return
    if df_tv.empty:
        st.warning(
                     "No stocks match the filters — lower the thresholds.")
        return

    st.success(
        f" {count} stocks passed the filters · Updated: {pd.Timestamp.now().strftime('%H:%M:%S')}")

    # Top 6 stock cards
    top = df_tv.head(6).to_dict("records")
    for i in range(0, len(top), 3):
        cols = st.columns(3)
        for col, r in zip(cols, top[i:i + 3]):
            day_col  = C_UP if r.get("Daily %", 0) >= 0 else C_DOWN
            rvol_col = C_UP if r.get("RVOL", 1) >= 2 else C_GOLD
            col.markdown(
                f'<div style="background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.3);'
                f'border-radius:12px;padding:14px;margin-bottom:10px;">'
                f'<div style="font-size:1.2rem;font-weight:800;color:#fff;">{r["Ticker"]} '
                f'<span style="font-size:0.85rem;color:{day_col};">{r.get("Daily %",0):+.2f}%</span></div>'
                f'<div style="font-size:0.82rem;color:#d1d5db;margin-top:6px;">'
                f' ${r["Price"]:.2f} &nbsp;|&nbsp; '
                f'<span style="color:{rvol_col};"> RVOL {r.get("RVOL",0):.1f}x</span> &nbsp;|&nbsp; '
                f'ADR {r.get("ADR%",0):.1f}%</div>'
                f'<div style="font-size:0.75rem;color:#6b7280;margin-top:4px;">'
                f'1Y: <b style="color:{C_UP};">{r.get("1Y %",0):+.0f}%</b> &nbsp;·&nbsp; '
                f'EMA100 +{r.get("EMA100 Above %",0):.1f}% · EMA200 +{r.get("EMA200 Above %",0):.1f}%</div>'
                f'<div style="font-size:0.75rem;color:#6b7280;">'
                f'W:{r.get("Weekly %",0):+.1f}% · M:{r.get("Monthly %",0):+.1f}% · '
                f'3M:{r.get("3-Month %",0):+.1f}%</div>'
                f'</div>', unsafe_allow_html=True)

    # Full table
    show_cols = ["Ticker", "Price", "Daily %", "ADR%", "RVOL",
                 "1Y %", "Weekly %", "Monthly %", "3-Month %",
                 "EMA100 Above %", "EMA200 Above %"]
    show_cols = [c for c in show_cols if c in df_tv.columns]
    st.dataframe(
        df_tv[show_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "RVOL": st.column_config.ProgressColumn(min_value=0, max_value=10, format="%.1fx",
                help="Today's volume / 90-day average. >1 = above average."),
            "ADR%": st.column_config.NumberColumn(format="%.1f%%",
                help="Average daily range %. Qullamaggie looks for 3.5%+."),
            "1Y %": st.column_config.NumberColumn(format="%.0f%%"),
            "Daily %": st.column_config.NumberColumn(format="%.2f%%"),
            "Weekly %": st.column_config.NumberColumn(format="%.1f%%"),
            "Monthly %": st.column_config.NumberColumn(format="%.1f%%"),
            "3-Month %": st.column_config.NumberColumn(format="%.1f%%"),
            "EMA100 Above %": st.column_config.NumberColumn(format="+%.1f%%",
                help="Price EMA100 above percentage (≈21 weekly)"),
            "EMA200 Above %": st.column_config.NumberColumn(format="+%.1f%%",
                help="Price EMA200 above percentage (≈50 weekly)"),
        }
    )

    # Chart + trade plan
    picks = df_tv["Ticker"].tolist()
    if picks:
        st.markdown("#### " +  "Stock Chart & Trade Plan")
        sel = st.selectbox( "Select ticker", picks, key="qs_pick_chart")

        sel_row = df_tv[df_tv["Ticker"] == sel]
        if not sel_row.empty:
            r = sel_row.iloc[0]
            close_series = r.get("_close")
            if close_series is not None:
                # fetch full OHLCV data (detect_setup requires Open and Volume)
                full_df = fetch_daily(sel, "1y")
                if full_df is not None and len(full_df) >= 25:
                    setup = detect_setup(full_df)
                    plan  = explain_trade(setup, full_df)

                    if plan:
                        pc1, pc2, pc3, pc4 = st.columns(4)
                        pc1.metric("Setup", setup)
                        pc2.metric( "Entry", f"${plan['entry']}")
                        pc3.metric("Stop", f"${plan['stop']}")
                        pc4.metric("R:R", f"{plan['rr']}:1",
                                   delta= "Good" if plan["rr"] >= 3
                                   else ( "Fair" if plan["rr"] >= 2 else  "Weak"))

                    st.plotly_chart(
                        make_cloud_chart(full_df, f"{sel} — EMA 10/20 + 50/200 MA"),
                        use_container_width=True,
                    )


def _render_daily_commentary(spx_chg: float, vix_chg: float, ndx_chg: float, sec_df):
    """Render a concise technical daily market commentary."""
    date_text = datetime.now().strftime("%d.%m.%Y")

    if spx_chg > 0.3 and vix_chg < 0:
        risk_color, risk_icon, risk_label = C_UP, "", "Risk-On"
        risk_description = (
            f"Indices up (SPX {spx_chg:+.2f}%), VIX down ({vix_chg:+.2f}%). "
            "Risk appetite is on. You can take Qullamaggie setups — with the trend."
        )
        action = "Scan breakout and EMA-pullback setups. Keep stops tight."
    elif spx_chg < -0.3 and vix_chg > 0:
        risk_color, risk_icon, risk_label = C_DOWN, "", "Risk-Off"
        risk_description = (
            f"Indices down (SPX {spx_chg:+.2f}%), VIX up ({vix_chg:+.2f}%). "
            "Institutions are selling. Don't open new positions."
        )
        action = "Tighten stops on existing positions. Hold cash."
    elif abs(spx_chg) <= 0.3:
        risk_color, risk_icon, risk_label = C_GOLD, "",  "Flat"
        risk_description = (
            f"SPX {spx_chg:+.2f}%, Nasdaq {ndx_chg:+.2f}%. "
            "The market is searching for direction. Don't trade without a breakout."
        )
        action = "Scan your watchlist, set breakout orders — don't enter before the trigger."
    else:
        risk_color, risk_icon, risk_label = C_GOLD, "",  "Mixed"
        risk_description = f"SPX {spx_chg:+.2f}%, VIX {vix_chg:+.2f}% — signals conflict."
        action = "Small starter position or watch-and-wait."

    st.markdown(
        f'<div style="background:rgba(255,255,255,0.03);border-left:4px solid {risk_color};'
        f'border-radius:8px;padding:16px 20px;margin-bottom:14px;">'
        f'<div style="font-size:0.75rem;color:#6b7280;margin-bottom:4px;">{date_text}</div>'
        f'<div style="font-size:1.1rem;font-weight:800;color:{risk_color};margin-bottom:6px;">'
        f'{risk_icon} {risk_label}</div>'
        f'<div style="font-size:0.88rem;color:#d1d5db;margin-bottom:8px;">{risk_description}</div>'
        f'<div style="font-size:0.82rem;color:#9ca3af;background:rgba(255,255,255,0.04);'
        f'border-radius:6px;padding:8px 12px;"> <b>{ "What to do:"}</b> {action}</div>'
        f'</div>', unsafe_allow_html=True)

    if sec_df is not None and not sec_df.empty:
        best  = sec_df.iloc[0]
        worst = sec_df.iloc[-1]
        gainers = sec_df[sec_df["Weekly %"] > 0]
        losers    = sec_df[sec_df["Weekly %"] < 0]
        st.markdown(
            '<div style="font-size:0.85rem;color:#9ca3af;padding:6px 0;">'
            +
                f' <b style="color:{C_UP};">{best["Sector"]}</b> strong on the week ({best["Weekly %"]:+.2f}%) — '
                "favor the leaders in this sector. &nbsp;|&nbsp; "
                f' <b style="color:{C_DOWN};">{worst["Sector"]}</b> weak ({worst["Weekly %"]:+.2f}%) — '
                "avoid going long here."
            + f'<br><span style="color:#6b7280;font-size:0.78rem;">'
            f'{len(gainers)} { "sectors"} ↑ · {len(losers)} { "sectors"} ↓</span>'
            f'</div>', unsafe_allow_html=True)

    st.caption(
                 "Auto-generated · Not investment advice.")


def _render_market_health():
    """Decline Radar: market breadth + distribution days + defensive/cyclical ratio,
    with a current interpretation for each."""
    st.markdown("### " +  "Market Health — Decline Radar")
    st.caption(
        "Catches internal deterioration while the index still rises (leading signals). "
        f"~{len(SP500_UNIVERSE)} stocks scanned · first scan ~20-30s (then 30 min cached).")

    if st.button( " Analyze Market Health", key="health_btn"):
        with st.spinner(
                          "Computing breadth, distribution and rotation…"):
            st.session_state["health_res"] = {
                "breadth": market_breadth(tuple(SP500_UNIVERSE)),
                "dist": distribution_days(),
                "dc": defensive_cyclical(),
            }

    res = st.session_state.get("health_res")
    if res is None:
        st.info(
                  " Press 'Analyze Market Health'.")
        return

    # ---- 1) Market breadth ----
    breadth = res.get("breadth")
    if breadth and breadth.get("ma"):
        cols = st.columns(2)
        for col, ma in zip(cols, (50, 200)):
            v = breadth["ma"].get(ma)
            if not v:
                continue
            now, prev = v["now"], v["prev20"]
            color = C_UP if now >= 70 else (C_GOLD if now >= 50 else C_DOWN)
            col.markdown(
                f'<div style="background:rgba(255,255,255,0.03);border:1px solid {color};'
                f'border-radius:12px;padding:14px;text-align:center;">'
                f'<div style="font-size:0.8rem;color:#9ca3af;">{ "Stocks above"} '
                f'{ma}MA { ""}</div>'
                f'<div style="font-size:1.8rem;font-weight:800;color:{color};">{now:.0f}%</div>'
                f'<div style="font-size:0.75rem;color:#6b7280;">'
                f'{ "20d ago"} {prev:.0f}% ({now - prev:+.0f})</div>'
                f'</div>', unsafe_allow_html=True)

        b200 = breadth["ma"].get(200, {}).get("now", 50)
        if b200 >= 70:
            st.success(
                         f" **Healthy participation** — {b200:.0f}% of stocks above 200MA. Broad-based uptrend.")
        elif b200 >= 50:
            st.warning(
                         f" **Watch** — {b200:.0f}% above 200MA (50-70 is a neutral zone).")
        elif b200 >= 30:
            st.error(
                       f" **Weak** — only {b200:.0f}% above 200MA. Bear confirmation (<50).")
        else:
            st.error(
                       f" **Deep decline** — {b200:.0f}% above 200MA (<30). Oversold / capitulation zone.")

        if breadth.get("divergence"):
            st.error(
                " **DIVERGENCE WARNING:** SPX rose over 20 days while breadth fell — "
                "fewer stocks joining the rally. A classic early warning before a top.")

        # 200MA breadth zaman serisi grafigi
        series = breadth["ma"].get(200, {}).get("series")
        if series is not None and len(series) > 20:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=series.index, y=series.values, mode="lines",
                                     line=dict(color=C_ACCENT, width=2), name="200MA breadth"))
            fig.add_hline(y=70, line=dict(color=C_UP, dash="dot", width=1))
            fig.add_hline(y=50, line=dict(color=C_GOLD, dash="dot", width=1))
            fig.add_hline(y=30, line=dict(color=C_DOWN, dash="dot", width=1))
            fig.update_layout(height=200, margin=dict(l=0, r=0, t=20, b=0),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              yaxis=dict(range=[0, 100], color="#6b7280",
                                         gridcolor="rgba(255,255,255,0.05)"),
                              xaxis=dict(color="#6b7280"), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    # ---- 2) Distribution days ----
    dist = res.get("dist")
    if dist:
        c = dist["count"]
        cc = st.columns([1, 3])
        cc[0].metric( "Distribution Days", f"{c}", help= "Institutional selling days in the window")
        with cc[1]:
            if c >= 6:
                st.error(
                           f" **{c} distribution days** — institutions selling hard. Strong top/decline warning.")
            elif c >= 4:
                st.warning(
                             f" **{c} distribution days** — institutional selling building. Be cautious.")
            else:
                st.success(
                             f" **{c} distribution days** — low institutional selling. Healthy.")
        st.caption(
                     "Distribution day = close ≤ -0.2% on higher volume than prior day (SPY, O'Neil).")

    # ---- 3) Defensive / Cyclical ----
    dc = res.get("dc")
    if dc:
        cyc, deff = dc["cyclical_ret20"], dc["defensive_ret20"]
        if dc["risk_on"]:
            st.success(
                f" **Risk-On rotation:** Cyclicals (XLK/XLY/XLI/XLF, {cyc:+.1f}%) beat defensives "
                f"(XLP/XLU/XLV, {deff:+.1f}%). Money moving to risk — healthy.")
        else:
            st.error(
                f" **Risk-Off tilt:** Defensives (XLP/XLU/XLV, {deff:+.1f}%) leading cyclicals "
                f"(XLK/XLY/XLI/XLF, {cyc:+.1f}%). Money fleeing to safety — a pre-decline warning.")
        st.caption(
                     f"XLY/XLP ratio 20-day slope: {dc['ratio_slope20']:+.1f}% "
                     "(positive = risk appetite, negative = flight to safety).")


def _render_rrg():
    """Sector rotation — Relative Rotation Graph (RRG) + money-flow commentary."""
    st.markdown("### " +  "Sector Rotation — RRG")
    st.caption(
        "Each sector ETF vs SPY: strength (RS-Ratio, x) and momentum (RS-Momentum, y). "
        "Rotates clockwise. Center at (100,100). The tail is the last ~8 days' path.")

    if st.button( " Analyze Rotation (RRG)", key="rrg_btn"):
        with st.spinner( "Computing RRG…"):
            st.session_state["rrg_res"] = sector_rrg()

    rrg = st.session_state.get("rrg_res")
    if rrg is None:
        if "rrg_res" in st.session_state:
            st.info( "RRG data unavailable — try again.")
        else:
            st.info( " Press 'Analyze Rotation (RRG)'.")
        return

    quad_color = {"Leading": C_UP, "Weakening": C_GOLD, "Lagging": C_DOWN, "Improving": C_ACCENT}
    quad_tr = {"Leading": "Leading", "Weakening": "Weakening", "Lagging": "Lagging", "Improving": "Improving"}

    xs = [p for d in rrg.values() for p in d["tail_x"]]
    ys = [p for d in rrg.values() for p in d["tail_y"]]
    xpad = max(1.0, (max(xs) - min(xs)) * 0.1)
    ypad = max(1.0, (max(ys) - min(ys)) * 0.1)
    x0, x1 = min(min(xs), 100) - xpad, max(max(xs), 100) + xpad
    y0, y1 = min(min(ys), 100) - ypad, max(max(ys), 100) + ypad

    fig = go.Figure()
    # Quadrant backgrounds
    fig.add_shape(type="rect", x0=100, y0=100, x1=x1, y1=y1, fillcolor="rgba(22,199,132,0.07)", line_width=0)
    fig.add_shape(type="rect", x0=100, y0=y0, x1=x1, y1=100, fillcolor="rgba(240,185,11,0.07)", line_width=0)
    fig.add_shape(type="rect", x0=x0, y0=y0, x1=100, y1=100, fillcolor="rgba(234,57,67,0.07)", line_width=0)
    fig.add_shape(type="rect", x0=x0, y0=100, x1=100, y1=y1, fillcolor="rgba(59,130,246,0.07)", line_width=0)
    fig.add_vline(x=100, line=dict(color="rgba(255,255,255,0.2)", width=1))
    fig.add_hline(y=100, line=dict(color="rgba(255,255,255,0.2)", width=1))
    # Quadrant labels
    fig.add_annotation(x=x1, y=y1, text= "Leading", showarrow=False,
                       xanchor="right", yanchor="top", font=dict(color=C_UP, size=11))
    fig.add_annotation(x=x1, y=y0, text= "Weakening", showarrow=False,
                       xanchor="right", yanchor="bottom", font=dict(color=C_GOLD, size=11))
    fig.add_annotation(x=x0, y=y0, text= "Lagging", showarrow=False,
                       xanchor="left", yanchor="bottom", font=dict(color=C_DOWN, size=11))
    fig.add_annotation(x=x0, y=y1, text= "Improving", showarrow=False,
                       xanchor="left", yanchor="top", font=dict(color=C_ACCENT, size=11))

    for etf, d in rrg.items():
        col = quad_color[d["quadrant"]]
        fig.add_trace(go.Scatter(
            x=d["tail_x"], y=d["tail_y"], mode="lines", line=dict(color=col, width=1.5),
            opacity=0.5, showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(
            x=[d["x"]], y=[d["y"]], mode="markers+text", text=[etf],
            textposition="top center", textfont=dict(color=col, size=11),
            marker=dict(color=col, size=11, line=dict(color="#0b0f1a", width=1)),
            name=etf, showlegend=False,
            hovertemplate=f"{etf} — {d['name']}<br>RS-Ratio %{{x:.1f}}<br>RS-Mom %{{y:.1f}}<extra></extra>"))

    fig.update_layout(height=460, margin=dict(l=0, r=0, t=10, b=0),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      xaxis=dict(range=[x0, x1], title="RS-Ratio", color="#6b7280",
                                 gridcolor="rgba(255,255,255,0.04)", zeroline=False),
                      yaxis=dict(range=[y0, y1], title="RS-Momentum", color="#6b7280",
                                 gridcolor="rgba(255,255,255,0.04)", zeroline=False))
    st.plotly_chart(fig, use_container_width=True)

    # money flow commentary
    by_q = {"Leading": [], "Weakening": [], "Lagging": [], "Improving": []}
    for etf, d in rrg.items():
        by_q[d["quadrant"]].append(f"{d['name']} ({etf})")

    def _join(items):
        return ", ".join(items) if items else  "—"

    st.markdown( "**Where is money rotating?**")
    inflow = by_q["Improving"] + by_q["Leading"]
    outflow = by_q["Weakening"] + by_q["Lagging"]
    st.success(
                 f" **INFLOW (strong/improving):** {_join(inflow)}")
    st.error(
               f" **OUTFLOW (weak/weakening):** {_join(outflow)}")

    for q in ("Leading", "Improving", "Weakening", "Lagging"):
        if by_q[q]:
            label =  q
            hint = {
                "Leading":  "strong + accelerating — leaders",
                "Improving":  "weak but improving — early-entry candidates",
                "Weakening":  "strong but slowing — take-profit zone",
                "Lagging":  "weak + decelerating — avoid",
            }[q]
            st.markdown(f'<span style="color:{quad_color[q]};">●</span> **{label}** '
                        f'<span style="color:#6b7280;font-size:0.85rem;">({hint})</span>: {_join(by_q[q])}',
                        unsafe_allow_html=True)


def page_market_pulse(tickers):
    st.markdown(
        '<div class="page-header">'
        '<h2> ' +  "Market Pulse" + '</h2>'
        '<p>' +
            "S&P 500, VIX, rates, dollar and sector rotation at a glance. "
            "Read the market first — Risk-On or Risk-Off — then plan your trade. "
            "Qullamaggie's first rule: <b>don't trade against the market.</b>"
        + '</p></div>', unsafe_allow_html=True)

    top = st.columns([2, 1, 1])
    top[0].caption( "Last update: " + datetime.now().strftime('%d.%m.%Y %H:%M'))
    if top[1].button( " Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    # Auto-refresh toggle
    auto = top[2].toggle( "⏱ Auto-refresh (60s)", value=False)
    if auto:
        import time as _time
        last = st.session_state.get("_pulse_ts", 0)
        if _time.time() - last > 60:
            st.session_state["_pulse_ts"] = _time.time()
            st.cache_data.clear()
            st.rerun()

    # Cekilemeyen sembolleri say (sessizce yutmak yerine useiciya bildir)
    failed_syms = []

    # ---------- 1) MAKRO TABLO ----------
    st.markdown("### " +  "Daily Macro Summary")
    macro_rows, spx_chg, vix_chg, ndx_chg = [], 0, 0, 0
    for sym, name in MACRO_ASSETS.items():
        df = fetch_daily(sym, "5d")
        if df is None or len(df) < 2:
            failed_syms.append(sym)
            continue
        chg = (df["Close"].iloc[-1] - df["Close"].iloc[-2]) / df["Close"].iloc[-2] * 100
        if sym == "^GSPC": spx_chg = chg
        if sym == "^VIX":  vix_chg = chg
        if sym == "^IXIC": ndx_chg = chg
        macro_rows.append({"Asset":  MACRO_ASSETS[sym], "Price": round(float(df["Close"].iloc[-1]), 2),
                           "Daily %": round(float(chg), 2)})
    if macro_rows:
        cols = st.columns(5)
        for i, r in enumerate(macro_rows):
            cols[i % 5].metric(r["Asset"], f"{r['Price']:,}", f"{r['Daily %']:+.2f}%")

        # Risk-on / risk-off reading
        if spx_chg > 0 and vix_chg < 0:
            st.success(
                " **Risk-On:** Indices up, fear (VIX) down. Positive appetite — long setups favored.")
        elif spx_chg < 0 and vix_chg > 0:
            st.error(
                " **Risk-Off:** Indices down, fear (VIX) up. Be cautious — cash/defensive sectors favored.")
        else:
            st.info(
                " **Mixed:** No clear risk direction; be selective, wait for confirmation.")

    st.divider()

    # ---------- 2) SECTOR ROTATION ----------
    st.markdown("### " +
                           "Sector Rotation — Where Is Money Flowing?")
    sec_rows = []
    for sym, name in SECTOR_ETFS.items():
        df = fetch_daily(sym, "1mo")
        if df is None or len(df) < 6:
            failed_syms.append(sym)
            continue
        d1 = (df["Close"].iloc[-1] - df["Close"].iloc[-2]) / df["Close"].iloc[-2] * 100
        d5 = (df["Close"].iloc[-1] - df["Close"].iloc[-6]) / df["Close"].iloc[-6] * 100
        sec_rows.append({"Sector":  SECTOR_ETFS[sym], "Symbol": sym,
                        "Daily %": round(float(d1), 2), "Weekly %": round(float(d5), 2)})

    sec_df = pd.DataFrame()
    if sec_rows:
        sec_df = pd.DataFrame(sec_rows).sort_values("Weekly %", ascending=False)
        try:
            save_daily_sector_snapshot(sec_df)
        except (OSError, ValueError) as exc:
            st.warning(
                         f"Could not save the daily sector snapshot: {exc}")
        best = sec_df.iloc[0]; worst = sec_df.iloc[-1]
        st.markdown(
            f" **{ 'Inflow'}:** {best['Sector']} "
            f"({ 'weekly'} {best['Weekly %']:+}%) &nbsp;|&nbsp; "
            f" **{ 'Outflow'}:** {worst['Sector']} "
            f"({ 'weekly'} {worst['Weekly %']:+}%)")

        # Card grid — all sectors sorted from strongest to weakest by weekly return.
        per_row = 4
        recs = sec_df.to_dict("records")
        for start in range(0, len(recs), per_row):
            cols = st.columns(per_row)
            for col, r in zip(cols, recs[start:start + per_row]):
                wk = r["Weekly %"]
                # Renk: guclu yesilden guclu kirmiziya
                if wk >= 2: bg, brd = "rgba(22,199,132,0.22)", C_UP
                elif wk >= 0: bg, brd = "rgba(22,199,132,0.10)", C_UP
                elif wk > -2: bg, brd = "rgba(234,57,67,0.10)", C_DOWN
                else: bg, brd = "rgba(234,57,67,0.22)", C_DOWN
                dcol = C_UP if r["Daily %"] >= 0 else C_DOWN
                wcol = C_UP if wk >= 0 else C_DOWN
                col.markdown(
                    f'<div style="background:{bg};border:1px solid {brd};border-radius:12px;'
                    f'padding:12px;text-align:center;margin-bottom:10px;min-height:108px;">'
                    f'<div style="font-size:0.9rem;font-weight:700;color:#eee;">{r["Sector"]}</div>'
                    f'<div style="font-size:0.7rem;color:#888;">{r["Symbol"]}</div>'
                    f'<div style="font-size:1.4rem;font-weight:800;color:{wcol};margin-top:6px;">{wk:+.2f}%</div>'
                    f'<div style="font-size:0.72rem;color:#999;">{ "weekly"}</div>'
                    f'<div style="font-size:0.8rem;color:{dcol};margin-top:2px;">{ "today"} {r["Daily %"]:+.2f}%</div>'
                    f'</div>', unsafe_allow_html=True)

    st.divider()

    # ---------- 2b) GLOBAL MARKETS ----------
    st.markdown("### " +  "Global Markets")
    for region, indices in GLOBAL_INDICES.items():
        st.markdown(f"**{GLOBAL_REGIONS[region]}**")
        cols = st.columns(len(indices))
        for col, (sym, meta) in zip(cols, indices.items()):
            gdf = fetch_daily(sym, "5d")
            if gdf is None or len(gdf) < 2:
                failed_syms.append(sym)
                col.markdown(
                    f'<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);'
                    f'border-radius:10px;padding:10px;text-align:center;margin-bottom:8px;">'
                    f'<div style="font-size:0.8rem;color:#6b7280;">{meta["country"]} {meta["name"]}</div>'
                    f'<div style="font-size:0.85rem;color:#4b5563;">{ "No data"}</div>'
                    f'</div>', unsafe_allow_html=True)
                continue
            price = float(gdf["Close"].iloc[-1])
            d1    = (price - float(gdf["Close"].iloc[-2])) / float(gdf["Close"].iloc[-2]) * 100
            wk    = (price - float(gdf["Close"].iloc[0])) / float(gdf["Close"].iloc[0]) * 100 if len(gdf) >= 5 else d1
            col_d = C_UP if d1 >= 0 else C_DOWN
            bg    = "rgba(22,199,132,0.10)" if d1 >= 0 else "rgba(234,57,67,0.10)"
            brd   = C_UP if d1 >= 0 else C_DOWN
            col.markdown(
                f'<div style="background:{bg};border:1px solid {brd};border-radius:10px;'
                f'padding:10px;text-align:center;margin-bottom:8px;">'
                f'<div style="font-size:0.72rem;color:#9ca3af;">{meta["country"]} {meta["name"]}</div>'
                f'<div style="font-size:1rem;font-weight:800;color:{col_d};margin:3px 0;">{d1:+.2f}%</div>'
                f'<div style="font-size:0.68rem;color:#6b7280;">{ "weekly"} {wk:+.1f}%</div>'
                f'</div>', unsafe_allow_html=True)

    # Symbols that failed to load; keep failures visible instead of silently skipping them.
    if failed_syms:
        _syms = f"{', '.join(failed_syms[:12])}{'…' if len(failed_syms) > 12 else ''}"
        st.info(
            f" {len(failed_syms)} symbols failed to load: {_syms} "
            "— Yahoo Finance may be temporarily unavailable; try 'Refresh'.")

    st.divider()

    # ---------- 3) MARKET REGIME INDICATOR ----------
    st.markdown("### " +  "Market Regime Indicator")
    spx_1y = fetch_daily("^GSPC", "1y")
    if spx_1y is not None and len(spx_1y) >= 200:
        spx_price = float(spx_1y["Close"].iloc[-1])
        spx_ma200 = float(spx_1y["Close"].rolling(200).mean().iloc[-1])
        diff_pct = (spx_price - spx_ma200) / spx_ma200 * 100
        _stats = (f'<div style="font-size:0.82rem;color:#9ca3af;margin-top:6px;">'
                  f'SPX: ${spx_price:,.0f} · 200 MA: ${spx_ma200:,.0f} · '
                  f'{ "Diff"}: {diff_pct:+.1f}%</div>')
        if diff_pct > 1.0:
            st.markdown(
                '<div style="background:rgba(22,199,132,0.15);border:2px solid #16c784;border-radius:14px;'
                'padding:18px 24px;text-align:center;font-size:1.1rem;font-weight:700;color:#16c784;">'
                +
                    " BULL REGIME — SPX above its 200-day MA. Scan for long setups."
                + _stats + '</div>', unsafe_allow_html=True)
        elif diff_pct < -1.0:
            st.markdown(
                '<div style="background:rgba(234,57,67,0.15);border:2px solid #ea3943;border-radius:14px;'
                'padding:18px 24px;text-align:center;font-size:1.1rem;font-weight:700;color:#ea3943;">'
                +
                    " BEAR REGIME — SPX below its 200-day MA. Hold cash, consider shorts."
                + _stats + '</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                '<div style="background:rgba(240,185,11,0.12);border:2px solid #f0b90b;border-radius:14px;'
                'padding:18px 24px;text-align:center;font-size:1.1rem;font-weight:700;color:#f0b90b;">'
                +
                    " TRANSITION — SPX at its 200 MA. Be careful."
                + _stats + '</div>', unsafe_allow_html=True)
    else:
        st.caption( "SPX 1y data unavailable.")

    st.divider()

    # ---------- 4) VIX TREND GRAFIGI ----------
    st.markdown("### " +  "VIX — Fear Index (5 Days)")
    vix_5d = fetch_daily("^VIX", "5d")
    if vix_5d is not None and len(vix_5d) >= 2:
        vix_now = float(vix_5d["Close"].iloc[-1])
        vix_prev = float(vix_5d["Close"].iloc[-2])
        vix_delta = vix_now - vix_prev
        fig_vix = go.Figure()
        fig_vix.add_trace(go.Scatter(
            x=vix_5d.index, y=vix_5d["Close"],
            mode="lines+markers", line=dict(color="#ea3943", width=2),
            name="VIX"
        ))
        fig_vix.update_layout(
            height=200, margin=dict(l=0, r=0, t=20, b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False, color="#6b7280"),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", color="#6b7280"),
            showlegend=False,
        )
        vix_col1, vix_col2 = st.columns([3, 1])
        with vix_col1:
            st.plotly_chart(fig_vix, use_container_width=True)
        with vix_col2:
            st.metric( "VIX Now", f"{vix_now:.2f}", f"{vix_delta:+.2f}")
            if vix_now < 15:
                st.caption( " Low fear — market calm")
            elif vix_now < 25:
                st.caption( " Normal fear level")
            elif vix_now < 35:
                st.caption( " High fear — caution")
            else:
                st.caption( " Panic zone — opportunity?")

    st.divider()

    # ---------- 5) MARKET LEADERS ----------
    LEADING_STOCKS = ["NVDA", "META", "TSLA", "AMZN", "AAPL", "MSFT"]
    st.markdown("### " +
                           "Market Leaders — Barometer Stocks")
    lead_cols = st.columns(len(LEADING_STOCKS))
    for col, sym in zip(lead_cols, LEADING_STOCKS):
        ldf = fetch_daily(sym, "5d")
        if ldf is not None and len(ldf) >= 2:
            price_now = float(ldf["Close"].iloc[-1])
            daily_chg = (price_now - float(ldf["Close"].iloc[-2])) / float(ldf["Close"].iloc[-2]) * 100
            weekly_chg = (price_now - float(ldf["Close"].iloc[0])) / float(ldf["Close"].iloc[0]) * 100
            col.metric(
                sym,
                f"${price_now:.2f}",
                f"{ 'Day'} {daily_chg:+.1f}% · { 'Wk'} {weekly_chg:+.1f}%"
            )
        else:
            col.caption(f"{sym}: { 'no data'}")

    st.divider()

    st.divider()

    # ---------- 7d) MARKET HEALTH (DECLINE RADAR) ----------
    _render_market_health()

    st.divider()

    # ---------- 7e) SECTOR ROTATION (RRG) ----------
    _render_rrg()

    st.divider()

    # ---------- 8) DAILY COMMENTARY ----------
    st.markdown("### " +  "Daily Commentary")
    _render_daily_commentary(spx_chg, vix_chg, ndx_chg, sec_df)

    st.divider()
