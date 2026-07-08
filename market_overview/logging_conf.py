"""Merkezî logging yapılandırması.

Tek bir modül-düzeyi ``logger`` sağlar. Veri çekme katmanındaki hatalar akışı
bozmadan (hâlâ ``None``/boş dönerek) buraya kaydedilir; böylece sessizce
yutulmak yerine görünür olurlar.
"""
import logging

logger = logging.getLogger("market_overview")

if not logger.handlers:  # tekrarlı import'ta handler çoğaltma
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s", "%H:%M:%S")
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
