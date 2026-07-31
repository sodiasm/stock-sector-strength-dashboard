"""security.py input validation tests (network-free)."""
from market_overview.config import MAX_TICKERS
from market_overview.security import sanitize_tickers


def test_valid_tickers_normalized_and_uppercased():
    assert sanitize_tickers("aapl, msft , NvDa") == ["AAPL", "MSFT", "NVDA"]


def test_rejects_html_injection():
    assert sanitize_tickers("<img src=x onerror=alert(1)>") == []


def test_rejects_sql_like_input():
    assert sanitize_tickers(" ; DROP TABLE users; ") == []


def test_deduplicates_preserving_order():
    assert sanitize_tickers("AAPL, AAPL, MSFT, aapl") == ["AAPL", "MSFT"]


def test_preserves_valid_special_symbols():
    assert sanitize_tickers("^GSPC, BRK-B, BF.B") == ["^GSPC", "BRK-B", "BF.B"]


def test_enforces_max_tickers_cap():
    raw = ",".join(f"AA{i}" for i in range(MAX_TICKERS + 20))
    assert len(sanitize_tickers(raw)) == MAX_TICKERS


def test_empty_input_returns_empty_list():
    assert sanitize_tickers("   ") == []
