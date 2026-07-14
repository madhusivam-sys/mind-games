from __future__ import annotations

from datetime import date, datetime, timedelta
from io import BytesIO
from zipfile import ZipFile
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from services.cpr_scanner import BhavcopyError, ScanConfig, download_bhavcopy_history, load_bhavcopy_files, normalise_bhavcopy, scan_latest, telegram_report
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
        }
    )

    result = normalise_bhavcopy(raw)

    assert len(result) == 1
    assert result.iloc[0]["close"] == 805.0
    assert result.iloc[0]["instrument"] == "FUTSTK"
    assert result.iloc[0]["asset_type"] == "F&O Stock Future"


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
