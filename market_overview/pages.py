"""Streamlit sayfa/bölüm render fonksiyonları."""

from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

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
    MACRO_ASSETS,
    MOMENTUM_UNIVERSE,
    NASDAQ100,
    SECTOR_ETFS,
    SP500_UNIVERSE,
)
from market_overview.data import fetch_daily, finra_short_volume, options_flow
from market_overview.i18n import L
from market_overview.scanners import scan_qullamaggie_yf
from market_overview.signals import detect_setup, explain_trade


def _render_qullamaggie_scan_section():
    """Qullamaggie filtre tarayıcısı — tamamen yfinance tabanlı, yayın için yasal."""
    st.markdown("### " + L("Qullamaggie Filtre Tarayıcısı", "Qullamaggie Filter Scanner"))
    st.caption(L(
        "Filtreler: **Fiyat > EMA100 (≈21 haftalık) · Fiyat > EMA200 (≈50 haftalık) · "
        "1Y > 50% · Hacim artıyor (10G ort > 90G ort) · ADR% > 3.5%** — "
        "Veri: Yahoo Finance (yfinance) · 30 dk cache",
        "Filters: **Price > EMA100 (≈21 weeks) · Price > EMA200 (≈50 weeks) · "
        "1Y > 50% · Volume rising (10d avg > 90d avg) · ADR% > 3.5%** — "
        "Data: Yahoo Finance (yfinance) · 30 min cache"))

    evren_opts = [L("S&P500 + Momentum (~300)", "S&P 500 + Momentum (~300)"),
                  "Nasdaq-100",
                  L("Momentum (hızlı, 40)", "Momentum (fast, 40)")]
    fc = st.columns(4)
    q_evren   = fc[0].selectbox(L("Evren", "Universe"), evren_opts, key="qs_evren")
    q_perf1y  = fc[1].slider("Min. 1Y %", 0, 300, 50, 10, key="qs_perf1y",
                               help=L("1 yıllık performans. Qullamaggie 50%+ arar.",
                                      "1-year performance. Qullamaggie looks for 50%+."))
    q_adr     = fc[2].slider("Min. ADR %", 1.0, 10.0, 3.5, 0.5, key="qs_adr",
                               help=L("Ortalama günlük hareket. 3.5%+ = hareketli.",
                                      "Average daily range. 3.5%+ = active."))
    q_cap     = fc[3].slider(L("Min. Piyasa Değ. ($B)", "Min. Market Cap ($B)"), 0.0, 10.0, 2.0, 0.5,
                               key="qs_cap",
                               help=L("0 = filtre yok. Büyük para için 2B+ tercih.",
                                      "0 = no filter. Prefer 2B+ for large-cap."))

    if q_evren == evren_opts[0]:
        universe = SP500_UNIVERSE
    elif q_evren == evren_opts[1]:
        universe = NASDAQ100
    else:
        universe = MOMENTUM_UNIVERSE

    st.caption(L(
        f" {len(universe)} hisse taranacak · İlk tarama ~20-30 sn sürer (sonra 30 dk cache'li)",
        f" {len(universe)} stocks will be scanned · First scan ~20-30s (then 30 min cached)"))

    if st.button(L(" Qullamaggie Tara", " Run Qullamaggie Scan"), type="primary",
                 use_container_width=True, key="qs_scan_btn"):
        with st.spinner(L(f"{len(universe)} hisse için 1 yıllık veri indiriliyor…",
                          f"Downloading 1-year data for {len(universe)} stocks…")):
            df_q, count = scan_qullamaggie_yf(universe, float(q_perf1y), float(q_cap), float(q_adr))
            st.session_state["qs_result"] = df_q
            st.session_state["qs_count"]  = count

    df_tv = st.session_state.get("qs_result")
    count  = st.session_state.get("qs_count", 0)

    if df_tv is None:
        st.info(L(" 'Qullamaggie Tara' butonuna bas.", " Press the 'Run Qullamaggie Scan' button."))
        return
    if df_tv.empty:
        st.warning(L("Filtrelerle eşleşen hisse yok — eşikleri düşür.",
                     "No stocks match the filters — lower the thresholds."))
        return

    st.success(L(
        f" {count} hisse filtreden geçti · Güncelleme: {pd.Timestamp.now().strftime('%H:%M:%S')}",
        f" {count} stocks passed the filters · Updated: {pd.Timestamp.now().strftime('%H:%M:%S')}"))

    # En güçlü 6 hisse kart
    top = df_tv.head(6).to_dict("records")
    for i in range(0, len(top), 3):
        cols = st.columns(3)
        for col, r in zip(cols, top[i:i + 3]):
            day_col  = C_UP if r.get("Günlük %", 0) >= 0 else C_DOWN
            rvol_col = C_UP if r.get("RVOL", 1) >= 2 else C_GOLD
            col.markdown(
                f'<div style="background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.3);'
                f'border-radius:12px;padding:14px;margin-bottom:10px;">'
                f'<div style="font-size:1.2rem;font-weight:800;color:#fff;">{r["Ticker"]} '
                f'<span style="font-size:0.85rem;color:{day_col};">{r.get("Günlük %",0):+.2f}%</span></div>'
                f'<div style="font-size:0.82rem;color:#d1d5db;margin-top:6px;">'
                f' ${r["Fiyat"]:.2f} &nbsp;|&nbsp; '
                f'<span style="color:{rvol_col};"> RVOL {r.get("RVOL",0):.1f}x</span> &nbsp;|&nbsp; '
                f'ADR {r.get("ADR%",0):.1f}%</div>'
                f'<div style="font-size:0.75rem;color:#6b7280;margin-top:4px;">'
                f'1Y: <b style="color:{C_UP};">{r.get("1Y %",0):+.0f}%</b> &nbsp;·&nbsp; '
                f'EMA100 +{r.get("EMA100 ↑%",0):.1f}% · EMA200 +{r.get("EMA200 ↑%",0):.1f}%</div>'
                f'<div style="font-size:0.75rem;color:#6b7280;">'
                f'W:{r.get("Haftalık %",0):+.1f}% · M:{r.get("Aylık %",0):+.1f}% · '
                f'3M:{r.get("3 Aylık %",0):+.1f}%</div>'
                f'</div>', unsafe_allow_html=True)

    # Tam tablo
    show_cols = ["Ticker", "Fiyat", "Günlük %", "ADR%", "RVOL",
                 "1Y %", "Haftalık %", "Aylık %", "3 Aylık %",
                 "EMA100 ↑%", "EMA200 ↑%"]
    show_cols = [c for c in show_cols if c in df_tv.columns]
    st.dataframe(
        df_tv[show_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "RVOL": st.column_config.ProgressColumn(min_value=0, max_value=10, format="%.1fx",
                help="Bugünkü hacim / 90G ort. >1 = ortalamanın üzerinde."),
            "ADR%": st.column_config.NumberColumn(format="%.1f%%",
                help="Ortalama günlük hareket %. Qullamaggie 3.5%+ arar."),
            "1Y %": st.column_config.NumberColumn(format="%.0f%%"),
            "Günlük %": st.column_config.NumberColumn(format="%.2f%%"),
            "Haftalık %": st.column_config.NumberColumn(format="%.1f%%"),
            "Aylık %": st.column_config.NumberColumn(format="%.1f%%"),
            "3 Aylık %": st.column_config.NumberColumn(format="%.1f%%"),
            "EMA100 ↑%": st.column_config.NumberColumn(format="+%.1f%%",
                help="Fiyatın EMA100 üzerinde yüzdesi (≈21 haftalık)"),
            "EMA200 ↑%": st.column_config.NumberColumn(format="+%.1f%%",
                help="Fiyatın EMA200 üzerinde yüzdesi (≈50 haftalık)"),
        }
    )

    # Grafik + trade planı
    picks = df_tv["Ticker"].tolist()
    if picks:
        st.markdown("#### " + L("Hisse Grafiği & Trade Planı", "Stock Chart & Trade Plan"))
        sel = st.selectbox(L("Hisse seç", "Select ticker"), picks, key="qs_pick_chart")

        sel_row = df_tv[df_tv["Ticker"] == sel]
        if not sel_row.empty:
            r = sel_row.iloc[0]
            close_series = r.get("_close")
            if close_series is not None:
                # fetch_daily ile tam OHLCV verisi çek (detect_setup Open+Volume gerektirir)
                full_df = fetch_daily(sel, "1y")
                if full_df is not None and len(full_df) >= 25:
                    setup = detect_setup(full_df)
                    plan  = explain_trade(setup, full_df)

                    if plan:
                        pc1, pc2, pc3, pc4 = st.columns(4)
                        pc1.metric("Setup", setup)
                        pc2.metric(L("Giriş", "Entry"), f"${plan['entry']}")
                        pc3.metric("Stop", f"${plan['stop']}")
                        pc4.metric("R:R", f"{plan['rr']}:1",
                                   delta=L("İyi", "Good") if plan["rr"] >= 3
                                   else (L("Orta", "Fair") if plan["rr"] >= 2 else L("Zayıf", "Weak")))

                    st.plotly_chart(
                        make_cloud_chart(full_df, f"{sel} — EMA 10/20 + 50/200 MA"),
                        use_container_width=True,
                    )


def _render_daily_commentary(spx_chg: float, vix_chg: float, ndx_chg: float, sec_df):
    """Günün piyasa yorumunu sade-teknik dille gösterir."""
    tarih = datetime.now().strftime("%d.%m.%Y")

    if spx_chg > 0.3 and vix_chg < 0:
        risk_renk, risk_ikon, risk_metin = C_UP, "", "Risk-On"
        risk_aciklama = L(
            f"Endeksler yukarı (SPX {spx_chg:+.2f}%), VIX aşağı ({vix_chg:+.2f}%). "
            "Piyasa iştahlı. Qullamaggie setuplarına girebilirsin — trend yönünde.",
            f"Indices up (SPX {spx_chg:+.2f}%), VIX down ({vix_chg:+.2f}%). "
            "Risk appetite is on. You can take Qullamaggie setups — with the trend.")
        eylem = L("Kırılım ve EMA geri çekilme setuplarını tara. Stop'ları sıkı tut.",
                  "Scan breakout and EMA-pullback setups. Keep stops tight.")
    elif spx_chg < -0.3 and vix_chg > 0:
        risk_renk, risk_ikon, risk_metin = C_DOWN, "", "Risk-Off"
        risk_aciklama = L(
            f"Endeksler aşağı (SPX {spx_chg:+.2f}%), VIX yukarı ({vix_chg:+.2f}%). "
            "Kurumlar satıyor. Yeni pozisyon açma.",
            f"Indices down (SPX {spx_chg:+.2f}%), VIX up ({vix_chg:+.2f}%). "
            "Institutions are selling. Don't open new positions.")
        eylem = L("Mevcut pozisyonların stopunu sıkılaştır. Nakit beklet.",
                  "Tighten stops on existing positions. Hold cash.")
    elif abs(spx_chg) <= 0.3:
        risk_renk, risk_ikon, risk_metin = C_GOLD, "", L("Durağan", "Flat")
        risk_aciklama = L(
            f"SPX {spx_chg:+.2f}%, Nasdaq {ndx_chg:+.2f}%. "
            "Piyasa yön arıyor. Kırılım olmadan işlem açma.",
            f"SPX {spx_chg:+.2f}%, Nasdaq {ndx_chg:+.2f}%. "
            "The market is searching for direction. Don't trade without a breakout.")
        eylem = L("Watchlist tara, kırılım emri koy — tetik düşmeden girme.",
                  "Scan your watchlist, set breakout orders — don't enter before the trigger.")
    else:
        risk_renk, risk_ikon, risk_metin = C_GOLD, "", L("Karışık", "Mixed")
        risk_aciklama = L(f"SPX {spx_chg:+.2f}%, VIX {vix_chg:+.2f}% — sinyal çelişiyor.",
                          f"SPX {spx_chg:+.2f}%, VIX {vix_chg:+.2f}% — signals conflict.")
        eylem = L("Küçük deneme pozisyonu veya izle-bekle.",
                  "Small starter position or watch-and-wait.")

    st.markdown(
        f'<div style="background:rgba(255,255,255,0.03);border-left:4px solid {risk_renk};'
        f'border-radius:8px;padding:16px 20px;margin-bottom:14px;">'
        f'<div style="font-size:0.75rem;color:#6b7280;margin-bottom:4px;">{tarih}</div>'
        f'<div style="font-size:1.1rem;font-weight:800;color:{risk_renk};margin-bottom:6px;">'
        f'{risk_ikon} {risk_metin}</div>'
        f'<div style="font-size:0.88rem;color:#d1d5db;margin-bottom:8px;">{risk_aciklama}</div>'
        f'<div style="font-size:0.82rem;color:#9ca3af;background:rgba(255,255,255,0.04);'
        f'border-radius:6px;padding:8px 12px;"> <b>{L("Ne yapmalısın:", "What to do:")}</b> {eylem}</div>'
        f'</div>', unsafe_allow_html=True)

    if sec_df is not None and not sec_df.empty:
        best  = sec_df.iloc[0]
        worst = sec_df.iloc[-1]
        yukselenler = sec_df[sec_df["Haftalık %"] > 0]
        dusenler    = sec_df[sec_df["Haftalık %"] < 0]
        st.markdown(
            '<div style="font-size:0.85rem;color:#9ca3af;padding:6px 0;">'
            + L(
                f' <b style="color:{C_UP};">{best["Sektör"]}</b> haftalık güçlü ({best["Haftalık %"]:+.2f}%) — '
                "bu sektördeki lider hisselere öncelik ver. &nbsp;|&nbsp; "
                f' <b style="color:{C_DOWN};">{worst["Sektör"]}</b> zayıf ({worst["Haftalık %"]:+.2f}%) — '
                "bu sektörde long açmaktan kaçın.",
                f' <b style="color:{C_UP};">{best["Sektör"]}</b> strong on the week ({best["Haftalık %"]:+.2f}%) — '
                "favor the leaders in this sector. &nbsp;|&nbsp; "
                f' <b style="color:{C_DOWN};">{worst["Sektör"]}</b> weak ({worst["Haftalık %"]:+.2f}%) — '
                "avoid going long here.")
            + f'<br><span style="color:#6b7280;font-size:0.78rem;">'
            f'{len(yukselenler)} {L("sektör", "sectors")} ↑ · {len(dusenler)} {L("sektör", "sectors")} ↓</span>'
            f'</div>', unsafe_allow_html=True)

    st.caption(L("Otomatik üretildi · Yatırım tavsiyesi değildir.",
                 "Auto-generated · Not investment advice."))


def _render_market_health():
    """Düşüş radarı: market breadth + dağıtım günleri + savunma/döngüsel oranı,
    her biri için o güne özel yorumla."""
    st.markdown("### " + L("Piyasa Sağlığı — Düşüş Radarı", "Market Health — Decline Radar"))
    st.caption(L(
        "Endeks yükselirken içeride bozulmayı yakalar (öncü sinyaller). "
        f"~{len(SP500_UNIVERSE)} hisse taranır · ilk tarama ~20-30 sn (sonra 30 dk cache).",
        "Catches internal deterioration while the index still rises (leading signals). "
        f"~{len(SP500_UNIVERSE)} stocks scanned · first scan ~20-30s (then 30 min cached)."))

    if st.button(L(" Piyasa Sağlığını Analiz Et", " Analyze Market Health"), key="health_btn"):
        with st.spinner(L("Breadth, dağıtım ve rotasyon hesaplanıyor…",
                          "Computing breadth, distribution and rotation…")):
            st.session_state["health_res"] = {
                "breadth": market_breadth(tuple(SP500_UNIVERSE)),
                "dist": distribution_days(),
                "dc": defensive_cyclical(),
            }

    res = st.session_state.get("health_res")
    if res is None:
        st.info(L(" 'Piyasa Sağlığını Analiz Et' butonuna bas.",
                  " Press 'Analyze Market Health'."))
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
                f'<div style="font-size:0.8rem;color:#9ca3af;">{L("Hisselerin", "Stocks above")} '
                f'{ma}MA {L("üstünde", "")}</div>'
                f'<div style="font-size:1.8rem;font-weight:800;color:{color};">{now:.0f}%</div>'
                f'<div style="font-size:0.75rem;color:#6b7280;">'
                f'{L("20g önce", "20d ago")} {prev:.0f}% ({now - prev:+.0f})</div>'
                f'</div>', unsafe_allow_html=True)

        b200 = breadth["ma"].get(200, {}).get("now", 50)
        if b200 >= 70:
            st.success(L(f" **Sağlıklı katılım** — hisselerin %{b200:.0f}'i 200MA üstünde. Geniş tabanlı yükseliş.",
                         f" **Healthy participation** — {b200:.0f}% of stocks above 200MA. Broad-based uptrend."))
        elif b200 >= 50:
            st.warning(L(f" **İzlemeye değer** — %{b200:.0f} 200MA üstünde (50-70 arası nötr bölge).",
                         f" **Watch** — {b200:.0f}% above 200MA (50-70 is a neutral zone)."))
        elif b200 >= 30:
            st.error(L(f" **Zayıf** — sadece %{b200:.0f} 200MA üstünde. Ayı piyasası teyidi (<50).",
                       f" **Weak** — only {b200:.0f}% above 200MA. Bear confirmation (<50)."))
        else:
            st.error(L(f" **Derin düşüş** — %{b200:.0f} 200MA üstünde (<30). Aşırı satım / kapitülasyon bölgesi.",
                       f" **Deep decline** — {b200:.0f}% above 200MA (<30). Oversold / capitulation zone."))

        if breadth.get("divergence"):
            st.error(L(
                " **DIVERGENCE UYARISI:** Endeks (SPX) 20 günde yükselirken breadth düşüyor — "
                "ralliye az hisse katılıyor. Klasik tepe öncesi erken uyarı.",
                " **DIVERGENCE WARNING:** SPX rose over 20 days while breadth fell — "
                "fewer stocks joining the rally. A classic early warning before a top."))

        # 200MA breadth zaman serisi grafiği
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

    # ---- 2) Dağıtım günleri ----
    dist = res.get("dist")
    if dist:
        c = dist["count"]
        cc = st.columns([1, 3])
        cc[0].metric(L("Dağıtım Günü", "Distribution Days"), f"{c}", help=L(
            f"Son {dist['lookback']} seansta kurumsal satış günü", "Institutional selling days in the window"))
        with cc[1]:
            if c >= 6:
                st.error(L(f" **{c} dağıtım günü** — kurumlar agresif satıyor. Güçlü tepe/düşüş uyarısı.",
                           f" **{c} distribution days** — institutions selling hard. Strong top/decline warning."))
            elif c >= 4:
                st.warning(L(f" **{c} dağıtım günü** — kurumsal satış birikiyor. Dikkatli ol.",
                             f" **{c} distribution days** — institutional selling building. Be cautious."))
            else:
                st.success(L(f" **{c} dağıtım günü** — kurumsal satış baskısı düşük. Sağlıklı.",
                             f" **{c} distribution days** — low institutional selling. Healthy."))
        st.caption(L("Dağıtım günü = kapanış ≤ -%0.2 ve hacim önceki günden yüksek (SPY, O'Neil).",
                     "Distribution day = close ≤ -0.2% on higher volume than prior day (SPY, O'Neil)."))

    # ---- 3) Savunma / Döngüsel ----
    dc = res.get("dc")
    if dc:
        cyc, deff = dc["cyclical_ret20"], dc["defensive_ret20"]
        if dc["risk_on"]:
            st.success(L(
                f" **Risk-On rotasyonu:** Döngüseller (XLK/XLY/XLI/XLF, {cyc:+.1f}%) savunmayı "
                f"(XLP/XLU/XLV, {deff:+.1f}%) yeniyor. Para riske dönüyor — sağlıklı.",
                f" **Risk-On rotation:** Cyclicals (XLK/XLY/XLI/XLF, {cyc:+.1f}%) beat defensives "
                f"(XLP/XLU/XLV, {deff:+.1f}%). Money moving to risk — healthy."))
        else:
            st.error(L(
                f" **Risk-Off eğilimi:** Savunma sektörleri (XLP/XLU/XLV, {deff:+.1f}%) döngüselleri "
                f"(XLK/XLY/XLI/XLF, {cyc:+.1f}%) geçiyor. Para güvenliğe kaçıyor — düşüş öncesi uyarı.",
                f" **Risk-Off tilt:** Defensives (XLP/XLU/XLV, {deff:+.1f}%) leading cyclicals "
                f"(XLK/XLY/XLI/XLF, {cyc:+.1f}%). Money fleeing to safety — a pre-decline warning."))
        st.caption(L(f"XLY/XLP oranı 20 günlük eğim: {dc['ratio_slope20']:+.1f}% "
                     "(pozitif = risk iştahı, negatif = savunmaya kaçış).",
                     f"XLY/XLP ratio 20-day slope: {dc['ratio_slope20']:+.1f}% "
                     "(positive = risk appetite, negative = flight to safety)."))


def _render_rrg():
    """Sektör rotasyonu — Relative Rotation Graph (RRG) + para nereye kayıyor yorumu."""
    st.markdown("### " + L("Sektör Rotasyonu — RRG", "Sector Rotation — RRG"))
    st.caption(L(
        "Her sektör ETF'i SPY'a karşı: güç (RS-Ratio, yatay) ve ivme (RS-Momentum, dikey). "
        "Saat yönünde döner. Merkez (100,100). Kuyruk son ~8 günün yolu.",
        "Each sector ETF vs SPY: strength (RS-Ratio, x) and momentum (RS-Momentum, y). "
        "Rotates clockwise. Center at (100,100). The tail is the last ~8 days' path."))

    if st.button(L(" Rotasyonu Analiz Et (RRG)", " Analyze Rotation (RRG)"), key="rrg_btn"):
        with st.spinner(L("RRG hesaplanıyor…", "Computing RRG…")):
            st.session_state["rrg_res"] = sector_rrg()

    rrg = st.session_state.get("rrg_res")
    if rrg is None:
        if "rrg_res" in st.session_state:
            st.info(L("RRG verisi alınamadı — tekrar dene.", "RRG data unavailable — try again."))
        else:
            st.info(L(" 'Rotasyonu Analiz Et (RRG)' butonuna bas.", " Press 'Analyze Rotation (RRG)'."))
        return

    quad_color = {"Leading": C_UP, "Weakening": C_GOLD, "Lagging": C_DOWN, "Improving": C_ACCENT}
    quad_tr = {"Leading": "Lider", "Weakening": "Zayıflıyor", "Lagging": "Geride", "Improving": "Toparlıyor"}

    xs = [p for d in rrg.values() for p in d["tail_x"]]
    ys = [p for d in rrg.values() for p in d["tail_y"]]
    xpad = max(1.0, (max(xs) - min(xs)) * 0.1)
    ypad = max(1.0, (max(ys) - min(ys)) * 0.1)
    x0, x1 = min(min(xs), 100) - xpad, max(max(xs), 100) + xpad
    y0, y1 = min(min(ys), 100) - ypad, max(max(ys), 100) + ypad

    fig = go.Figure()
    # Çeyrek arka planları
    fig.add_shape(type="rect", x0=100, y0=100, x1=x1, y1=y1, fillcolor="rgba(22,199,132,0.07)", line_width=0)
    fig.add_shape(type="rect", x0=100, y0=y0, x1=x1, y1=100, fillcolor="rgba(240,185,11,0.07)", line_width=0)
    fig.add_shape(type="rect", x0=x0, y0=y0, x1=100, y1=100, fillcolor="rgba(234,57,67,0.07)", line_width=0)
    fig.add_shape(type="rect", x0=x0, y0=100, x1=100, y1=y1, fillcolor="rgba(59,130,246,0.07)", line_width=0)
    fig.add_vline(x=100, line=dict(color="rgba(255,255,255,0.2)", width=1))
    fig.add_hline(y=100, line=dict(color="rgba(255,255,255,0.2)", width=1))
    # Çeyrek etiketleri
    fig.add_annotation(x=x1, y=y1, text=L("Lider", "Leading"), showarrow=False,
                       xanchor="right", yanchor="top", font=dict(color=C_UP, size=11))
    fig.add_annotation(x=x1, y=y0, text=L("Zayıflıyor", "Weakening"), showarrow=False,
                       xanchor="right", yanchor="bottom", font=dict(color=C_GOLD, size=11))
    fig.add_annotation(x=x0, y=y0, text=L("Geride", "Lagging"), showarrow=False,
                       xanchor="left", yanchor="bottom", font=dict(color=C_DOWN, size=11))
    fig.add_annotation(x=x0, y=y1, text=L("Toparlıyor", "Improving"), showarrow=False,
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

    # Para nereye kayıyor yorumu
    by_q = {"Leading": [], "Weakening": [], "Lagging": [], "Improving": []}
    for etf, d in rrg.items():
        by_q[d["quadrant"]].append(f"{d['name']} ({etf})")

    def _join(items):
        return ", ".join(items) if items else L("—", "—")

    st.markdown(L("**Para nereye kayıyor?**", "**Where is money rotating?**"))
    inflow = by_q["Improving"] + by_q["Leading"]
    outflow = by_q["Weakening"] + by_q["Lagging"]
    st.success(L(f" **Para GİRİŞİ (güçlü/toparlayan):** {_join(inflow)}",
                 f" **INFLOW (strong/improving):** {_join(inflow)}"))
    st.error(L(f" **Para ÇIKIŞI (zayıf/zayıflayan):** {_join(outflow)}",
               f" **OUTFLOW (weak/weakening):** {_join(outflow)}"))

    for q in ("Leading", "Improving", "Weakening", "Lagging"):
        if by_q[q]:
            label = L(quad_tr[q], q)
            hint = {
                "Leading": L("güçlü + hızlanıyor — liderler", "strong + accelerating — leaders"),
                "Improving": L("zayıf ama toparlıyor — erken giriş adayı", "weak but improving — early-entry candidates"),
                "Weakening": L("güçlü ama yavaşlıyor — kâr-al bölgesi", "strong but slowing — take-profit zone"),
                "Lagging": L("zayıf + yavaşlıyor — kaçın", "weak + decelerating — avoid"),
            }[q]
            st.markdown(f'<span style="color:{quad_color[q]};">●</span> **{label}** '
                        f'<span style="color:#6b7280;font-size:0.85rem;">({hint})</span>: {_join(by_q[q])}',
                        unsafe_allow_html=True)


def page_market_pulse(tickers):
    st.markdown(
        '<div class="page-header">'
        '<h2> ' + L("Piyasa Nabzı", "Market Pulse") + '</h2>'
        '<p>' + L(
            "S&P500, VIX, faiz, dolar ve sektör rotasyonu tek bakışta. "
            "Önce piyasayı oku — Risk-On mu Risk-Off mu — sonra işlem planı yap. "
            "Qullamaggie'nin birinci kuralı: <b>piyasa aleyhine işlem açma.</b>",
            "S&P 500, VIX, rates, dollar and sector rotation at a glance. "
            "Read the market first — Risk-On or Risk-Off — then plan your trade. "
            "Qullamaggie's first rule: <b>don't trade against the market.</b>")
        + '</p></div>', unsafe_allow_html=True)

    top = st.columns([2, 1, 1])
    top[0].caption(L("Son güncelleme: ", "Last update: ") + datetime.now().strftime('%d.%m.%Y %H:%M'))
    if top[1].button(L(" Yenile", " Refresh"), use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    # Auto-refresh toggle
    auto = top[2].toggle(L("⏱ Oto-Yenile (60s)", "⏱ Auto-refresh (60s)"), value=False)
    if auto:
        import time as _time
        last = st.session_state.get("_pulse_ts", 0)
        if _time.time() - last > 60:
            st.session_state["_pulse_ts"] = _time.time()
            st.cache_data.clear()
            st.rerun()

    # Çekilemeyen sembolleri say (sessizce yutmak yerine kullanıcıya bildir)
    failed_syms = []

    # ---------- 1) MAKRO TABLO ----------
    st.markdown("### " + L("Günlük Makro Özet", "Daily Macro Summary"))
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
        macro_rows.append({"Varlık": name, "Fiyat": round(float(df["Close"].iloc[-1]), 2),
                           "Günlük %": round(float(chg), 2)})
    if macro_rows:
        cols = st.columns(5)
        for i, r in enumerate(macro_rows):
            cols[i % 5].metric(r["Varlık"], f"{r['Fiyat']:,}", f"{r['Günlük %']:+.2f}%")

        # Risk-on / risk-off okuması
        if spx_chg > 0 and vix_chg < 0:
            st.success(L(
                " **Risk-On:** Endeksler yukarı, korku (VIX) aşağı. Piyasa iştahı pozitif — long kurulumlar öne çıkar.",
                " **Risk-On:** Indices up, fear (VIX) down. Positive appetite — long setups favored."))
        elif spx_chg < 0 and vix_chg > 0:
            st.error(L(
                " **Risk-Off:** Endeksler aşağı, korku (VIX) yukarı. Temkinli ol, nakit/savunma sektörleri öne çıkar.",
                " **Risk-Off:** Indices down, fear (VIX) up. Be cautious — cash/defensive sectors favored."))
        else:
            st.info(L(
                " **Karışık:** Net bir risk yönü yok; seçici ol, teyit bekle.",
                " **Mixed:** No clear risk direction; be selective, wait for confirmation."))

    st.divider()

    # ---------- 2) SEKTÖR ROTASYONU (KARE KARE) ----------
    st.markdown("### " + L("Sektör Rotasyonu — Para Nereye Akıyor?",
                           "Sector Rotation — Where Is Money Flowing?"))
    sec_rows = []
    for sym, name in SECTOR_ETFS.items():
        df = fetch_daily(sym, "1mo")
        if df is None or len(df) < 6:
            failed_syms.append(sym)
            continue
        d1 = (df["Close"].iloc[-1] - df["Close"].iloc[-2]) / df["Close"].iloc[-2] * 100
        d5 = (df["Close"].iloc[-1] - df["Close"].iloc[-6]) / df["Close"].iloc[-6] * 100
        sec_rows.append({"Sektör": name, "Sembol": sym,
                        "Günlük %": round(float(d1), 2), "Haftalık %": round(float(d5), 2)})

    sec_df = pd.DataFrame()
    if sec_rows:
        sec_df = pd.DataFrame(sec_rows).sort_values("Haftalık %", ascending=False)
        best = sec_df.iloc[0]; worst = sec_df.iloc[-1]
        st.markdown(
            f" **{L('Para girişi', 'Inflow')}:** {best['Sektör']} "
            f"({L('haftalık', 'weekly')} {best['Haftalık %']:+}%) &nbsp;|&nbsp; "
            f" **{L('Para çıkışı', 'Outflow')}:** {worst['Sektör']} "
            f"({L('haftalık', 'weekly')} {worst['Haftalık %']:+}%)")

        # Kare kart ızgarası — tüm sektörler (haftalığa göre güçlüden zayıfa)
        per_row = 4
        recs = sec_df.to_dict("records")
        for start in range(0, len(recs), per_row):
            cols = st.columns(per_row)
            for col, r in zip(cols, recs[start:start + per_row]):
                wk = r["Haftalık %"]
                # Renk: güçlü yeşilden güçlü kırmızıya
                if wk >= 2: bg, brd = "rgba(22,199,132,0.22)", C_UP
                elif wk >= 0: bg, brd = "rgba(22,199,132,0.10)", C_UP
                elif wk > -2: bg, brd = "rgba(234,57,67,0.10)", C_DOWN
                else: bg, brd = "rgba(234,57,67,0.22)", C_DOWN
                dcol = C_UP if r["Günlük %"] >= 0 else C_DOWN
                wcol = C_UP if wk >= 0 else C_DOWN
                col.markdown(
                    f'<div style="background:{bg};border:1px solid {brd};border-radius:12px;'
                    f'padding:12px;text-align:center;margin-bottom:10px;min-height:108px;">'
                    f'<div style="font-size:0.9rem;font-weight:700;color:#eee;">{r["Sektör"]}</div>'
                    f'<div style="font-size:0.7rem;color:#888;">{r["Sembol"]}</div>'
                    f'<div style="font-size:1.4rem;font-weight:800;color:{wcol};margin-top:6px;">{wk:+.2f}%</div>'
                    f'<div style="font-size:0.72rem;color:#999;">{L("haftalık", "weekly")}</div>'
                    f'<div style="font-size:0.8rem;color:{dcol};margin-top:2px;">{L("bugün", "today")} {r["Günlük %"]:+.2f}%</div>'
                    f'</div>', unsafe_allow_html=True)

    st.divider()

    # ---------- 2b) DÜNYA BORSALARI ----------
    st.markdown("### " + L("Dünya Borsaları", "Global Markets"))
    for bolge, indices in GLOBAL_INDICES.items():
        st.markdown(f"**{bolge}**")
        cols = st.columns(len(indices))
        for col, (sym, meta) in zip(cols, indices.items()):
            gdf = fetch_daily(sym, "5d")
            if gdf is None or len(gdf) < 2:
                failed_syms.append(sym)
                col.markdown(
                    f'<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);'
                    f'border-radius:10px;padding:10px;text-align:center;margin-bottom:8px;">'
                    f'<div style="font-size:0.8rem;color:#6b7280;">{meta["ulke"]} {meta["isim"]}</div>'
                    f'<div style="font-size:0.85rem;color:#4b5563;">{L("Veri yok", "No data")}</div>'
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
                f'<div style="font-size:0.72rem;color:#9ca3af;">{meta["ulke"]} {meta["isim"]}</div>'
                f'<div style="font-size:1rem;font-weight:800;color:{col_d};margin:3px 0;">{d1:+.2f}%</div>'
                f'<div style="font-size:0.68rem;color:#6b7280;">{L("haftalık", "weekly")} {wk:+.1f}%</div>'
                f'</div>', unsafe_allow_html=True)

    # Veri çekilemeyen sembol bildirimi (sessiz atlamayı görünür kıl)
    if failed_syms:
        _syms = f"{', '.join(failed_syms[:12])}{'…' if len(failed_syms) > 12 else ''}"
        st.info(L(
            f" {len(failed_syms)} sembol çekilemedi: {_syms} "
            "— Yahoo Finance geçici olarak yanıt vermemiş olabilir; 'Yenile' deneyin.",
            f" {len(failed_syms)} symbols failed to load: {_syms} "
            "— Yahoo Finance may be temporarily unavailable; try 'Refresh'."))

    st.divider()

    # ---------- 3) PİYASA REJİMİ GÖSTERGESİ ----------
    st.markdown("### " + L("Piyasa Rejimi Göstergesi", "Market Regime Indicator"))
    spx_1y = fetch_daily("^GSPC", "1y")
    if spx_1y is not None and len(spx_1y) >= 200:
        spx_price = float(spx_1y["Close"].iloc[-1])
        spx_ma200 = float(spx_1y["Close"].rolling(200).mean().iloc[-1])
        diff_pct = (spx_price - spx_ma200) / spx_ma200 * 100
        _stats = (f'<div style="font-size:0.82rem;color:#9ca3af;margin-top:6px;">'
                  f'SPX: ${spx_price:,.0f} · 200 MA: ${spx_ma200:,.0f} · '
                  f'{L("Fark", "Diff")}: {diff_pct:+.1f}%</div>')
        if diff_pct > 1.0:
            st.markdown(
                '<div style="background:rgba(22,199,132,0.15);border:2px solid #16c784;border-radius:14px;'
                'padding:18px 24px;text-align:center;font-size:1.1rem;font-weight:700;color:#16c784;">'
                + L(" BOĞA REJİMİ — SPX 200 günlük MA üstünde. Long setup tara.",
                    " BULL REGIME — SPX above its 200-day MA. Scan for long setups.")
                + _stats + '</div>', unsafe_allow_html=True)
        elif diff_pct < -1.0:
            st.markdown(
                '<div style="background:rgba(234,57,67,0.15);border:2px solid #ea3943;border-radius:14px;'
                'padding:18px 24px;text-align:center;font-size:1.1rem;font-weight:700;color:#ea3943;">'
                + L(" AYI REJİMİ — SPX 200 günlük MA altında. Nakit beklet, short düşün.",
                    " BEAR REGIME — SPX below its 200-day MA. Hold cash, consider shorts.")
                + _stats + '</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                '<div style="background:rgba(240,185,11,0.12);border:2px solid #f0b90b;border-radius:14px;'
                'padding:18px 24px;text-align:center;font-size:1.1rem;font-weight:700;color:#f0b90b;">'
                + L(" GEÇİŞ — SPX 200 MA sınırında. Dikkatli ol.",
                    " TRANSITION — SPX at its 200 MA. Be careful.")
                + _stats + '</div>', unsafe_allow_html=True)
    else:
        st.caption(L("SPX 1y verisi alınamadı.", "SPX 1y data unavailable."))

    st.divider()

    # ---------- 4) VIX TREND GRAFİĞİ ----------
    st.markdown("### " + L("VIX — Korku Endeksi (5 Gün)", "VIX — Fear Index (5 Days)"))
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
            st.metric(L("VIX Şu An", "VIX Now"), f"{vix_now:.2f}", f"{vix_delta:+.2f}")
            if vix_now < 15:
                st.caption(L(" Düşük korku — piyasa sakin", " Low fear — market calm"))
            elif vix_now < 25:
                st.caption(L(" Normal korku seviyesi", " Normal fear level"))
            elif vix_now < 35:
                st.caption(L(" Yüksek korku — dikkat", " High fear — caution"))
            else:
                st.caption(L(" Panik bölgesi — fırsat?", " Panic zone — opportunity?"))

    st.divider()

    # ---------- 5) ÖNCÜ HİSSELER ----------
    LEADING_STOCKS = ["NVDA", "META", "TSLA", "AMZN", "AAPL", "MSFT"]
    st.markdown("### " + L("Öncü Hisseler — Piyasa Barometresi",
                           "Market Leaders — Barometer Stocks"))
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
                f"{L('Gün', 'Day')} {daily_chg:+.1f}% · {L('Hft', 'Wk')} {weekly_chg:+.1f}%"
            )
        else:
            col.caption(f"{sym}: {L('veri yok', 'no data')}")

    st.divider()

    # ---------- 6) GAP-UP TARAYICI ----------
    st.markdown("### " + L("Gap-Up Açılanlar — Olası EP Fırsatları",
                           "Gap-Up Openers — Possible EP Opportunities"))
    st.caption(L("Bugün önceki kapanışa göre %3+ gap-up ile açılan hisseler.",
                 "Stocks opening 3%+ above the prior close today."))

    @st.cache_data(ttl=1800)
    def _scan_gap_ups(universe_tuple):
        gaps = []
        for t in universe_tuple:
            try:
                df_g = yf.download(t, period="5d", interval="1d", progress=False, auto_adjust=True)
                if df_g is None or len(df_g) < 2:
                    continue
                df_g.columns = [c[0] if isinstance(c, tuple) else c for c in df_g.columns]
                prev_close = float(df_g["Close"].iloc[-2])
                today_open = float(df_g["Open"].iloc[-1])
                gap_pct = (today_open - prev_close) / prev_close * 100
                if gap_pct >= 3.0:
                    vol_avg = float(df_g["Volume"].iloc[-6:-1].mean()) if len(df_g) >= 6 else float(df_g["Volume"].mean())
                    vol_ratio = float(df_g["Volume"].iloc[-1]) / vol_avg if vol_avg > 0 else 1.0
                    gaps.append({"Hisse": t, "Gap %": round(gap_pct, 2), "Hacim Oranı": round(vol_ratio, 2)})
            except Exception:
                continue
        gaps.sort(key=lambda x: x["Gap %"], reverse=True)
        return gaps

    if st.button(L(" Gap-Up Tara", " Scan Gap-Ups"), key="gap_scan_btn"):
        with st.spinner(L("Gap-up taranıyor...", "Scanning gap-ups...")):
            gaps = _scan_gap_ups(tuple(MOMENTUM_UNIVERSE))
        st.session_state["gap_up_results"] = gaps

    gap_results = st.session_state.get("gap_up_results")
    if gap_results is not None:
        if not gap_results:
            st.info(L("Bugün %3+ gap-up açılan hisse bulunamadı.",
                      "No stocks gapped up 3%+ today."))
        else:
            gcols = st.columns(min(4, len(gap_results)))
            for col, r in zip(gcols * 10, gap_results[:8]):
                col.markdown(
                    f'<div style="background:rgba(240,185,11,0.10);border:1px solid #f0b90b;'
                    f'border-radius:10px;padding:10px;text-align:center;margin-bottom:8px;">'
                    f'<div style="font-weight:800;color:#fff;">{r["Hisse"]}</div>'
                    f'<div style="color:#f0b90b;font-size:0.95rem;font-weight:700;">Gap {r["Gap %"]:+.2f}%</div>'
                    f'<div style="color:#9ca3af;font-size:0.75rem;">{r["Hacim Oranı"]}x {L("hacim", "volume")}</div>'
                    f'</div>', unsafe_allow_html=True)

    st.divider()

    # ---------- 7) HACİM ANOMALİSİ ----------
    st.markdown("### " + L("Hacim Anomalisi — Olağandışı Hareketler",
                           "Volume Anomaly — Unusual Moves"))
    st.caption(L("Günlük hacmi 20 günlük ortalamanın 3 katını aşan hisseler.",
                 "Stocks trading at 3x+ their 20-day average volume."))

    @st.cache_data(ttl=1800)
    def _scan_volume_anomaly(universe_tuple):
        anomalies = []
        for t in universe_tuple:
            try:
                df_v = yf.download(t, period="3mo", interval="1d", progress=False, auto_adjust=True)
                if df_v is None or len(df_v) < 22:
                    continue
                df_v.columns = [c[0] if isinstance(c, tuple) else c for c in df_v.columns]
                vol_avg = float(df_v["Volume"].iloc[-21:-1].mean())
                vol_today = float(df_v["Volume"].iloc[-1])
                rvol = vol_today / vol_avg if vol_avg > 0 else 1.0
                if rvol >= 3.0:
                    price = float(df_v["Close"].iloc[-1])
                    chg = (price - float(df_v["Close"].iloc[-2])) / float(df_v["Close"].iloc[-2]) * 100
                    anomalies.append({"Hisse": t, "RVOL": round(rvol, 2), "Fiyat Değişim %": round(chg, 2)})
            except Exception:
                continue
        anomalies.sort(key=lambda x: x["RVOL"], reverse=True)
        return anomalies

    if st.button(L(" Hacim Anomalisi Tara", " Scan Volume Anomaly"), key="vol_anomaly_btn"):
        with st.spinner(L("Hacim taranıyor...", "Scanning volume...")):
            vol_anom = _scan_volume_anomaly(tuple(MOMENTUM_UNIVERSE))
        st.session_state["vol_anomaly_results"] = vol_anom

    vol_results = st.session_state.get("vol_anomaly_results")
    if vol_results is not None:
        if not vol_results:
            st.info(L("Bugün 3x+ hacim anomalisi bulunamadı.",
                      "No 3x+ volume anomaly found today."))
        else:
            va_df = pd.DataFrame(vol_results).rename(columns={
                "Hisse": L("Hisse", "Ticker"),
                "Fiyat Değişim %": L("Fiyat Değişim %", "Price Change %"),
            })
            st.dataframe(va_df, use_container_width=True, hide_index=True,
                         column_config={
                             "RVOL": st.column_config.NumberColumn(format="%.2fx"),
                             L("Fiyat Değişim %", "Price Change %"):
                                 st.column_config.NumberColumn(format="%.2f%%"),
                         })

    st.divider()

    # ---------- 7b) DARK POOL / OFF-EXCHANGE (FINRA) ----------
    st.markdown("###  " + L("Dark Pool & Off-Exchange Aktivitesi",
                            "Dark Pool & Off-Exchange Activity"))
    st.caption(L(
        "FINRA günlük konsolide short-hacim verisi (resmi, ücretsiz, ~1 gün gecikmeli). "
        "Short hacmin toplam hacme yüksek oranı = yoğun borsa-dışı/kurumsal aktivite vekili. "
        "Gerçek zamanlı dark pool print'i değildir.",
        "FINRA daily consolidated short-volume data (official, free, ~1 day delayed). "
        "A high short-to-total ratio proxies heavy off-exchange/institutional activity. "
        "It is not a real-time dark pool print."))
    if st.button(L(" Dark Pool Tara (FINRA)", " Scan Dark Pool (FINRA)"), key="darkpool_btn"):
        with st.spinner(L("FINRA verisi çekiliyor...", "Fetching FINRA data...")):
            st.session_state["darkpool_res"] = finra_short_volume(tuple(tickers))

    dp = st.session_state.get("darkpool_res")
    if dp is not None:
        if not dp.get("ok"):
            st.info(L(
                f"Veri alınamadı ({dp.get('reason', 'bilinmiyor')}). "
                "Hafta sonu/tatilde FINRA dosyası yayınlanmaz.",
                f"Data unavailable ({dp.get('reason', 'unknown')}). "
                "FINRA files are not published on weekends/holidays."))
        else:
            st.caption(L("Veri tarihi: ", "Data date: ") + str(dp['date']))
            _hisse = L("Hisse", "Ticker")
            _sh = L("Short Hacim", "Short Volume")
            _th = L("Toplam Hacim", "Total Volume")
            dpv = dp["df"][["Symbol", "Short %", "ShortVolume", "TotalVolume"]].rename(
                columns={"Symbol": _hisse, "ShortVolume": _sh, "TotalVolume": _th})
            st.dataframe(dpv, use_container_width=True, hide_index=True,
                         column_config={
                             "Short %": st.column_config.ProgressColumn(
                                 "Short %", format="%.1f%%", min_value=0, max_value=100),
                             _sh: st.column_config.NumberColumn(format="%d"),
                             _th: st.column_config.NumberColumn(format="%d"),
                         })
            hot = dpv.iloc[0]
            st.markdown(
                L(" En yüksek off-exchange baskısı: **{s}** (short oranı {r}%)",
                  " Highest off-exchange pressure: **{s}** (short ratio {r}%)").format(
                    s=hot[_hisse], r=hot['Short %']))

    st.divider()

    # ---------- 7c) OPSİYON AKIŞI (yfinance) ----------
    st.markdown("###  " + L("Opsiyon Akışı", "Options Flow"))
    st.caption(L(
        "yfinance opsiyon zincirinden ücretsiz vekil: Put/Call dengesi ve olağandışı "
        "kontratlar (günlük hacim > açık pozisyon = yeni pozisyon akını). "
        "Gerçek zamanlı paralı 'flow' değildir.",
        "Free proxy from the yfinance option chain: Put/Call balance and unusual "
        "contracts (daily volume > open interest = new positioning). "
        "It is not a real-time paid 'flow'."))
    of_col = st.columns([2, 1])
    of_ticker = of_col[0].selectbox(L("Hisse seç", "Select ticker"), tickers, key="of_ticker")
    if of_col[1].button(L(" Opsiyon Akışını Getir", " Get Options Flow"), key="opt_flow_btn"):
        with st.spinner(L(f"{of_ticker} opsiyon zinciri okunuyor...",
                          f"Reading {of_ticker} option chain...")):
            st.session_state["opt_flow_res"] = (of_ticker, options_flow(of_ticker))

    ofr = st.session_state.get("opt_flow_res")
    if ofr is not None:
        of_sym, of = ofr
        if not of.get("ok"):
            st.info(L(
                f"{of_sym} için opsiyon verisi bulunamadı (opsiyonu olmayan/likit olmayan hisse olabilir).",
                f"No options data for {of_sym} (may be an illiquid or non-optionable stock)."))
        else:
            pc = of["pc_ratio"]
            m = st.columns(4)
            m[0].metric(L("Call Hacmi", "Call Volume"), f"{of['call_vol']:,.0f}")
            m[1].metric(L("Put Hacmi", "Put Volume"), f"{of['put_vol']:,.0f}")
            m[2].metric(L("Put/Call Oranı", "Put/Call Ratio"), f"{pc:.2f}" if pc else "—")
            m[3].metric(L("Toplam OI", "Total OI"), f"{(of['call_oi'] + of['put_oi']):,.0f}")
            if pc is not None:
                if pc < 0.7:
                    st.success(L(f" Call ağırlıklı (P/C {pc:.2f}) — boğa opsiyon iştahı.",
                                 f" Call-heavy (P/C {pc:.2f}) — bullish options appetite."))
                elif pc > 1.0:
                    st.error(L(f" Put ağırlıklı (P/C {pc:.2f}) — korunma/ayı opsiyon iştahı.",
                               f" Put-heavy (P/C {pc:.2f}) — hedging/bearish options appetite."))
                else:
                    st.info(L(f" Dengeli opsiyon akışı (P/C {pc:.2f}).",
                              f" Balanced options flow (P/C {pc:.2f})."))
            if of["unusual"]:
                st.markdown(L("**Olağandışı Kontratlar** (hacim > açık pozisyon)",
                              "**Unusual Contracts** (volume > open interest)"))
                _u = pd.DataFrame(of["unusual"]).rename(columns={
                    "Yön": L("Yön", "Side"), "Vade": L("Vade", "Expiry"),
                    "Hacim": L("Hacim", "Volume")})
                st.dataframe(_u, use_container_width=True, hide_index=True,
                             column_config={
                                 "Strike": st.column_config.NumberColumn(format="%.1f"),
                                 L("Hacim", "Volume"): st.column_config.NumberColumn(format="%d"),
                                 "OI": st.column_config.NumberColumn(format="%d"),
                                 "Son $": st.column_config.NumberColumn(format="$%.2f"),
                             })
            else:
                st.caption(L("Bu vadelerde olağandışı kontrat yok.",
                             "No unusual contracts in these expiries."))

    st.divider()

    # ---------- 7d) PİYASA SAĞLIĞI (DÜŞÜŞ RADARI) ----------
    _render_market_health()

    st.divider()

    # ---------- 7e) SEKTÖR ROTASYONU (RRG) ----------
    _render_rrg()

    st.divider()

    # ---------- 8) GÜNÜN YORUMU ----------
    st.markdown("### " + L("Günün Yorumu", "Daily Commentary"))
    _render_daily_commentary(spx_chg, vix_chg, ndx_chg, sec_df)

    st.divider()
