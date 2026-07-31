"""Central logging configuration."""

import logging

logger = logging.getLogger("market_overview")

if not logger.handlers:  # Avoid duplicating handlers on repeated imports.
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s", "%H:%M:%S")
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.WARNING)
    logger.propagate = False
