from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

from dashboard.api_client import DashboardApiError, DashboardQuery, clear_dashboard_cache, fetch_analysis_context, fetch_auth_status, fetch_health, fetch_live_signals, fetch_live_status


@dataclass(slots=True)
class DashboardContext:
    base_url: str
    query: DashboardQuery
    history: pd.DataFrame
    features: pd.DataFrame
    signal_snapshot: dict[str, Any]
    prior_session: dict[str, Any]
    model_predictions: dict[str, Any]
    day_type_summary: list[dict[str, Any]]
    briefing: dict[str, Any]
    auth_status: dict[str, Any]
    data_source: str
    session_mode: str
    as_of_timestamp: str
    live_status: dict[str, Any] | None
    live_signals: dict[str, Any] | None


def default_base_url() -> str:
    return st.session_state.get("api_base_url", "http://127.0.0.1:8000")


def dashboard_sidebar() -> tuple[str, DashboardQuery, bool]:
    st.sidebar.markdown("### Market context")
    st.sidebar.caption("Configure the active analysis surface.")
    symbol = st.sidebar.selectbox("Instrument", options=["NIFTY-I", "BANKNIFTY-I", "NIFTY_FUT", "BANKNIFTY_FUT"], index=0, key="symbol")
    interval = st.sidebar.selectbox("Analysis interval", options=["1min", "5min", "15min"], index=0, key="interval")
    limit = st.sidebar.slider("History bars", min_value=60, max_value=1000, value=240, step=20, key="limit")
    auto_refresh = st.sidebar.toggle("Prefer live analysis", value=True, key="prefer_live")
    if st.sidebar.button("Refresh market context", type="primary", width="stretch"):
        clear_dashboard_cache()
    with st.sidebar.expander("Connection settings", expanded=False):
        base_url = st.text_input("API address", value=default_base_url(), key="api_base_url")
    return base_url, DashboardQuery(symbol=symbol, interval=interval, limit=limit), auto_refresh


@st.cache_data(ttl=10, show_spinner=False)
def load_dashboard_context(base_url: str, query: DashboardQuery, prefer_live: bool) -> DashboardContext:
    health = fetch_health(base_url)
    if health.get("status") != "ok":
        raise DashboardApiError("Backend health check did not return ok status.")

    auth_status = fetch_auth_status(base_url, query.symbol)
    try:
        payload = fetch_analysis_context(base_url, query)
    except DashboardApiError as exc:
        if not auth_status.get("authorized", False):
            raise DashboardApiError(
                "Live market data is not authorized. Review the TrueData credentials in the application environment, then refresh the market context."
            ) from exc
        raise

    live_status: dict[str, Any] | None = None
    live_signals: dict[str, Any] | None = None
    try:
        live_status = fetch_live_status(base_url)
        if prefer_live and live_status.get("running") and live_status.get("has_analysis"):
            live_signals = fetch_live_signals(base_url)
    except DashboardApiError:
        live_status = None
        live_signals = None

    return DashboardContext(
        base_url=base_url,
        query=query,
        history=pd.DataFrame(payload.get("bars", [])),
        features=pd.DataFrame(payload.get("features", [])),
        signal_snapshot=payload["signal_snapshot"],
        prior_session=payload["prior_session_summary"],
        model_predictions=payload["model_predictions"],
        day_type_summary=payload.get("day_type_summary", []),
        briefing=payload["briefing"],
        auth_status=auth_status,
        data_source=str(payload.get("data_source", "unknown")),
        session_mode=str(payload.get("session_mode", "unknown")),
        as_of_timestamp=str(payload.get("as_of_timestamp", "")),
        live_status=live_status,
        live_signals=live_signals,
    )
