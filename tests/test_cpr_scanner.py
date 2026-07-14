from __future__ import annotations

from datetime import date, datetime, timedelta
from io import BytesIO
from zipfile import ZipFile
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from services.cpr_scanner import (
    BhavcopyError,
    ScanConfig,
    attach_mwpl_snapshot,
    download_bhavcopy_history,
    load_bhavcopy_files,
    normalise_bhavcopy,
    normalise_mwpl,
    scan_latest,
    telegram_report,
)
from services.cpr_scheduler import _next_run


def _history() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    start = date(2026, 7, 1)
    values = [
        (100.0, 110.0, 90.0, 100.0),
        (101.0, 109.0, 99.0, 106.0),
        (107.0, 112.0, 104.0, 111.0),
        (112.0, 116.0, 109.0, 115.0),
        (116.0, 118.0, 113.0, 117.0),
    ]
    for offset, (opening, high, low, close) in enumerate(values):
        rows.append(
            {
                "symbol": "DEMO",
                "session_date": start + timedelta(days=offset),
                "open": opening,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1000 + offset,
                "turnover": 0.0,
                "asset_type": "F&O Stock Future",
            }
        )
    return pd.DataFrame(rows)


def test_normalise_rejects_cash_bhavcopy() -> None:
    raw = pd.DataFrame(
        {
            "TradDt": ["2026-07-10"] * 3,
            "TckrSymb": ["SBIN", "NIFTY", "ILLIQUID"],
            "SctySrs": ["EQ", "INDEX", "BE"],
            "FinInstrmTp": ["STK", "INDEX", "STK"],
            "OpnPric": [800.0, 25000.0, 10.0],
            "HghPric": [810.0, 25100.0, 11.0],
            "LwPric": [790.0, 24900.0, 9.0],
            "ClsPric": [805.0, 25050.0, 10.5],
            "TtlTradgVol": [10_000, 0, 100],
        }
    )

    with pytest.raises(BhavcopyError, match="No NSE stock-futures"):
        normalise_bhavcopy(raw)


def test_normalise_fo_selects_nearest_future_and_excludes_option() -> None:
    raw = pd.DataFrame(
        {
            "TradDt": ["2026-07-10"] * 4,
            "TckrSymb": ["SBIN", "SBIN", "SBIN", "NIFTY"],
            "FinInstrmTp": ["STF", "FUTSTK", "OPTSTK", "FUTIDX"],
            "XpryDt": ["2026-07-30", "2026-08-27", "2026-07-30", "2026-07-30"],
            "OptnTp": ["", "", "CE", ""],
            "OpnPric": [800.0, 805.0, 10.0, 25000.0],
            "HghPric": [810.0, 815.0, 12.0, 25100.0],
            "LwPric": [790.0, 795.0, 8.0, 24900.0],
            "ClsPric": [805.0, 810.0, 11.0, 25050.0],
            "TtlTradgVol": [10_000, 5_000, 100_000, 50_000],
            "TtlTrfVal": [8_000_000, 4_000_000, 1_000_000, 9_000_000],
            "OpnIntrst": [100_000, 40_000, 500_000, 200_000],
            "ChngInOpnIntrst": [5_000, -1_000, 20_000, 8_000],
        }
    )

    result = normalise_bhavcopy(raw)

    assert len(result) == 1
    assert result.iloc[0]["close"] == 805.0
    assert result.iloc[0]["instrument"] == "FUTSTK"
    assert result.iloc[0]["asset_type"] == "F&O Stock Future"
    assert result.iloc[0]["aggregate_open_interest"] == 140_000
    assert result.iloc[0]["aggregate_turnover"] == 12_000_000
    assert result.iloc[0]["reported_oi_change"] == 4_000
    assert result.iloc[0]["futures_expiries"] == 2


def test_normalise_mwpl_uses_future_equivalent_oi_and_official_gate() -> None:
    raw = pd.DataFrame(
        {
            "NSE Symbol": ["DEMO"],
            "MWPL": [1_000_000],
            "Open Interest": [1_200_000],
            "Future Equivalent Open Interest": [910_000],
            "Limit for Next Day": ["No Fresh Positions"],
        }
    )

    result = normalise_mwpl(raw).iloc[0]

    assert result["mwpl_utilization_pct"] == 91.0
    assert bool(result["mwpl_ban"])


def test_scanner_restricts_universe_to_top_50_by_rolling_turnover() -> None:
    rows: list[dict[str, object]] = []
    for symbol_number in range(55):
        for day in range(5):
            rows.append(
                {
                    "symbol": f"S{symbol_number:02d}",
                    "session_date": date(2026, 7, 1) + timedelta(days=day),
                    "open": 100.0 + day,
                    "high": 104.0 + day,
                    "low": 99.0 + day,
                    "close": 103.0 + day,
                    "volume": 1_000 + symbol_number,
                    "turnover": 1_000_000 * (symbol_number + 1),
                    "aggregate_volume": 1_000 + symbol_number,
                    "aggregate_turnover": 1_000_000 * (symbol_number + 1),
                    "aggregate_open_interest": 10_000 + (day * 500),
                    "asset_type": "F&O Stock Future",
                }
            )

    result = scan_latest(pd.DataFrame(rows), ScanConfig(minimum_history=2))

    assert len(result) == 50
    assert set(f"S{number:02d}" for number in range(5)).isdisjoint(result["symbol"])
    assert result["liquidity_rank"].min() == 1
    assert result["liquidity_rank"].max() == 50


def test_oi_confirmation_and_mwpl_penalty_are_auditable() -> None:
    history = _history()
    history["aggregate_open_interest"] = [10_000, 10_500, 11_000, 11_500, 12_500]
    history["aggregate_volume"] = history["volume"]
    history["aggregate_turnover"] = history["volume"] * history["close"]
    snapshot = normalise_mwpl(
        pd.DataFrame(
            {
                "NSE Symbol": ["DEMO"],
                "MWPL": [100_000],
                "Open Interest": [90_000],
                "Future Equivalent Open Interest": [85_000],
                "Limit for Next Day": ["15,000"],
            }
        )
    )

    result = scan_latest(attach_mwpl_snapshot(history, snapshot), ScanConfig(minimum_history=2)).iloc[0]

    assert result["oi_regime"] == "Long buildup"
    assert result["oi_score"] > 0
    assert result["mwpl_utilization_pct"] == 85.0
    assert result["mwpl_score"] == -1
    assert bool(result["eligible"])


def test_official_no_fresh_positions_gate_excludes_telegram_candidate() -> None:
    history = _history()
    history["aggregate_open_interest"] = [10_000, 10_500, 11_000, 11_500, 12_500]
    snapshot = normalise_mwpl(
        pd.DataFrame(
            {
                "NSE Symbol": ["DEMO"],
                "MWPL": [100_000],
                "Open Interest": [110_000],
                "Future Equivalent Open Interest": [92_000],
                "Limit for Next Day": ["No Fresh Positions"],
            }
        )
    )

    results = scan_latest(attach_mwpl_snapshot(history, snapshot), ScanConfig(minimum_history=2))

    assert not bool(results.iloc[0]["eligible"])
    assert "1. DEMO" not in telegram_report(results)


def test_scanner_returns_auditable_ranked_candidate() -> None:
    result = scan_latest(_history(), ScanConfig(minimum_history=2))

    assert result.iloc[0]["symbol"] == "DEMO"
    assert result.iloc[0]["score"] > 0
    assert result.iloc[0]["reasons"] != "No configured CPR condition"
    assert {"pivot", "bc", "tc", "developing_pivot"}.issubset(result.columns)


def test_telegram_report_contains_rank_and_disclaimer() -> None:
    report = telegram_report(scan_latest(_history(), ScanConfig(minimum_history=2)))

    assert "1. DEMO" in report
    assert "technical watchlist only" in report
    assert "Verify price/action" in report


def test_telegram_report_renumbers_filtered_dataframe() -> None:
    results = scan_latest(_history(), ScanConfig(minimum_history=2))
    results.index = [17]

    report = telegram_report(results)

    assert "1. DEMO" in report
    assert "18. DEMO" not in report


def test_next_run_uses_same_day_before_cutoff_and_tomorrow_after() -> None:
    timezone = ZoneInfo("Asia/Kolkata")
    before = datetime(2026, 7, 14, 20, 59, tzinfo=timezone)
    after = datetime(2026, 7, 14, 21, 1, tzinfo=timezone)

    assert _next_run(before, 21, 0) == datetime(2026, 7, 14, 21, 0, tzinfo=timezone)
    assert _next_run(after, 21, 0) == datetime(2026, 7, 15, 21, 0, tzinfo=timezone)


def test_load_bhavcopy_files_accepts_nse_zip() -> None:
    csv_payload = (
        "TradDt,TckrSymb,FinInstrmTp,XpryDt,OptnTp,OpnPric,HghPric,LwPric,ClsPric,TtlTradgVol\n"
        "2026-07-10,SBIN,STF,2026-07-30,,800,810,790,805,10000\n"
    ).encode()
    archive = BytesIO()
    with ZipFile(archive, "w") as output:
        output.writestr("BhavCopy.csv", csv_payload)

    result = load_bhavcopy_files([("BhavCopy.zip", archive.getvalue())])

    assert result[["symbol", "instrument", "asset_type"]].to_dict("records") == [
        {"symbol": "SBIN", "instrument": "FUTSTK", "asset_type": "F&O Stock Future"}
    ]


def test_download_rejects_non_fo_segments_before_network() -> None:
    with pytest.raises(BhavcopyError, match="only the NSE F&O bhavcopy"):
        download_bhavcopy_history(date(2026, 7, 10), 3, ("CM",))
