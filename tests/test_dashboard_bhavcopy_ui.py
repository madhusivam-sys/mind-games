from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from services.cpr_scanner import scan_latest


def _history() -> pd.DataFrame:
    start = date(2026, 7, 7)
    return pd.DataFrame(
        [
            {
                "session_date": start + timedelta(days=offset),
                "symbol": "DEMO",
                "instrument": "FUTSTK",
                "asset_type": "F&O Stock Future",
                "open": close - 1,
                "high": close + 2,
                "low": close - 2,
                "close": close,
                "volume": 100_000 + offset * 1_000,
                "aggregate_volume": 150_000 + offset * 1_000,
                "aggregate_turnover": 15_000_000 + offset * 500_000,
                "aggregate_open_interest": 200_000 + offset * 10_000,
                "mwpl_utilization_pct": 55.0,
                "mwpl_ban": False,
            }
            for offset, close in enumerate([100.0, 103.0, 106.0, 109.0, 112.0])
        ]
    )


def test_home_uses_bhavcopy_source_and_navigation_actions() -> None:
    history = _history()
    app_path = Path(__file__).resolve().parents[1] / "src" / "dashboard" / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=30)
    app.session_state["cpr_history"] = history
    app.session_state["cpr_results"] = scan_latest(history)
    app.session_state["cpr_rows"] = len(history)
    app.session_state["dashboard_data_source"] = "NSE F&O Bhavcopy"

    app.run()

    assert not app.exception
    assert any(box.label == "Analysis Source" and box.value == "NSE F&O Bhavcopy" for box in app.selectbox)
    assert any("Official NSE F&O Bhavcopy Is Connected" in success.value for success in app.success)
    labels = {button.label for button in app.get("link_button")}
    assert {"🌅 Open Pre-Market", "📊 Open Model Insights", "🎯 Open CPR Scanner"}.issubset(labels)
    destinations = {button.label: button.url for button in app.get("link_button")}
    assert destinations["🌅 Open Pre-Market"] == "/PreMarket"
    assert destinations["📊 Open Model Insights"] == "/Model_Insights"
    assert destinations["🎯 Open CPR Scanner"] == "/CPR_Scanner"


def test_refresh_analysis_control_executes() -> None:
    history = _history()
    page_path = Path(__file__).resolve().parents[1] / "src" / "dashboard" / "pages" / "1_PreMarket.py"
    app = AppTest.from_file(str(page_path), default_timeout=30)
    app.session_state["cpr_history"] = history
    app.session_state["cpr_results"] = scan_latest(history)
    app.session_state["dashboard_data_source"] = "NSE F&O Bhavcopy"
    app.run()

    refresh = next(button for button in app.button if button.label == "Refresh Analysis")
    refresh.click()
    app.run()

    assert not app.exception
    assert any("Analysis Refreshed" in success.value for success in app.success)


def test_model_insights_uses_bhavcopy_evidence_scores() -> None:
    history = _history()
    page_path = Path(__file__).resolve().parents[1] / "src" / "dashboard" / "pages" / "4_Model_Insights.py"
    app = AppTest.from_file(str(page_path), default_timeout=30)
    app.session_state["cpr_history"] = history
    app.session_state["cpr_results"] = scan_latest(history)
    app.session_state["dashboard_data_source"] = "NSE F&O Bhavcopy"
    app.run()

    assert not app.exception
    rendered = " ".join(markdown.value for markdown in app.markdown)
    assert "Bhavcopy Engine Interpretation" in rendered
    assert "CPR Score" in rendered
    assert "OI Score" in rendered


def test_cpr_reset_filters_control_executes() -> None:
    history = _history()
    page_path = Path(__file__).resolve().parents[1] / "src" / "dashboard" / "pages" / "7_CPR_Scanner.py"
    app = AppTest.from_file(str(page_path), default_timeout=30)
    app.session_state["cpr_history"] = history
    app.session_state["cpr_results"] = scan_latest(history)
    app.session_state["cpr_rows"] = len(history)
    app.session_state["cpr_symbol_filter"] = "NO-MATCH"
    app.run()

    reset = next(button for button in app.button if button.label == "Reset Filters")
    reset.click()
    app.run()

    assert not app.exception
    assert app.session_state["cpr_symbol_filter"] == ""
