from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from utils.config import get_settings


def test_dashboard_password_gate_blocks_and_unlocks(monkeypatch) -> None:
    monkeypatch.setenv("DASHBOARD_PASSWORD", "unit-test-secret")
    get_settings.cache_clear()
    page = Path(__file__).resolve().parents[1] / "src" / "dashboard" / "pages" / "7_CPR_Scanner.py"
    try:
        app = AppTest.from_file(str(page), default_timeout=30).run()
        assert [field.label for field in app.text_input] == ["Dashboard password"]

        app.text_input[0].set_value("wrong")
        app.button[0].click()
        app.run()
        assert any("Incorrect password" in error.value for error in app.error)

        app.text_input[0].set_value("unit-test-secret")
        app.button[0].click()
        app.run()
        assert any(tab.label == "Download from NSE" for tab in app.tabs)
    finally:
        get_settings.cache_clear()
