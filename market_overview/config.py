"""Statik yapılandırma: sembol evrenleri, makro varlıklar, renkler, sabitler."""

import re

TICKER_RE = re.compile(r"^[A-Z0-9.\-^]{1,10}$")


MAX_TICKERS = 50  # aşırı sorgu/DoS'a karşı üst sınır


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


MOMENTUM_UNIVERSE = [
    "NVDA", "ARM", "SMCI", "PLTR", "COIN", "FCEL", "FLNC", "MSTR", "APP", "VRT",
    "CLS", "POWL", "ANET", "AVGO", "MU", "AMD", "TSLA", "NET", "CRWD", "DDOG",
    "SHOP", "PANW", "SNOW", "MARA", "RIOT", "CVNA", "AFRM", "SOFI", "DKNG", "RDDT",
    "HOOD", "IONQ", "RGTI", "OKLO", "SMR", "TSM", "ASML", "META", "AMZN", "GOOGL",
]


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


C_UP = "#2f7d5c"


C_DOWN = "#b94a46"


C_ACCENT = "#344f70"


C_PURPLE = "#6f628f"


C_GOLD = "#b87932"


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

MACRO_ASSETS_EN = {
    "^GSPC": "S&P 500", "^IXIC": "Nasdaq", "QQQ": "QQQ (Nasdaq ETF)", "^DJI": "Dow Jones",
    "^RUT": "Russell 2000", "^VIX": "VIX (Fear)", "^TNX": "10Y Yield", "DX-Y.NYB": "Dollar (DXY)",
    "GC=F": "Gold", "CL=F": "Oil", "BTC-USD": "Bitcoin",
}


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

GLOBAL_REGIONS_EN = {"Amerika": "Americas", "Avrupa": "Europe", "Asya-Pasifik": "Asia-Pacific"}


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

SECTOR_ETFS_EN = {
    "XLK": "Technology", "XLF": "Financials", "XLE": "Energy", "XLV": "Health Care",
    "XLY": "Consumer Discretionary", "XLP": "Consumer Staples", "XLI": "Industrials",
    "XLB": "Materials", "XLU": "Utilities", "XLRE": "Real Estate", "XLC": "Communication Services",
}


STOCK_SECTOR_MAP = {
    "XLK": ["NVDA","AMD","MSFT","AAPL","AVGO","ANET","MU","SMCI","ARM","INTC","QCOM","TXN","ADI","LRCX","AMAT","KLAC","MRVL"],
    "XLC": ["META","GOOGL","GOOG","NFLX","SNAP","RDDT","PINS","TTWO","EA"],
    "XLY": ["TSLA","AMZN","SHOP","CVNA","DKNG","ABNB","BKNG","MAR","ORLY"],
    "XLF": ["JPM","V","MA","GS","MS","BAC","COIN","HOOD","SOFI","AFRM"],
    "XLE": ["XOM","CVX","COP","SLB","OXY","PSX","VLO","MPC"],
    "XLV": ["LLY","JNJ","UNH","ABT","TMO","DHR","ISRG","VRTX","REGN","AMGN","GILD","IDXX","DXCM"],
    "XLI": ["GE","HON","CAT","DE","LMT","RTX","NOC","POWL","VRT","CLS"],
}
