"""Streamlit sayfa/bölüm render fonksiyonları."""

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

from market_overview.charts import make_cloud_chart
from market_overview.config import C_DOWN, C_GOLD, C_UP, GLOBAL_INDICES, MACRO_ASSETS, MOMENTUM_UNIVERSE, NASDAQ100, SECTOR_ETFS, SP500_UNIVERSE
from market_overview.data import fetch_daily, finra_short_volume, options_flow
from market_overview.scanners import scan_qullamaggie_yf
from market_overview.signals import detect_setup, explain_trade


def _render_qullamaggie_scan_section():
    """Qullamaggie filtre tarayıcısı — tamamen yfinance tabanlı, yayın için yasal."""
    st.markdown("### Qullamaggie Filtre Tarayıcısı")
    st.caption(
        "Filtreler: **Fiyat > EMA100 (≈21 haftalık) · Fiyat > EMA200 (≈50 haftalık) · "
        "1Y > 50% · Hacim artıyor (10G ort > 90G ort) · ADR% > 3.5%** — "
        "Veri: Yahoo Finance (yfinance) · 30 dk cache"
    )

    fc = st.columns(4)
    q_evren   = fc[0].selectbox("Evren", ["S&P500 + Momentum (~300)", "Nasdaq-100", "Momentum (hızlı, 40)"],
                                  key="qs_evren")
    q_perf1y  = fc[1].slider("Min. 1Y %", 0, 300, 50, 10, key="qs_perf1y",
                               help="1 yıllık performans. Qullamaggie 50%+ arar.")
    q_adr     = fc[2].slider("Min. ADR %", 1.0, 10.0, 3.5, 0.5, key="qs_adr",
                               help="Ortalama günlük hareket. 3.5%+ = hareketli.")
    q_cap     = fc[3].slider("Min. Piyasa Değ. ($B)", 0.0, 10.0, 2.0, 0.5, key="qs_cap",
                               help="0 = filtre yok. Büyük para için 2B+ tercih.")

    if q_evren == "S&P500 + Momentum (~300)":
        universe = SP500_UNIVERSE
    elif q_evren == "Nasdaq-100":
        universe = NASDAQ100
    else:
        universe = MOMENTUM_UNIVERSE

    st.caption(f" {len(universe)} hisse taranacak · İlk tarama ~20-30 sn sürer (sonra 30 dk cache'li)")

    if st.button(" Qullamaggie Tara", type="primary", use_container_width=True, key="qs_scan_btn"):
        with st.spinner(f"{len(universe)} hisse için 1 yıllık veri indiriliyor…"):
            df_q, count = scan_qullamaggie_yf(universe, float(q_perf1y), float(q_cap), float(q_adr))
            st.session_state["qs_result"] = df_q
            st.session_state["qs_count"]  = count

    df_tv = st.session_state.get("qs_result")
    count  = st.session_state.get("qs_count", 0)

    if df_tv is None:
        st.info(" 'Qullamaggie Tara' butonuna bas.")
        return
    if df_tv.empty:
        st.warning("Filtrelerle eşleşen hisse yok — eşikleri düşür.")
        return

    st.success(f" {count} hisse filtreden geçti · Güncelleme: {pd.Timestamp.now().strftime('%H:%M:%S')}")

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
        st.markdown("#### Hisse Grafiği & Trade Planı")
        sel = st.selectbox("Hisse seç", picks, key="qs_pick_chart")

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
                        rr_col = C_UP if plan["rr"] >= 3 else (C_GOLD if plan["rr"] >= 2 else C_DOWN)
                        pc1, pc2, pc3, pc4 = st.columns(4)
                        pc1.metric("Setup", setup)
                        pc2.metric("Giriş", f"${plan['entry']}")
                        pc3.metric("Stop", f"${plan['stop']}")
                        pc4.metric("R:R", f"{plan['rr']}:1",
                                   delta="İyi" if plan["rr"] >= 3 else ("Orta" if plan["rr"] >= 2 else "Zayıf"))

                    st.plotly_chart(
                        make_cloud_chart(full_df, f"{sel} — EMA 10/20 + 50/200 MA"),
                        use_container_width=True,
                    )


def _render_daily_commentary(spx_chg: float, vix_chg: float, ndx_chg: float, sec_df):
    """Günün piyasa yorumunu sade-teknik dille gösterir."""
    tarih = datetime.now().strftime("%d.%m.%Y")

    if spx_chg > 0.3 and vix_chg < 0:
        risk_renk, risk_ikon, risk_metin = C_UP, "", "Risk-On"
        risk_aciklama = (f"Endeksler yukarı (SPX {spx_chg:+.2f}%), VIX aşağı ({vix_chg:+.2f}%). "
                         "Piyasa iştahlı. Qullamaggie setuplarına girebilirsin — trend yönünde.")
        eylem = "Kırılım ve EMA geri çekilme setuplarını tara. Stop'ları sıkı tut."
    elif spx_chg < -0.3 and vix_chg > 0:
        risk_renk, risk_ikon, risk_metin = C_DOWN, "", "Risk-Off"
        risk_aciklama = (f"Endeksler aşağı (SPX {spx_chg:+.2f}%), VIX yukarı ({vix_chg:+.2f}%). "
                         "Kurumlar satıyor. Yeni pozisyon açma.")
        eylem = "Mevcut pozisyonların stopunu sıkılaştır. Nakit beklet."
    elif abs(spx_chg) <= 0.3:
        risk_renk, risk_ikon, risk_metin = C_GOLD, "", "Durağan"
        risk_aciklama = (f"SPX {spx_chg:+.2f}%, Nasdaq {ndx_chg:+.2f}%. "
                         "Piyasa yön arıyor. Kırılım olmadan işlem açma.")
        eylem = "Watchlist tara, kırılım emri koy — tetik düşmeden girme."
    else:
        risk_renk, risk_ikon, risk_metin = C_GOLD, "", "Karışık"
        risk_aciklama = (f"SPX {spx_chg:+.2f}%, VIX {vix_chg:+.2f}% — sinyal çelişiyor.")
        eylem = "Küçük deneme pozisyonu veya izle-bekle."

    st.markdown(
        f'<div style="background:rgba(255,255,255,0.03);border-left:4px solid {risk_renk};'
        f'border-radius:8px;padding:16px 20px;margin-bottom:14px;">'
        f'<div style="font-size:0.75rem;color:#6b7280;margin-bottom:4px;">{tarih}</div>'
        f'<div style="font-size:1.1rem;font-weight:800;color:{risk_renk};margin-bottom:6px;">'
        f'{risk_ikon} {risk_metin}</div>'
        f'<div style="font-size:0.88rem;color:#d1d5db;margin-bottom:8px;">{risk_aciklama}</div>'
        f'<div style="font-size:0.82rem;color:#9ca3af;background:rgba(255,255,255,0.04);'
        f'border-radius:6px;padding:8px 12px;"> <b>Ne yapmalısın:</b> {eylem}</div>'
        f'</div>', unsafe_allow_html=True)

    if sec_df is not None and not sec_df.empty:
        best  = sec_df.iloc[0]
        worst = sec_df.iloc[-1]
        yukselenler = sec_df[sec_df["Haftalık %"] > 0]
        dusenler    = sec_df[sec_df["Haftalık %"] < 0]
        st.markdown(
            f'<div style="font-size:0.85rem;color:#9ca3af;padding:6px 0;">'
            f' <b style="color:{C_UP};">{best["Sektör"]}</b> haftalık güçlü ({best["Haftalık %"]:+.2f}%) — '
            f'bu sektördeki lider hisselere öncelik ver. &nbsp;|&nbsp; '
            f' <b style="color:{C_DOWN};">{worst["Sektör"]}</b> zayıf ({worst["Haftalık %"]:+.2f}%) — '
            f'bu sektörde long açmaktan kaçın.'
            f'<br><span style="color:#6b7280;font-size:0.78rem;">'
            f'{len(yukselenler)} sektör ↑ · {len(dusenler)} sektör ↓</span>'
            f'</div>', unsafe_allow_html=True)

    st.caption("Otomatik üretildi · Yatırım tavsiyesi değildir.")


def page_market_pulse(tickers):
    st.markdown(
        '<div class="page-header">'
        '<h2> Piyasa Nabzı</h2>'
        '<p>S&P500, VIX, faiz, dolar ve sektör rotasyonu tek bakışta. '
        'Önce piyasayı oku — Risk-On mu Risk-Off mu — sonra işlem planı yap. '
        'Qullamaggie\'nin birinci kuralı: <b>piyasa aleyhine işlem açma.</b></p>'
        '</div>', unsafe_allow_html=True)

    top = st.columns([2, 1, 1])
    top[0].caption(f"Son güncelleme: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    if top[1].button(" Yenile", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    # Auto-refresh toggle
    auto = top[2].toggle("⏱ Oto-Yenile (60s)", value=False)
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
    st.markdown("### Günlük Makro Özet")
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
            st.success(" **Risk-On:** Endeksler yukarı, korku (VIX) aşağı. Piyasa iştahı pozitif — long kurulumlar öne çıkar.")
        elif spx_chg < 0 and vix_chg > 0:
            st.error(" **Risk-Off:** Endeksler aşağı, korku (VIX) yukarı. Temkinli ol, nakit/savunma sektörleri öne çıkar.")
        else:
            st.info(" **Karışık:** Net bir risk yönü yok; seçici ol, teyit bekle.")

    st.divider()

    # ---------- 2) SEKTÖR ROTASYONU (KARE KARE) ----------
    st.markdown("### Sektör Rotasyonu — Para Nereye Akıyor?")
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
        st.markdown(f" **Para girişi:** {best['Sektör']} (haftalık {best['Haftalık %']:+}%) &nbsp;|&nbsp; "
                    f" **Para çıkışı:** {worst['Sektör']} (haftalık {worst['Haftalık %']:+}%)")

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
                    f'<div style="font-size:0.72rem;color:#999;">haftalık</div>'
                    f'<div style="font-size:0.8rem;color:{dcol};margin-top:2px;">bugün {r["Günlük %"]:+.2f}%</div>'
                    f'</div>', unsafe_allow_html=True)

    st.divider()

    # ---------- 2b) DÜNYA BORSALARI ----------
    st.markdown("### Dünya Borsaları")
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
                    f'<div style="font-size:0.85rem;color:#4b5563;">Veri yok</div>'
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
                f'<div style="font-size:0.68rem;color:#6b7280;">haftalık {wk:+.1f}%</div>'
                f'</div>', unsafe_allow_html=True)

    # Veri çekilemeyen sembol bildirimi (sessiz atlamayı görünür kıl)
    if failed_syms:
        st.info(f" {len(failed_syms)} sembol çekilemedi: "
                f"{', '.join(failed_syms[:12])}{'…' if len(failed_syms) > 12 else ''} "
                f"— Yahoo Finance geçici olarak yanıt vermemiş olabilir; 'Yenile' deneyin.")

    st.divider()

    # ---------- 3) PİYASA REJİMİ GÖSTERGESİ ----------
    st.markdown("### Piyasa Rejimi Göstergesi")
    spx_1y = fetch_daily("^GSPC", "1y")
    if spx_1y is not None and len(spx_1y) >= 200:
        spx_price = float(spx_1y["Close"].iloc[-1])
        spx_ma200 = float(spx_1y["Close"].rolling(200).mean().iloc[-1])
        diff_pct = (spx_price - spx_ma200) / spx_ma200 * 100
        if diff_pct > 1.0:
            st.markdown(
                '<div style="background:rgba(22,199,132,0.15);border:2px solid #16c784;border-radius:14px;'
                'padding:18px 24px;text-align:center;font-size:1.1rem;font-weight:700;color:#16c784;">'
                ' BOĞA REJİMİ — SPX 200 günlük MA üstünde. Long setup tara.'
                f'<div style="font-size:0.82rem;color:#9ca3af;margin-top:6px;">'
                f'SPX: ${spx_price:,.0f} · 200 MA: ${spx_ma200:,.0f} · Fark: {diff_pct:+.1f}%</div>'
                '</div>', unsafe_allow_html=True)
        elif diff_pct < -1.0:
            st.markdown(
                '<div style="background:rgba(234,57,67,0.15);border:2px solid #ea3943;border-radius:14px;'
                'padding:18px 24px;text-align:center;font-size:1.1rem;font-weight:700;color:#ea3943;">'
                ' AYI REJİMİ — SPX 200 günlük MA altında. Nakit beklet, short düşün.'
                f'<div style="font-size:0.82rem;color:#9ca3af;margin-top:6px;">'
                f'SPX: ${spx_price:,.0f} · 200 MA: ${spx_ma200:,.0f} · Fark: {diff_pct:+.1f}%</div>'
                '</div>', unsafe_allow_html=True)
        else:
            st.markdown(
                '<div style="background:rgba(240,185,11,0.12);border:2px solid #f0b90b;border-radius:14px;'
                'padding:18px 24px;text-align:center;font-size:1.1rem;font-weight:700;color:#f0b90b;">'
                ' GEÇİŞ — SPX 200 MA sınırında. Dikkatli ol.'
                f'<div style="font-size:0.82rem;color:#9ca3af;margin-top:6px;">'
                f'SPX: ${spx_price:,.0f} · 200 MA: ${spx_ma200:,.0f} · Fark: {diff_pct:+.1f}%</div>'
                '</div>', unsafe_allow_html=True)
    else:
        st.caption("SPX 1y verisi alınamadı.")

    st.divider()

    # ---------- 4) VIX TREND GRAFİĞİ ----------
    st.markdown("### VIX — Korku Endeksi (5 Gün)")
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
            st.metric("VIX Şu An", f"{vix_now:.2f}", f"{vix_delta:+.2f}")
            if vix_now < 15:
                st.caption(" Düşük korku — piyasa sakin")
            elif vix_now < 25:
                st.caption(" Normal korku seviyesi")
            elif vix_now < 35:
                st.caption(" Yüksek korku — dikkat")
            else:
                st.caption(" Panik bölgesi — fırsat?")

    st.divider()

    # ---------- 5) ÖNCÜ HİSSELER ----------
    LEADING_STOCKS = ["NVDA", "META", "TSLA", "AMZN", "AAPL", "MSFT"]
    st.markdown("### Öncü Hisseler — Piyasa Barometresi")
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
                f"Gün {daily_chg:+.1f}% · Hft {weekly_chg:+.1f}%"
            )
        else:
            col.caption(f"{sym}: veri yok")

    st.divider()

    # ---------- 6) GAP-UP TARAYICI ----------
    st.markdown("### Gap-Up Açılanlar — Olası EP Fırsatları")
    st.caption("Bugün önceki kapanışa göre %3+ gap-up ile açılan hisseler.")

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

    if st.button(" Gap-Up Tara", key="gap_scan_btn"):
        with st.spinner("Gap-up taranıyor..."):
            gaps = _scan_gap_ups(tuple(MOMENTUM_UNIVERSE))
        st.session_state["gap_up_results"] = gaps

    gap_results = st.session_state.get("gap_up_results")
    if gap_results is not None:
        if not gap_results:
            st.info("Bugün %3+ gap-up açılan hisse bulunamadı.")
        else:
            gcols = st.columns(min(4, len(gap_results)))
            for col, r in zip(gcols * 10, gap_results[:8]):
                col.markdown(
                    f'<div style="background:rgba(240,185,11,0.10);border:1px solid #f0b90b;'
                    f'border-radius:10px;padding:10px;text-align:center;margin-bottom:8px;">'
                    f'<div style="font-weight:800;color:#fff;">{r["Hisse"]}</div>'
                    f'<div style="color:#f0b90b;font-size:0.95rem;font-weight:700;">Gap {r["Gap %"]:+.2f}%</div>'
                    f'<div style="color:#9ca3af;font-size:0.75rem;">{r["Hacim Oranı"]}x hacim</div>'
                    f'</div>', unsafe_allow_html=True)

    st.divider()

    # ---------- 7) HACİM ANOMALİSİ ----------
    st.markdown("### Hacim Anomalisi — Olağandışı Hareketler")
    st.caption("Günlük hacmi 20 günlük ortalamanın 3 katını aşan hisseler.")

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

    if st.button(" Hacim Anomalisi Tara", key="vol_anomaly_btn"):
        with st.spinner("Hacim taranıyor..."):
            vol_anom = _scan_volume_anomaly(tuple(MOMENTUM_UNIVERSE))
        st.session_state["vol_anomaly_results"] = vol_anom

    vol_results = st.session_state.get("vol_anomaly_results")
    if vol_results is not None:
        if not vol_results:
            st.info("Bugün 3x+ hacim anomalisi bulunamadı.")
        else:
            va_df = pd.DataFrame(vol_results)
            st.dataframe(va_df, use_container_width=True, hide_index=True,
                         column_config={
                             "RVOL": st.column_config.NumberColumn(format="%.2fx"),
                             "Fiyat Değişim %": st.column_config.NumberColumn(format="%.2f%%"),
                         })

    st.divider()

    # ---------- 7b) DARK POOL / OFF-EXCHANGE (FINRA) ----------
    st.markdown("###  Dark Pool & Off-Exchange Aktivitesi")
    st.caption("FINRA günlük konsolide short-hacim verisi (resmi, ücretsiz, ~1 gün gecikmeli). "
               "Short hacmin toplam hacme yüksek oranı = yoğun borsa-dışı/kurumsal aktivite vekili. "
               "Gerçek zamanlı dark pool print'i değildir.")
    if st.button(" Dark Pool Tara (FINRA)", key="darkpool_btn"):
        with st.spinner("FINRA verisi çekiliyor..."):
            st.session_state["darkpool_res"] = finra_short_volume(tuple(tickers))

    dp = st.session_state.get("darkpool_res")
    if dp is not None:
        if not dp.get("ok"):
            st.info(f"Veri alınamadı ({dp.get('reason', 'bilinmiyor')}). "
                    "Hafta sonu/tatilde FINRA dosyası yayınlanmaz.")
        else:
            st.caption(f"Veri tarihi: {dp['date']}")
            dpv = dp["df"][["Symbol", "Short %", "ShortVolume", "TotalVolume"]].rename(
                columns={"Symbol": "Hisse", "ShortVolume": "Short Hacim",
                         "TotalVolume": "Toplam Hacim"})
            st.dataframe(dpv, use_container_width=True, hide_index=True,
                         column_config={
                             "Short %": st.column_config.ProgressColumn(
                                 "Short %", format="%.1f%%", min_value=0, max_value=100),
                             "Short Hacim": st.column_config.NumberColumn(format="%d"),
                             "Toplam Hacim": st.column_config.NumberColumn(format="%d"),
                         })
            hot = dpv.iloc[0]
            st.markdown(f" En yüksek off-exchange baskısı: **{hot['Hisse']}** "
                        f"(short oranı {hot['Short %']}%)")

    st.divider()

    # ---------- 7c) OPSİYON AKIŞI (yfinance) ----------
    st.markdown("###  Opsiyon Akışı")
    st.caption("yfinance opsiyon zincirinden ücretsiz vekil: Put/Call dengesi ve olağandışı "
               "kontratlar (günlük hacim > açık pozisyon = yeni pozisyon akını). "
               "Gerçek zamanlı paralı 'flow' değildir.")
    of_col = st.columns([2, 1])
    of_ticker = of_col[0].selectbox("Hisse seç", tickers, key="of_ticker")
    if of_col[1].button(" Opsiyon Akışını Getir", key="opt_flow_btn"):
        with st.spinner(f"{of_ticker} opsiyon zinciri okunuyor..."):
            st.session_state["opt_flow_res"] = (of_ticker, options_flow(of_ticker))

    ofr = st.session_state.get("opt_flow_res")
    if ofr is not None:
        of_sym, of = ofr
        if not of.get("ok"):
            st.info(f"{of_sym} için opsiyon verisi bulunamadı (opsiyonu olmayan/likit olmayan hisse olabilir).")
        else:
            pc = of["pc_ratio"]
            m = st.columns(4)
            m[0].metric("Call Hacmi", f"{of['call_vol']:,.0f}")
            m[1].metric("Put Hacmi", f"{of['put_vol']:,.0f}")
            m[2].metric("Put/Call Oranı", f"{pc:.2f}" if pc else "—")
            m[3].metric("Toplam OI", f"{(of['call_oi'] + of['put_oi']):,.0f}")
            if pc is not None:
                if pc < 0.7:
                    st.success(f" Call ağırlıklı (P/C {pc:.2f}) — boğa opsiyon iştahı.")
                elif pc > 1.0:
                    st.error(f" Put ağırlıklı (P/C {pc:.2f}) — korunma/ayı opsiyon iştahı.")
                else:
                    st.info(f" Dengeli opsiyon akışı (P/C {pc:.2f}).")
            if of["unusual"]:
                st.markdown("**Olağandışı Kontratlar** (hacim > açık pozisyon)")
                st.dataframe(pd.DataFrame(of["unusual"]), use_container_width=True, hide_index=True,
                             column_config={
                                 "Strike": st.column_config.NumberColumn(format="%.1f"),
                                 "Hacim": st.column_config.NumberColumn(format="%d"),
                                 "OI": st.column_config.NumberColumn(format="%d"),
                                 "Son $": st.column_config.NumberColumn(format="$%.2f"),
                             })
            else:
                st.caption("Bu vadelerde olağandışı kontrat yok.")

    st.divider()

    # ---------- 8) GÜNÜN YORUMU ----------
    st.markdown("### Günün Yorumu")
    _render_daily_commentary(spx_chg, vix_chg, ndx_chg, sec_df)

    st.divider()
