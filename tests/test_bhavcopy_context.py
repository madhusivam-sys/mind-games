from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from dashboard.api_client import DashboardQuery
from dashboard.bhavcopy_context import build_bhavcopy_payload
from services.cpr_scanner import scan_latest


def _history() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    start = date(2026, 7, 7)
    for offset, close in enumerate([100.0, 103.0, 106.0, 109.0, 112.0]):
        rows.append(
            {
                "session_date": start + timedelta(days=offset),
                "symbol": "DEMO",
                "instrument": "FUTSTK",
                "asset_type": "F&O Stock Future",
                "open": close - 1.0,
                "high": close + 2.0,
                "low": close - 2.0,
                "close": close,
                "volume": 100_000 + offset * 5_000,
                "aggregate_volume": 150_000 + offset * 5_000,
                "aggregate_turnover": 15_000_000 + offset * 1_000_000,
                "aggregate_open_interest": 200_000 + offset * 10_000,
                "mwpl_utilization_pct": 52.0,
                "mwpl_ban": False,
            }
        )
    return pd.DataFrame(rows)


def test_bhavcopy_payload_runs_shared_dashboard_engine() -> None:
    history = _history()
    results = scan_latest(history)

    payload = build_bhavcopy_payload(history, results, DashboardQuery(symbol="DEMO", interval="1d", limit=20))

    assert payload["symbol"] == "DEMO"
    assert payload["data_source"] == "NSE F&O Bhavcopy"
    assert payload["session_mode"] == "End-Of-Day"
    assert payload["auth_status"]["authorized"] is True
    assert payload["signal_snapshot"]["scores"][0]["setup_name"] == "cpr_oi_confluence"
    assert payload["prior_session"]["tc"] >= payload["prior_session"]["bc"]
    assert {"technical_score", "oi_score", "mwpl_score"}.issubset(payload["model_predictions"])
    assert {"timestamp", "developing_poc", "vah", "val"}.issubset(payload["history"].columns)
