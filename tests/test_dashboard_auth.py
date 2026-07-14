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
    assert "height: 172px" in theme
    assert not (dashboard / "pages" / "6_API_Console.py").exists()


def test_dashboard_password_gate_blocks_and_unlocks(monkeypatch) -> None:
    monkeypatch.setenv("DASHBOARD_PASSWORD", "unit-test-secret")
    get_settings.cache_clear()
    page = Path(__file__).resolve().parents[1] / "src" / "dashboard" / "pages" / "7_CPR_Scanner.py"
    try:
        app = AppTest.from_file(str(page), default_timeout=30).run()
        assert [field.label for field in app.text_input] == ["Dashboard Password"]

        app.text_input[0].set_value("wrong")
        app.button[0].click()
        app.run()
        assert any("Incorrect password" in error.value for error in app.error)

        app.text_input[0].set_value("unit-test-secret")
        app.button[0].click()
        app.run()
        assert any(tab.label == "Official NSE Data" for tab in app.tabs)
    finally:
        get_settings.cache_clear()


def test_production_dashboard_fails_closed_without_password(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("DASHBOARD_PASSWORD", raising=False)
    get_settings.cache_clear()
    page = Path(__file__).resolve().parents[1] / "src" / "dashboard" / "pages" / "7_CPR_Scanner.py"
    try:
        app = AppTest.from_file(str(page), default_timeout=30).run()
        assert any("DASHBOARD_PASSWORD must be configured" in error.value for error in app.error)
        assert not app.tabs
    finally:
        get_settings.cache_clear()
