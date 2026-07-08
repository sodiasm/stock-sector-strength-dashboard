"""yfinance/FINRA veri çekme ve opsiyon/short-volume yardımcıları."""

import functools
import time
from datetime import datetime

import pandas as pd
import streamlit as st
import yfinance as yf

from market_overview.config import STOCK_SECTOR_MAP
from market_overview.logging_conf import logger


def retry(attempts: int = 3, base_delay: float = 0.5):
    """Ağ çağrılarını exponential backoff ile yeniden dener (0.5s, 1s, 2s).

    Yalnızca exception'da tekrar dener. Tüm denemeler tükenirse hatayı loglar
    ve ``None`` döner — böylece çağıran taraf mevcut davranışı (None) korur.
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            delay = base_delay
            for attempt in range(attempts):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:  # noqa: BLE001 — bilinçli geniş yakalama
                    if attempt == attempts - 1:
                        logger.warning("%s %d denemede başarısız: %s", fn.__name__, attempts, e)
                        return None
                    time.sleep(delay)
                    delay *= 2
            return None
        return wrapper
    return decorator


@st.cache_data(ttl=3600)
def get_float_shares(ticker: str) -> float | None:
    """Hissenin dolaşımdaki float hissesi sayısını çeker (milyon cinsinden)."""
    try:
        info = yf.Ticker(ticker).info
        fs = info.get("floatShares") or info.get("sharesOutstanding")
        return round(fs / 1e6, 1) if fs else None
    except Exception as e:
        logger.warning("%s float verisi çekilemedi: %s", ticker, e)
        return None


def sector_rs(ticker: str, df: pd.DataFrame) -> dict:
    """
    Hissenin kendi sektör ETF'ine karşı göreli gücünü hesaplar.
    Sektör ETF'inden güçlüyse = sektör lideri.
    """
    # Hangi sektörde?
    sector_etf = None
    for etf, stocks in STOCK_SECTOR_MAP.items():
        if ticker in stocks:
            sector_etf = etf
            break
    if not sector_etf:
        return {"vs_sector": None, "sector_etf": None}

    etf_df = fetch_daily(sector_etf, "3mo")
    if etf_df is None or len(etf_df) < 20:
        return {"vs_sector": None, "sector_etf": sector_etf}

    # Son 3 ay getirisi: hisse vs ETF
    stock_ret = (float(df["Close"].iloc[-1]) / float(df["Close"].iloc[-63]) - 1) * 100 if len(df) >= 63 else 0
    etf_ret   = (float(etf_df["Close"].iloc[-1]) / float(etf_df["Close"].iloc[-63]) - 1) * 100 if len(etf_df) >= 63 else 0
    vs_sector = round(stock_ret - etf_ret, 1)

    return {"vs_sector": vs_sector, "sector_etf": sector_etf,
            "stock_ret": round(stock_ret, 1), "etf_ret": round(etf_ret, 1)}


@st.cache_data(ttl=180, show_spinner=False)
@retry()
def fetch_daily(ticker: str, period: str = "3mo") -> pd.DataFrame | None:
    """Günlük veri (Piyasa Nabzı için, kısa cache = canlıya yakın).

    Ağ hatalarında :func:`retry` ile 3 kez denenir; kalıcı hatada ``None`` döner.
    """
    df = yf.download(ticker, period=period, interval="1d",
                     progress=False, auto_adjust=True)
    if df is None or len(df) < 2:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna()


@st.cache_data(ttl=300, show_spinner=False)
@retry()
def fetch_data(ticker: str, period: str, interval: str) -> pd.DataFrame | None:
    """Belirtilen periyot/aralıkta veri çeker; ağ hatalarında yeniden dener."""
    df = yf.download(ticker, period=period, interval=interval,
                     progress=False, auto_adjust=True)
    if df is None or len(df) < 30:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna()


@st.cache_data(ttl=1800)
def options_flow(ticker: str, max_expiries: int = 3) -> dict:
    """
    yfinance opsiyon zinciriyle ücretsiz opsiyon-akışı vekili.
    Gerçek 'flow' (paralı feed) değildir; kamuya açık hacim + açık pozisyon
    (OI) verisinden Put/Call dengesi ve olağandışı kontratları çıkarır.
    Olağandışı = günlük hacim > mevcut OI (yeni pozisyon akını) ve hacim >= 500.
    """
    try:
        tk = yf.Ticker(ticker)
        expiries = list(tk.options[:max_expiries])
    except Exception as e:
        logger.warning("%s opsiyon vadeleri çekilemedi: %s", ticker, e)
        return {"ok": False}
    if not expiries:
        return {"ok": False}

    call_vol = put_vol = call_oi = put_oi = 0.0
    unusual = []
    for exp in expiries:
        try:
            chain = tk.option_chain(exp)
        except Exception as e:
            logger.warning("%s %s opsiyon zinciri çekilemedi: %s", ticker, exp, e)
            continue
        for df_o, is_call in ((chain.calls, True), (chain.puts, False)):
            if df_o is None or df_o.empty:
                continue
            v = df_o["volume"].fillna(0)
            oi = df_o["openInterest"].fillna(0)
            if is_call:
                call_vol += float(v.sum()); call_oi += float(oi.sum())
            else:
                put_vol += float(v.sum()); put_oi += float(oi.sum())
            udf = df_o.assign(volume=v, openInterest=oi)
            mask = (udf["volume"] > udf["openInterest"]) & (udf["volume"] >= 500)
            for _, row in udf[mask].iterrows():
                unusual.append({
                    "Yön": "CALL" if is_call else "PUT",
                    "Vade": exp,
                    "Strike": float(row["strike"]),
                    "Hacim": int(row["volume"]),
                    "OI": int(row["openInterest"]),
                    "Son $": round(float(row.get("lastPrice", 0) or 0), 2),
                })
    total_vol = call_vol + put_vol
    if total_vol <= 0:
        return {"ok": False}
    unusual.sort(key=lambda x: x["Hacim"], reverse=True)
    return {
        "ok": True,
        "call_vol": call_vol, "put_vol": put_vol,
        "call_oi": call_oi, "put_oi": put_oi,
        "pc_ratio": (put_vol / call_vol) if call_vol > 0 else None,
        "unusual": unusual[:15],
        "expiries": expiries,
    }


@st.cache_data(ttl=3600)
def finra_short_volume(symbols_tuple: tuple) -> dict:
    """
    FINRA'nın günlük konsolide short-hacim dosyası (CNMSshvol).
    Ücretsiz ve resmidir; borsa-dışı (off-exchange / dark pool) aktivite için
    sektörde yaygın kullanılan vekil göstergedir. Gerçek dark pool print'i
    değildir — short hacmin toplam hacme oranını verir (bir günlük gecikmeli).
    """
    import io
    import urllib.request
    from datetime import timedelta

    base = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{}.txt"
    day = datetime.now()
    for _ in range(6):  # en yakın yayınlanmış işlem gününü bul
        url = base.format(day.strftime("%Y%m%d"))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            raw = urllib.request.urlopen(req, timeout=12).read().decode("utf-8", "ignore")
            header = raw.split("\n", 1)[0]
            if "Symbol" in header:
                df = pd.read_csv(io.StringIO(raw), sep="|")
                df = df[df["Symbol"].notna() & (df["Symbol"] != "Total")]
                sub = df[df["Symbol"].isin(symbols_tuple)].copy()
                if sub.empty:
                    return {"ok": False, "reason": "havuzdaki hisseler dosyada yok"}
                sub["Short %"] = (sub["ShortVolume"] / sub["TotalVolume"] * 100).round(1)
                sub = sub.sort_values("Short %", ascending=False)
                return {"ok": True, "date": day.strftime("%d.%m.%Y"), "df": sub}
        except Exception as e:
            logger.warning("FINRA short-hacim %s çekilemedi: %s", day.strftime("%Y%m%d"), e)
        day -= timedelta(days=1)
    return {"ok": False, "reason": "FINRA verisi çekilemedi"}
