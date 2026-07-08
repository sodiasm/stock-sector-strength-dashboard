"""Streamlit Cloud entry point.

The application lives in the ``market_overview`` package; this thin shim keeps
the existing deploy command (``streamlit run trading_app.py``) working.
"""
from market_overview.app import main

main()
