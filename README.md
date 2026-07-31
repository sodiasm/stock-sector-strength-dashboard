# Market Overview Dashboard

[![CI](https://github.com/sodiasm/stock-sector-strength-dashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/sodiasm/stock-sector-strength-dashboard/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A one-page market briefing dashboard for momentum swing traders. It combines
macro indicators, sector rotation, global markets, market breadth, momentum
scanners, technical charts, and trade-plan research in one Streamlit app.

> Educational and research use only. The app places no real orders and is not
> investment advice.

## Features

- Daily macro summary for major indices, VIX, rates, DXY, gold, oil, and Bitcoin.
- Risk-On / Risk-Off market context.
- Sector rotation grid for all 11 SPDR sector ETFs.
- Global markets across the Americas, Europe, and Asia-Pacific.
- S&P 500 market-regime indicator based on the 200-day moving average.
- VIX trend chart and market-leader cards.
- Qullamaggie-style momentum scanner and Minervini trend-template checks.
- Entry, stop, target, and risk/reward trade-plan research tools.
- EMA, RSI, MFI, OBV, ATR, relative-volume, ADR, breadth, RRG, and formation analysis.

## Tech stack

| Layer | Technology |
|---|---|
| UI | Streamlit |
| Data | yfinance / Yahoo Finance |
| Analysis | pandas, numpy |
| Charts | Plotly |

## Run locally

```powershell
git clone https://github.com/sodiasm/stock-sector-strength-dashboard.git sectorheatmap
cd sectorheatmap
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run trading_app.py
```

The app opens at `http://localhost:8501`.

## Streamlit Community Cloud

Create a new app from this repository with:

- Branch: `main`
- Main file: `trading_app.py`
- Secrets: none required

The app uses public Yahoo Finance data and does not require broker credentials.

## Project structure

```text
market_overview/
├── app.py            # Streamlit entry point and theme
├── config.py         # Ticker universes and constants
├── data.py           # Yahoo Finance data access
├── indicators.py     # Technical indicators
├── signals.py        # Setups, scores, and signals
├── scanners.py       # Market and momentum scanners
├── breadth.py        # Breadth and sector-rotation analysis
├── charts.py         # Plotly chart builders
├── pages.py          # Streamlit page rendering
└── persistence.py    # Local sector snapshots
trading_app.py        # Streamlit Cloud entry point
tests/                # Network-free pytest suite
```

## License

MIT
