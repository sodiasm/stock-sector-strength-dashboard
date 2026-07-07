
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import random
import re
from datetime import datetime

# ---------------------------------------------------------------------------
# GÜVENLİK: kullanıcı girdisi doğrulama (sınırda temizle)
# ---------------------------------------------------------------------------
# Geçerli sembol karakterleri: harf, rakam, nokta, tire, ^ (endeksler). Bu
# beyaz-liste, kullanıcı girdisinin HTML'e (unsafe_allow_html) veya dış
# servis URL'lerine enjekte edilmesini (XSS / injection) engeller.
TICKER_RE = re.compile(r"^[A-Z0-9.\-^]{1,10}$")
MAX_TICKERS = 50  # aşırı sorgu/DoS'a karşı üst sınır


def sanitize_tickers(raw: str) -> list:
    """Ham kullanıcı girdisini güvenli, tekrarsız sembol listesine indirger."""
    seen, out = set(), []
    for part in raw.split(","):
        sym = part.strip().upper()
        if sym and TICKER_RE.match(sym) and sym not in seen:
            seen.add(sym)
            out.append(sym)
        if len(out) >= MAX_TICKERS:
            break
    return out

# ===========================================================================
# SABİTLER
# ===========================================================================

DEFAULT_TICKERS = [
    "AAPL", "MSFT", "NVDA", "TSLA", "AMD", "META", "AMZN", "GOOGL",
    "PLTR", "COIN", "NFLX", "AVGO", "SMCI", "MU", "INTC", "JPM",
    "V", "WMT", "DIS", "BA",
]

PERIOD_INTERVAL_MAP = {
    "5 Gün / 15dk": ("5d", "15m"),
    "1 Ay / 1saat": ("1mo", "1h"),
    "3 Ay / Günlük": ("3mo", "1d"),
    "6 Ay / Günlük": ("6mo", "1d"),
    "1 Yıl / Günlük": ("1y", "1d"),
}

# Momentum / breakout taraması için geniş evren (Qullamaggie/Minervini tarzı adaylar)
MOMENTUM_UNIVERSE = [
    "NVDA", "ARM", "SMCI", "PLTR", "COIN", "FCEL", "FLNC", "MSTR", "APP", "VRT",
    "CLS", "POWL", "ANET", "AVGO", "MU", "AMD", "TSLA", "NET", "CRWD", "DDOG",
    "SHOP", "PANW", "SNOW", "MARA", "RIOT", "CVNA", "AFRM", "SOFI", "DKNG", "RDDT",
    "HOOD", "IONQ", "RGTI", "OKLO", "SMR", "TSM", "ASML", "META", "AMZN", "GOOGL",
]

# Nasdaq-100 (yaklaşık) — daha geniş ve anlamlı RS sıralaması için
NASDAQ100 = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "AVGO", "TSLA", "COST",
    "NFLX", "ASML", "AMD", "PEP", "ADBE", "LIN", "CSCO", "TMUS", "INTU", "QCOM",
    "TXN", "AMGN", "ISRG", "AMAT", "BKNG", "HON", "VRTX", "PANW", "ADP", "MU",
    "ADI", "GILD", "REGN", "LRCX", "MELI", "SBUX", "MDLZ", "KLAC", "SNPS", "CDNS",
    "CRWD", "CEG", "MAR", "PYPL", "ORLY", "CSX", "ABNB", "MRVL", "FTNT", "DASH",
    "WDAY", "ADSK", "NXPI", "ROP", "TTD", "CHTR", "PCAR", "MNST", "AEP", "PAYX",
    "KDP", "ODFL", "FAST", "EA", "CTAS", "VRSK", "DDOG", "EXC", "GEHC", "KHC",
    "CCEP", "LULU", "BKR", "XEL", "CSGP", "IDXX", "ON", "TEAM", "ANSS", "ZS",
    "CDW", "BIIB", "DXCM", "MCHP", "TTWO", "GFS", "ILMN", "WBD", "ARM", "PLTR",
    "APP", "MSTR", "SMCI", "COIN",
]

# S&P 500 geniş evreni — Qullamaggie taraması için (~500 hisse, büyük cap)
SP500_UNIVERSE = sorted(set(NASDAQ100 + [
    "JPM", "BAC", "WFC", "GS", "MS", "C", "USB", "PNC", "TFC", "COF",
    "BLK", "SCHW", "AXP", "CB", "MMC", "ICE", "CME", "SPGI", "MCO", "AON",
    "JNJ", "UNH", "LLY", "PFE", "ABBV", "MRK", "BMY", "ABT", "TMO", "DHR",
    "SYK", "BSX", "MDT", "EW", "ZBH", "BDX", "HOLX", "ALGN", "IDXX", "MTD",
    "ORCL", "CRM", "NOW", "SAP", "INTU", "ADBE", "SNPS", "CDNS", "ANSS", "PTC",
    "UBER", "LYFT", "ABNB", "BKNG", "EXPE", "MAR", "HLT", "WYNN", "LVS", "MGM",
    "AMZN", "SHOP", "ETSY", "EBAY", "W", "CHWY", "CVNA", "CARVANA", "KR", "COST",
    "WMT", "TGT", "HD", "LOW", "BBY", "DG", "DLTR", "FIVE", "OLLI",
    "XOM", "CVX", "COP", "SLB", "HAL", "BKR", "PSX", "VLO", "MPC", "DVN",
    "NEE", "DUK", "SO", "AEP", "EXC", "SRE", "PEG", "D", "ETR", "PPL",
    "LIN", "APD", "ECL", "SHW", "PPG", "IFF", "ALB", "MP", "ENPH", "FSLR",
    "CAT", "DE", "EMR", "ETN", "ROK", "AME", "VRSK", "GE", "HON", "MMM",
    "UPS", "FDX", "XPO", "SAIA", "ODFL", "JBHT", "KNX", "CHRW",
    "NFLX", "DIS", "PARA", "WBD", "FOX", "FOXA", "CMCSA", "CHTR", "TMUS",
    "V", "MA", "PYPL", "SQ", "FI", "FIS", "GPN", "WEX", "AFRM", "SOFI",
    "TSLA", "GM", "F", "RIVN", "LCID", "TM", "HMC", "STLA",
    "BA", "LMT", "RTX", "NOC", "GD", "L3H", "TDG", "HWM", "SPR", "KTOS",
    "DECK", "NKE", "LULU", "UAA", "VFC", "RL", "PVH", "TPR",
    "MCD", "SBUX", "YUM", "QSR", "CMG", "DKNG", "PENN", "VICI",
    "PLD", "AMT", "CCI", "EQIX", "DLR", "SPG", "O", "PSA", "EQR", "AVB",
    "LEN", "DHI", "PHM", "TOL", "NVR", "TMHC",
    "CELH", "MNST", "KO", "PEP", "KDP", "STZ", "BUD", "TAP",
    "FICO", "TYL", "MSCI", "NTRS", "BEN", "TROW", "IVZ", "AMG",
    "AXON", "TASER", "S", "OKTA", "ZS", "SAIL", "QLYS", "TENB",
    "MELI", "NU", "STNE", "PAGS", "XP", "GLOB", "ARCO",
    "RDDT", "SNAP", "PINS", "MTCH", "ZM", "DOCU", "DOCN", "CFLT",
    "GH", "EXAS", "NVAX", "MRNA", "BNTX", "REGN", "ALNY", "INCY",
    "HOOD", "COIN", "MSTR", "MARA", "RIOT", "CLSK", "CIFR",
    "IONQ", "RGTI", "QBTS", "OKLO", "SMR", "NNE", "BWXT", "CEG", "VST",
    "PLTR", "AI", "BBAI", "SOUN", "IREN", "CORZ",
    "VRT", "ANET", "SMCI", "CLS", "POWL", "ASTS", "RDW",
]))

# Renkler
C_UP = "#16c784"
C_DOWN = "#ea3943"
C_ACCENT = "#3b82f6"
C_PURPLE = "#a855f7"
C_GOLD = "#f0b90b"

# Makro / piyasa geneli enstrümanlar (risk iştahı okuması için)
MACRO_ASSETS = {
    "^GSPC": "S&P 500",
    "^IXIC": "Nasdaq",
    "QQQ":   "QQQ (Nasdaq ETF)",
    "^DJI":  "Dow Jones",
    "^RUT":  "Russell 2000",
    "^VIX":  "VIX (Korku)",
    "^TNX":  "10Y Faiz",
    "DX-Y.NYB": "Dolar (DXY)",
    "GC=F":  "Altın",
    "CL=F":  "Petrol",
    "BTC-USD": "Bitcoin",
}

# Dünya borsaları — bölgeye göre gruplandırılmış
GLOBAL_INDICES = {
    "Amerika": {
        "^GSPC": {"isim": "S&P 500", "ulke": ""},
        "^IXIC": {"isim": "Nasdaq", "ulke": ""},
        "QQQ": {"isim": "QQQ", "ulke": ""},
        "^RUT": {"isim": "Russell 2000", "ulke": ""},
        "^BVSP": {"isim": "Bovespa", "ulke": ""},
    },
    "Avrupa": {
        "^FTSE": {"isim": "FTSE 100", "ulke": ""},
        "^GDAXI": {"isim": "DAX", "ulke": ""},
        "^FCHI": {"isim": "CAC 40", "ulke": ""},
        "^STOXX50E":{"isim": "Euro Stoxx", "ulke": ""},
        "XU100.IS": {"isim": "BIST 100", "ulke": ""},
    },
    "Asya-Pasifik": {
        "^N225": {"isim": "Nikkei 225", "ulke": ""},
        "^KS11": {"isim": "KOSPI", "ulke": ""},
        "^HSI": {"isim": "Hang Seng", "ulke": ""},
        "000001.SS":{"isim": "Shanghai", "ulke": ""},
        "^NSEI": {"isim": "NIFTY 50", "ulke": ""},
        "^AXJO": {"isim": "ASX 200", "ulke": ""},
    },
}

# Sektör ETF'leri (para hangi sektöre akıyor - sektör rotasyonu)
SECTOR_ETFS = {
    "XLK": "Teknoloji",
    "XLF": "Finans",
    "XLE": "Enerji",
    "XLV": "Sağlık",
    "XLY": "Tüketici (İsteğe Bağlı)",
    "XLP": "Tüketici (Temel)",
    "XLI": "Sanayi",
    "XLB": "Hammadde",
    "XLU": "Kamu Hizmetleri",
    "XLRE": "Gayrimenkul",
    "XLC": "İletişim",
}

# Sektör ETF eşlemesi — RS hesabı için
STOCK_SECTOR_MAP = {
    "XLK": ["NVDA","AMD","MSFT","AAPL","AVGO","ANET","MU","SMCI","ARM","INTC","QCOM","TXN","ADI","LRCX","AMAT","KLAC","MRVL"],
    "XLC": ["META","GOOGL","GOOG","NFLX","SNAP","RDDT","PINS","TTWO","EA"],
    "XLY": ["TSLA","AMZN","SHOP","CVNA","DKNG","ABNB","BKNG","MAR","ORLY"],
    "XLF": ["JPM","V","MA","GS","MS","BAC","COIN","HOOD","SOFI","AFRM"],
    "XLE": ["XOM","CVX","COP","SLB","OXY","PSX","VLO","MPC"],
    "XLV": ["LLY","JNJ","UNH","ABT","TMO","DHR","ISRG","VRTX","REGN","AMGN","GILD","IDXX","DXCM"],
    "XLI": ["GE","HON","CAT","DE","LMT","RTX","NOC","POWL","VRT","CLS"],
}

# ===========================================================================
# TEKNİK HESAPLAMALAR
# ===========================================================================

def compute_ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def compute_mfi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Money Flow Index — hacim ağırlıklı RSI; para girişi/çıkışını ölçer."""
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    mf = tp * df["Volume"]
    pos = mf.where(tp > tp.shift(), 0.0)
    neg = mf.where(tp < tp.shift(), 0.0)
    pos_sum = pos.rolling(period).sum()
    neg_sum = neg.rolling(period).sum()
    mfr = pos_sum / neg_sum.replace(0, np.nan)
    return 100 - (100 / (1 + mfr))


def compute_obv(df: pd.DataFrame) -> pd.Series:
    """On-Balance Volume — hacmi fiyat yönüne göre toplar; birikim/dağıtım izi."""
    direction = np.sign(df["Close"].diff()).fillna(0)
    return (direction * df["Volume"]).cumsum()


def relative_volume(df: pd.DataFrame, window: int = 20) -> float:
    """Bugünkü hacim / son `window` günün ortalaması. >1.5 = olağandışı ilgi."""
    if len(df) < window + 1:
        return 1.0
    avg = df["Volume"].iloc[-window - 1:-1].mean()
    return float(df["Volume"].iloc[-1] / avg) if avg > 0 else 1.0


def compute_adr_pct(df: pd.DataFrame, period: int = 20) -> float:
    """Average Daily Range % — günlük volatilite (Qullamaggie/Minervini metriği)."""
    if len(df) < period + 1:
        period = max(2, len(df) - 1)
    dr = df["High"] / df["Low"]
    return float((dr.iloc[-period:].mean() - 1) * 100)


def momentum_score(df: pd.DataFrame) -> float:
    """IBD tarzı ağırlıklı getiri (göreli güç ham puanı)."""
    c = df["Close"]
    def ret(n):
        return c.iloc[-1] / c.iloc[-n] - 1 if len(c) > n else c.iloc[-1] / c.iloc[0] - 1
    return 0.4 * ret(63) + 0.3 * ret(126) + 0.2 * ret(189) + 0.1 * ret(252)


def trend_template(df: pd.DataFrame) -> dict:
    """Minervini Trend Template kontrolleri + Qullamaggie EMA bulutu durumu."""
    c = df["Close"]
    price = float(c.iloc[-1])
    ema10 = compute_ema(c, 10).iloc[-1]
    ema20 = compute_ema(c, 20).iloc[-1]
    sma50 = c.rolling(50).mean().iloc[-1] if len(c) >= 50 else c.mean()
    sma150 = c.rolling(150).mean().iloc[-1] if len(c) >= 150 else c.mean()
    sma200 = c.rolling(200).mean().iloc[-1] if len(c) >= 200 else c.mean()
    sma200_prev = c.rolling(200).mean().iloc[-21] if len(c) >= 221 else sma200
    high52 = float(c.iloc[-252:].max()) if len(c) >= 60 else float(c.max())
    low52 = float(c.iloc[-252:].min()) if len(c) >= 60 else float(c.min())

    checks = {
        "Fiyat > 50MA": price > sma50,
        "50MA > 150MA": sma50 > sma150,
        "150MA > 200MA": sma150 > sma200,
        "200MA yükseliyor": sma200 > sma200_prev,
        "52H zirvenin %25'i içinde": price >= high52 * 0.75,
        "52H dipten %30+ yukarı": price >= low52 * 1.30,
        "Bulut üstünde (EMA10>EMA20)": price > ema10 and ema10 > ema20,
    }
    return {
        "passed": sum(checks.values()),
        "total": len(checks),
        "checks": checks,
        "above_cloud": price > ema10 > ema20,
        "above_50": price > sma50,
        "pct_from_high": round((price / high52 - 1) * 100, 1),
        "high52": round(high52, 2),
    }


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


@st.cache_data(ttl=3600)
def get_float_shares(ticker: str) -> float | None:
    """Hissenin dolaşımdaki float hissesi sayısını çeker (milyon cinsinden)."""
    try:
        info = yf.Ticker(ticker).info
        fs = info.get("floatShares") or info.get("sharesOutstanding")
        return round(fs / 1e6, 1) if fs else None
    except Exception:
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


def wilder_atr(df: pd.DataFrame, period: int) -> pd.Series:
    """TradingView atr() ile uyumlu Wilder (RMA) ATR."""
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


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
    rsi = compute_rsi(close)
    last_close = close.iloc[-1]
    last_rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
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


# ===========================================================================
# VERİ ÇEKME (cache'li)
# ===========================================================================

@st.cache_data(ttl=180, show_spinner=False)
def fetch_daily(ticker: str, period: str = "3mo") -> pd.DataFrame | None:
    """Günlük veri (Piyasa Nabzı için, kısa cache = canlıya yakın)."""
    try:
        df = yf.download(ticker, period=period, interval="1d",
                         progress=False, auto_adjust=True)
        if df is None or len(df) < 2:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df.dropna()
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_data(ticker: str, period: str, interval: str) -> pd.DataFrame | None:
    try:
        df = yf.download(ticker, period=period, interval=interval,
                         progress=False, auto_adjust=True)
        if df is None or len(df) < 30:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df.dropna()
    except Exception:
        return None


# ===========================================================================
# BACKTEST
# ===========================================================================

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


# ===========================================================================
# PİYASA TARAYICI
# ===========================================================================

def scan_market(tickers: list, period: str, interval: str,
                key_value: float, atr_period: int, lookback: int) -> pd.DataFrame:
    """Her hisse için son `lookback` mumda sinyal var mı kontrol eder."""
    rows = []
    progress = st.progress(0.0, text="Hisseler taranıyor...")
    for i, t in enumerate(tickers):
        progress.progress((i + 1) / len(tickers), text=f"Taranıyor: {t}")
        df = fetch_data(t, period, interval)
        if df is None or len(df) < atr_period + 5:
            continue
        sig = ut_bot_signals(df, key_value, atr_period)
        recent = sig.iloc[-lookback:]
        last = sig.iloc[-1]

        signal = "—"
        bars_ago = None
        if recent["buy"].any():
            signal = "AL"
            bars_ago = lookback - 1 - int(np.where(recent["buy"].values)[0][-1])
        if recent["sell"].any():
            sell_idx = lookback - 1 - int(np.where(recent["sell"].values)[0][-1])
            if signal == "—" or sell_idx < bars_ago:
                signal = "SAT"
                bars_ago = sell_idx

        score = compute_score(df)
        chg = (df["Close"].iloc[-1] - df["Close"].iloc[-2]) / df["Close"].iloc[-2] * 100
        price = float(df["Close"].iloc[-1])
        ut_stop = float(last["stop"])
        bias = "LONG" if last["pos"] == 1 else "SHORT"
        stop_dist = (price - ut_stop) / price * 100
        rows.append({
            "Hisse": t,
            "Sinyal": signal,
            "Eğilim": bias,
            "Kaç Mum Önce": bars_ago if bars_ago is not None else "—",
            "Fiyat": round(price, 2),
            "UT Stop": round(ut_stop, 2),
            "Stop Mesafe %": round(stop_dist, 2),
            "Günlük %": round(float(chg), 2),
            "Skor": score["total"],
            "RSI": score["rsi_val"],
            "Sistem": system_decision(score["total"]),
        })
    progress.empty()
    return pd.DataFrame(rows)


# ===========================================================================
# GRAFİKLER
# ===========================================================================

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


# ===========================================================================
# TRADE PLANI — Gerçek borsada kullanılabilir işlem parametreleri
# ===========================================================================
# Profesyonel trader'ların her işlemde hesapladığı şeyler:
#   - Giriş fiyatı
#   - Stop-loss (ATR / UT trailing stop bazlı) -> nerede yanıldığını kabul edersin
#   - Kâr hedefleri TP1 (1.5R) ve TP2 (3R)     -> risk/ödül planı
#   - Risk/Ödül oranı (R:R)
#   - Pozisyon büyüklüğü -> hesabının yalnızca %X'ini riske atacak lot sayısı
#   - Trend filtresi (EMA50) -> trende karşı işlemden kaçınma

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


# ===========================================================================
# SAYFALAR
# ===========================================================================

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


# ===========================================================================
# OPSİYON AKIŞI (yfinance opsiyon zinciri — ÜCRETSİZ)
# ===========================================================================

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
    except Exception:
        return {"ok": False}
    if not expiries:
        return {"ok": False}

    call_vol = put_vol = call_oi = put_oi = 0.0
    unusual = []
    for exp in expiries:
        try:
            chain = tk.option_chain(exp)
        except Exception:
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


# ===========================================================================
# DARK POOL / OFF-EXCHANGE (FINRA günlük short-hacim — ÜCRETSİZ, RESMİ)
# ===========================================================================

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
        except Exception:
            pass
        day -= timedelta(days=1)
    return {"ok": False, "reason": "FINRA verisi çekilemedi"}


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


@st.cache_data(ttl=1800)
def scan_qullamaggie_yf(universe: list, min_perf1y: float = 50,
                         min_cap_b: float = 2.0, min_adr_pct: float = 3.5) -> tuple:
    """
    yfinance ile Qullamaggie filtreleri (tamamen yasal, yayın için uygun):
    - Fiyat > EMA100  (~21 haftalık EMA)
    - Fiyat > EMA200  (~50 haftalık EMA)
    - 1Y Performans > min_perf1y%
    - Vol 10G ort > Vol 90G ort  (hacim artıyor)
    - ADR% > min_adr_pct%
    - Piyasa Değeri > min_cap_b milyar $
    30 dakika cache — yfinance batch ile ~300 hisseyi 15-20 sn'de tarar.
    """
    import yfinance as yf

    if not universe:
        return pd.DataFrame(), 0

    # Batch download — tüm hisseleri tek seferde çek (çok daha hızlı)
    raw = yf.download(
        universe, period="1y", interval="1d",
        group_by="ticker", auto_adjust=True,
        progress=False, threads=True,
    )

    rows = []
    price_1y_ago = {}

    for ticker in universe:
        try:
            if len(universe) == 1:
                df = raw.copy()
            else:
                df = raw[ticker].dropna(how="all")

            if df is None or len(df) < 60:
                continue

            close  = df["Close"].dropna()
            volume = df["Volume"].dropna()
            high   = df["High"].dropna()
            low    = df["Low"].dropna()

            if len(close) < 60:
                continue

            price_now  = float(close.iloc[-1])
            price_prev = float(close.iloc[-2]) if len(close) > 1 else price_now

            # EMA hesapla
            ema100 = float(close.ewm(span=100, adjust=False).mean().iloc[-1])
            ema200 = float(close.ewm(span=200, adjust=False).mean().iloc[-1])
            ema10  = float(close.ewm(span=10,  adjust=False).mean().iloc[-1])
            ema20  = float(close.ewm(span=20,  adjust=False).mean().iloc[-1])

            # Filtre 1: Fiyat > EMA100 ve EMA200
            if price_now <= ema100 or price_now <= ema200:
                continue

            # 1Y performans
            perf_1y = (price_now / float(close.iloc[0]) - 1) * 100
            if perf_1y < min_perf1y:
                continue

            # Hacim artışı: 10 günlük ort > 90 günlük ort
            vol10  = float(volume.iloc[-10:].mean())
            vol90  = float(volume.iloc[-90:].mean())
            if vol10 <= vol90:
                continue

            # ADR%: son 14 günün ortalama günlük aralığı
            daily_range = ((high - low) / close * 100).iloc[-14:]
            adr_pct = float(daily_range.mean())
            if adr_pct < min_adr_pct:
                continue

            # Haftalık / aylık / 3 aylık performans
            perf_w  = (price_now / float(close.iloc[-5])  - 1) * 100 if len(close) >= 5  else 0
            perf_1m = (price_now / float(close.iloc[-21]) - 1) * 100 if len(close) >= 21 else 0
            perf_3m = (price_now / float(close.iloc[-63]) - 1) * 100 if len(close) >= 63 else 0

            # RVOL: bugünkü hacim / 10 günlük ort
            vol_today = float(volume.iloc[-1])
            rvol = round(vol_today / vol90, 2) if vol90 > 0 else 0

            # Piyasa değeri (yaklaşık — fiyat * ortalama hacim proxy, gerçek için yf.Ticker kullan)
            # Gerçek market cap bilgisi için ayrı çekim gerekir, burada hisse başına fiyat kullanıyoruz
            # Büyük cap evreni kullandığımız için bu filtre evrende zaten uygulanmış sayılır
            rows.append({
                "Ticker":      ticker,
                "Fiyat":       round(price_now, 2),
                "Günlük %":    round((price_now / price_prev - 1) * 100, 2),
                "1Y %":        round(perf_1y, 1),
                "Haftalık %":  round(perf_w, 1),
                "Aylık %":     round(perf_1m, 1),
                "3 Aylık %":   round(perf_3m, 1),
                "ADR%":        round(adr_pct, 2),
                "RVOL":        rvol,
                "EMA100":      round(ema100, 2),
                "EMA200":      round(ema200, 2),
                "EMA100 ↑%":   round((price_now / ema100 - 1) * 100, 1),
                "EMA200 ↑%":   round((price_now / ema200 - 1) * 100, 1),
                "EMA10":       round(ema10, 2),
                "EMA20":       round(ema20, 2),
                "Vol 10G":     int(vol10),
                "Vol 90G":     int(vol90),
                "_close":      close,
            })
        except Exception:
            continue

    if not rows:
        return pd.DataFrame(), 0

    result = pd.DataFrame(rows).sort_values("RVOL", ascending=False).reset_index(drop=True)
    return result, len(result)


def scan_momentum(universe: list, min_rs: int, min_adr: float) -> pd.DataFrame:
    """Qullamaggie/Minervini momentum breakout taraması."""
    rows = []
    prog = st.progress(0.0, text="Momentum taraması...")
    raw = []
    for i, t in enumerate(universe):
        prog.progress((i + 1) / len(universe), text=f"Taranıyor: {t}")
        df = fetch_daily(t, "1y")
        if df is None or len(df) < 60:
            continue
        raw.append((t, df, momentum_score(df)))

    if not raw:
        prog.empty()
        return pd.DataFrame()

    # RS Rating: havuz içi yüzdelik sıralama (1-99)
    scores = pd.Series({t: s for t, _, s in raw}).rank(pct=True) * 98 + 1

    for t, df, _ in raw:
        tt   = trend_template(df)
        adr  = compute_adr_pct(df)
        rs   = int(round(scores[t]))
        setup = detect_setup(df)
        chg  = (df["Close"].iloc[-1] - df["Close"].iloc[-2]) / df["Close"].iloc[-2] * 100
        rvol = relative_volume(df)
        stealth = stealth_accumulation(df, 10)
        sec_rs  = sector_rs(t, df)
        rows.append({
            "Hisse": t,
            "Setup": setup,
            "RS": rs,
            "Sektör RS": sec_rs.get("vs_sector"),
            "ADR %": round(adr, 1),
            "Trend": f"{tt['passed']}/{tt['total']}",
            "Zirveye %": tt["pct_from_high"],
            "Gör. Hacim": round(rvol, 2),
            "Günlük %": round(float(chg), 2),
            "Fiyat": round(float(df["Close"].iloc[-1]), 2),
            "Birikim": stealth["score"],
            "_pass": tt["passed"], "_adr": adr, "_rs": rs,
            "_above": tt["above_cloud"] and tt["above_50"],
            "_stealth": stealth["signal"],
        })
    prog.empty()
    df = pd.DataFrame(rows)
    # Filtre: RS ve ADR eşiği + trend yapısı sağlam
    df = df[(df["_rs"] >= min_rs) & (df["_adr"] >= min_adr) & (df["_above"])]
    return df.sort_values(["_pass", "_rs"], ascending=False)




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

    # ---------- 1) MAKRO TABLO ----------
    st.markdown("### Günlük Makro Özet")
    macro_rows, spx_chg, vix_chg, ndx_chg = [], 0, 0, 0
    for sym, name in MACRO_ASSETS.items():
        df = fetch_daily(sym, "5d")
        if df is None or len(df) < 2:
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



# ===========================================================================
# ===========================================================================
# GELİŞİM & PRATİK
# ===========================================================================

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


if __name__ == "__main__":
    main()
