from __future__ import annotations

import pandas as pd

from dashboard.cpr_scanner_view import prepare_action_table


def test_action_table_builds_plain_language_watch_plans() -> None:
    results = pd.DataFrame(
        [
            {"symbol": "LT", "direction": "Bullish", "bc": 3800.0, "tc": 3810.0, "reasons": "Narrow CPR · Ascending CPR"},
            {"symbol": "SBIN", "direction": "Bearish", "bc": 810.0, "tc": 815.0, "reasons": "Descending CPR"},
            {"symbol": "TCS", "direction": "Neutral", "bc": 3200.0, "tc": 3220.0, "reasons": "Inside CPR"},
        ]
    )

    table = prepare_action_table(results)

    assert table["plan"].tolist() == ["Track strength", "Track weakness", "Wait for break"]
    assert table["conditions"].tolist() == [2, 1, 1]
    assert table.loc[0, "trigger"] == "Sustain above TC 3,810.00"
    assert table.loc[1, "trigger"] == "Sustain below BC 810.00"
    assert table.loc[2, "cpr_band"] == "3,200.00 – 3,220.00"


def test_action_table_makes_mwpl_risk_state_obvious() -> None:
    results = pd.DataFrame(
        [
            {"symbol": "SAFE", "direction": "Bullish", "bc": 100.0, "tc": 101.0, "reasons": "Narrow CPR", "mwpl_utilization_pct": 42.0, "eligible": True},
            {"symbol": "BUSY", "direction": "Neutral", "bc": 200.0, "tc": 202.0, "reasons": "Inside CPR", "mwpl_utilization_pct": 84.0, "eligible": True},
            {"symbol": "BAN", "direction": "Bearish", "bc": 300.0, "tc": 303.0, "reasons": "Descending CPR", "mwpl_utilization_pct": 96.0, "eligible": False, "mwpl_ban": True},
        ]
    )

    table = prepare_action_table(results)

    assert table["status"].tolist() == ["Track", "Crowding risk", "Avoid fresh positions"]
    assert table["mwpl_view"].tolist() == ["42.0%", "84.0%", "96.0%"]
