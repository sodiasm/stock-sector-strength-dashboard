"""Basit iki dilli (TR/EN) metin yardımcısı.

Aktif dil ``st.session_state["lang"]`` içinde tutulur (varsayılan "TR").
``L(tr, en)`` çağrısı render sırasında aktif dile göre doğru metni döndürür.
"""
import streamlit as st


def current_lang() -> str:
    """Aktif dil kodu: 'TR' veya 'EN' (varsayılan 'TR')."""
    return st.session_state.get("lang", "TR")


def L(tr: str, en: str) -> str:
    """Aktif dile göre TR veya EN metnini döndürür."""
    return en if current_lang() == "EN" else tr
