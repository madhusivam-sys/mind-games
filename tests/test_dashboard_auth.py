from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from utils.config import get_settings


def test_brand_theme_and_logo_assets_are_present() -> None:
    dashboard = Path(__file__).resolve().parents[1] / "src" / "dashboard"
    theme = (dashboard / "theme.py").read_text(encoding="utf-8")

    assert (dashboard / "assets" / "bmg-logo.png").stat().st_size > 0
    assert "Montserrat" in theme
    assert "Lato" in theme
    assert all(color in theme for color in ["#333333", "#20959A", "#383861", "#3C7B53", "#86894B"])


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
        assert any(tab.label == "Official NSE data" for tab in app.tabs)
    finally:
        get_settings.cache_clear()
