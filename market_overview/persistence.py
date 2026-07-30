"""Local daily snapshots for sector-strength research."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd


def save_daily_sector_snapshot(
    frame: pd.DataFrame,
    output_dir: str | Path = "data/daily",
    trading_date: date | None = None,
) -> tuple[Path, Path]:
    """Write one deterministic JSON and CSV snapshot for a trading day."""
    if frame.empty:
        raise ValueError("Cannot save an empty sector snapshot")

    day = trading_date or date.today()
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    normalized = frame.copy()
    normalized.insert(0, "trading_date", day.isoformat())
    normalized = normalized.where(pd.notna(normalized), None)

    json_path = target / f"{day.isoformat()}.json"
    csv_path = target / f"{day.isoformat()}.csv"
    payload = {
        "trading_date": day.isoformat(),
        "record_count": len(normalized),
        "source": "yfinance",
        "sectors": normalized.to_dict(orient="records"),
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    normalized.to_csv(csv_path, index=False, encoding="utf-8")
    return json_path, csv_path
