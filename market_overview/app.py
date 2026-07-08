"""Uygulama giriş noktası: set_page_config, CSS, sayfa çağrısı."""

import streamlit as st

from market_overview.config import DEFAULT_TICKERS
from market_overview.pages import page_market_pulse
from market_overview.security import sanitize_tickers


def main():
    st.set_page_config(page_title="Genel Bakış", page_icon="", layout="wide")

    st.markdown("""
    <style>
    /* ── Genel arka plan ── */
    .stApp { background: #0b0f1a; }

    /* ── Sekme çubuğu ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: #111827;
        border-radius: 12px;
        padding: 5px;
        border: 1px solid rgba(255,255,255,0.07);
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 8px 16px;
        font-size: 0.85rem;
        font-weight: 500;
        color: #9ca3af;
        background: transparent;
        border: none;
        transition: all 0.2s;
    }
    .stTabs [aria-selected="true"] {
        background: #1e293b !important;
        color: #f1f5f9 !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
    }
    .stTabs [data-baseweb="tab-highlight"] { display: none; }
    .stTabs [data-baseweb="tab-border"] { display: none; }

    /* ── Kart bileşeni ── */
    .mcard {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 12px;
        padding: 14px;
        text-align: center;
    }
    .mval { font-size: 1.25rem; font-weight: 700; color: #3b82f6; }
    .mlbl { font-size: 0.72rem; color: #6b7280; margin-top: 2px; }

    /* ── Rozet ── */
    .badge {
        display: inline-block;
        background: rgba(240,185,11,0.12);
        border: 1px solid rgba(240,185,11,0.4);
        border-radius: 20px;
        padding: 3px 10px;
        margin: 3px;
        font-size: 0.78rem;
        color: #f0b90b;
    }

    /* ── Sayfa başlık bloğu ── */
    .page-header {
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 14px;
        padding: 20px 24px;
        margin-bottom: 20px;
    }
    .page-header h2 { margin: 0 0 4px 0; font-size: 1.3rem; color: #f1f5f9; }
    .page-header p  { margin: 0; font-size: 0.85rem; color: #6b7280; }

    /* ── Uyarı bandı ── */
    .warn-bar {
        background: rgba(234,57,67,0.08);
        border-left: 3px solid #ea3943;
        border-radius: 6px;
        padding: 8px 14px;
        font-size: 0.78rem;
        color: #9ca3af;
        margin-bottom: 16px;
    }

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] { background: #0f172a; }
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stSlider label,
    section[data-testid="stSidebar"] .stNumberInput label { font-size: 0.82rem; color: #9ca3af; }
    </style>
    """, unsafe_allow_html=True)

    # Uyarı bandı
    st.markdown(
        '<div class="warn-bar"> Bu araç yalnızca eğitim amaçlıdır. '
        'Gerçek emir göndermez ve yatırım tavsiyesi niteliği taşımaz.</div>',
        unsafe_allow_html=True)

    # Başlık
    st.markdown(
        '<h1 style="font-size:1.6rem;font-weight:800;color:#f1f5f9;margin-bottom:2px;"> Genel Bakış</h1>'
        '<p style="color:#6b7280;font-size:0.82rem;margin-bottom:16px;">'
        'Piyasayı oku · Risk-On mu Risk-Off mu · Nerede fırsat var</p>',
        unsafe_allow_html=True)

    # ── Sidebar ──
    with st.sidebar:
        st.markdown('<p style="font-size:0.95rem;font-weight:700;color:#f1f5f9;margin-bottom:8px;"> Ayarlar</p>',
                    unsafe_allow_html=True)
        custom = st.text_input("Hisse listesi (virgülle)", "", placeholder="AAPL, MSFT, NVDA",
                               key="sidebar_tickers")
        _clean = sanitize_tickers(custom)
        tickers = _clean or list(DEFAULT_TICKERS)
        if custom.strip() and not _clean:
            st.sidebar.warning("Geçersiz sembol girdisi — varsayılan listeye dönüldü.")

        st.divider()
        st.markdown('<p style="font-size:0.78rem;font-weight:600;color:#9ca3af;">RİSK YÖNETİMİ</p>',
                    unsafe_allow_html=True)

        st.divider()
        st.markdown(
            f'<p style="font-size:0.75rem;color:#4b5563;">Havuz: '
            f'<b style="color:#9ca3af;">{len(tickers)} hisse</b><br>'
            f'<span style="color:#374151;">{", ".join(tickers[:6])}{"…" if len(tickers) > 6 else ""}</span></p>',
            unsafe_allow_html=True)

    # ── 3 Sekme: bir tradercının günlük iş akışı ──
    page_market_pulse(tickers)
