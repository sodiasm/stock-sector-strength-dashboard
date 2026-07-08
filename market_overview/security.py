"""Kullanıcı girdisi doğrulama (sınırda temizleme)."""

from market_overview.config import MAX_TICKERS, TICKER_RE


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
