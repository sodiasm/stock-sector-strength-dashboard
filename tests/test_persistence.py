import json

import pandas as pd
import pytest

from market_overview.persistence import save_daily_sector_snapshot


def test_daily_sector_snapshot_writes_json_and_csv(tmp_path):
    frame = pd.DataFrame([
        {"Sektör": "科技", "Sembol": "XLK", "Günlük %": 1.2, "Haftalık %": 3.4},
    ])

    json_path, csv_path = save_daily_sector_snapshot(
        frame, tmp_path, trading_date=pd.Timestamp("2026-07-30").date()
    )

    assert json_path.name == "2026-07-30.json"
    assert csv_path.name == "2026-07-30.csv"
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["trading_date"] == "2026-07-30"
    assert payload["record_count"] == 1
    assert pd.read_csv(csv_path)["trading_date"].iloc[0] == "2026-07-30"


def test_daily_sector_snapshot_rejects_empty_frame(tmp_path):
    with pytest.raises(ValueError):
        save_daily_sector_snapshot(pd.DataFrame(), tmp_path)
