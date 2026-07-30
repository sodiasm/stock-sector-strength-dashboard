"""Bilingual text helper with Traditional Chinese as the default."""

import streamlit as st


_ZH_OVERRIDES = {
    "Piyasa Nabzı": "市場脈搏",
    "Günlük Makro Özet": "每日宏觀摘要",
    "Sektör Rotasyonu — Para Nereye Akıyor?": "Sector 輪動 — 資金流向哪裡？",
    "Dünya Borsaları": "全球市場",
    "Piyasa Rejimi Göstergesi": "市場狀態指標",
    "VIX — Korku Endeksi (5 Gün)": "VIX — 恐慌指數（5 日）",
    "Öncü Hisseler — Piyasa Barometresi": "領先股票 — 市場晴雨表",
    "Günün Yorumu": "每日市場摘要",
    "Piyasa Sağlığı — Düşüş Radarı": "市場健康度 — 下跌雷達",
    "Sektör Rotasyonu — RRG": "Sector 輪動 — RRG",
    "Qullamaggie Filtre Tarayıcısı": "Qullamaggie 篩選器",
    "Hisse Grafiği & Trade Planı": "股票圖表與交易計劃",
    "Yenile": "重新整理",
    "Son güncelleme:": "最後更新：",
    "Amerika": "美洲",
    "Avrupa": "歐洲",
    "Asya-Pasifik": "亞太地區",
    "haftalık": "每週",
    "bugün": "今日",
    "Hisse seç": "選擇股票",
    "Veri yok": "沒有資料",
    "Giriş": "入場",
    "İyi": "良好",
    "Orta": "一般",
    "Zayıf": "偏弱",
    "Leading": "領先",
    "Weakening": "轉弱",
    "Lagging": "落後",
    "Improving": "改善中",
}


def current_lang() -> str:
    """Return the active session language code."""
    return st.session_state.get("lang", "zh-TW")


def L(zh_tw: str, en: str) -> str:
    """Return Traditional Chinese or English text for the active session."""
    return en if current_lang() == "en" else _ZH_OVERRIDES.get(zh_tw.strip(), zh_tw)
