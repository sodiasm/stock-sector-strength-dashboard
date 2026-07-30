"""Streamlit entry point and visual theme."""

import streamlit as st

from market_overview.config import DEFAULT_TICKERS
from market_overview.i18n import L
from market_overview.pages import page_market_pulse
from market_overview.security import sanitize_tickers


def main():
    st.set_page_config(page_title="Market Overview", page_icon="◐", layout="wide")
    st.session_state.setdefault("lang", "zh-TW")

    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Noto+Sans+TC:wght@400;500;700;900&display=swap');
        :root { --paper:#f6f1e8; --ink:#202322; --muted:#6c716e; --vermilion:#c94c3d; --indigo:#344f70; --line:#ddd5c8; }
        .stApp { background:var(--paper); color:var(--ink); }
        [data-testid="stHeader"] { background:rgba(246,241,232,.92); }
        [data-testid="stSidebar"] { background:#eee7dc; border-right:1px solid var(--line); }
        [data-testid="stSidebar"] * { color:var(--ink); }
        h1,h2,h3,h4,p,div,span,button,label { font-family:'Noto Sans TC','DM Sans',sans-serif; }
        h1,h2,h3 { letter-spacing:.02em; color:var(--ink); }
        h1 { font-weight:900; }
        .stMarkdown, .stCaption { color:var(--muted); }
        .stButton > button { border:1px solid var(--indigo); border-radius:4px; color:var(--indigo); background:transparent; }
        .stButton > button:hover { border-color:var(--vermilion); color:var(--vermilion); }
        div[data-testid="stMetric"] { background:#fbf8f2; border:1px solid var(--line); border-radius:4px; padding:12px; }
        div[data-testid="stMetricLabel"] { color:var(--muted); }
        .mcard { background:#fbf8f2; border:1px solid var(--line); border-radius:4px; padding:14px; text-align:center; }
        .page-header { background:#fbf8f2; border-top:3px solid var(--vermilion); border-bottom:1px solid var(--line); padding:20px 24px; margin-bottom:20px; }
        .page-header h2 { margin:0 0 4px; color:var(--ink); }
        .page-header p { margin:0; color:var(--muted); }
        .warn-bar { background:#f4e4d8; border-left:3px solid var(--vermilion); padding:9px 14px; margin-bottom:16px; color:#6d4037; }
        hr { border-color:var(--line); }
        [data-testid="stDataFrame"] { border:1px solid var(--line); }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="warn-bar">' + L(
            "本工具僅供教育與研究使用，不會送出真實訂單，也不是投資建議。",
            "This tool is for education and research. It places no real orders and is not investment advice.",
        ) + "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="page-header"><h2>' + L("市場總覽", "Market Overview") + "</h2><p>"
        + L("先讀市場，再看 sector strength；辨識 Risk-On、Risk-Off 與資金輪動。",
            "Read the market first: identify Risk-On, Risk-Off and sector rotation.")
        + "</p></div>", unsafe_allow_html=True)

    with st.sidebar:
        st.radio(L("語言", "Language"), ["zh-TW", "en"], format_func=lambda x: "繁體中文" if x == "zh-TW" else "English", horizontal=True, key="lang")
        st.markdown("### " + L("設定", "Settings"))
        custom = st.text_input(L("股票清單（逗號分隔）", "Ticker list (comma-separated)"), "", placeholder="AAPL, MSFT, NVDA", key="sidebar_tickers")
        clean = sanitize_tickers(custom)
        tickers = clean or list(DEFAULT_TICKERS)
        if custom.strip() and not clean:
            st.warning(L("股票代號無效，已恢復預設清單。", "Invalid ticker input; reverted to the default list."))
        st.divider()
        st.caption(L("研究池", "Research pool") + f": {len(tickers)} " + L("檔股票", "stocks"))
        st.caption(", ".join(tickers[:6]) + ("…" if len(tickers) > 6 else ""))

    page_market_pulse(tickers)
