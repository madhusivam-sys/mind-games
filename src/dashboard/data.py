from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

from dashboard.api_client import DashboardApiError, DashboardQuery, clear_dashboard_cache, fetch_analysis_context, fetch_auth_status, fetch_health, fetch_live_signals, fetch_live_status
from dashboard.bhavcopy_context import build_bhavcopy_payload


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
    st.sidebar.markdown("### Market Context")
    st.sidebar.caption("Configure The Active Analysis Surface.")
    bhavcopy_results = st.session_state.get("cpr_results")
    bhavcopy_ready = isinstance(bhavcopy_results, pd.DataFrame) and not bhavcopy_results.empty and isinstance(st.session_state.get("cpr_history"), pd.DataFrame)
    source_options = ["NSE F&O Bhavcopy", "Live Market API"] if bhavcopy_ready else ["Live Market API"]
    source = st.sidebar.selectbox("Analysis Source", options=source_options, key="dashboard_data_source")

    if source == "NSE F&O Bhavcopy":
        ranked = bhavcopy_results.sort_values(["eligible", "score", "liquidity_rank"], ascending=[False, False, True])
        symbols = ranked["symbol"].astype(str).tolist()
        symbol = st.sidebar.selectbox("FUTSTK Instrument", options=symbols, key="bhavcopy_symbol")
        interval = "1d"
        limit = st.sidebar.slider("History Sessions", min_value=3, max_value=40, value=min(20, max(3, int(st.session_state.get("cpr_rows", 20)))), step=1, key="bhavcopy_limit")
        auto_refresh = False
        st.sidebar.success("Official NSE F&O Bhavcopy Is Connected.")
    else:
        symbol = st.sidebar.selectbox("Instrument", options=["NIFTY-I", "BANKNIFTY-I", "NIFTY_FUT", "BANKNIFTY_FUT"], index=0, key="symbol")
        interval = st.sidebar.selectbox("Analysis Interval", options=["1min", "5min", "15min"], index=0, key="interval")
        limit = st.sidebar.slider("History Bars", min_value=60, max_value=1000, value=240, step=20, key="limit")
        auto_refresh = st.sidebar.toggle("Prefer Live Analysis", value=True, key="prefer_live")
        if not bhavcopy_ready:
            st.sidebar.info("Run The CPR Scanner Once To Connect Official NSE FUTSTK Bhavcopy Data Here.")

    if st.sidebar.button("Refresh Analysis", type="primary", width="stretch"):
        clear_dashboard_cache()
        st.session_state["dashboard_refresh_notice"] = "Analysis Refreshed"
    if notice := st.session_state.pop("dashboard_refresh_notice", None):
        st.sidebar.success(notice)
    with st.sidebar.expander("Connection Settings", expanded=False):
        base_url = st.text_input("API Address", value=default_base_url(), key="api_base_url")
    return base_url, DashboardQuery(symbol=symbol, interval=interval, limit=limit), auto_refresh


def load_dashboard_context(base_url: str, query: DashboardQuery, prefer_live: bool) -> DashboardContext:
    if st.session_state.get("dashboard_data_source") == "NSE F&O Bhavcopy":
        payload = build_bhavcopy_payload(st.session_state["cpr_history"], st.session_state["cpr_results"], query)
        return DashboardContext(
            base_url=base_url,
            query=DashboardQuery(symbol=str(payload["symbol"]), interval="1d", limit=query.limit),
            history=payload["history"].tail(query.limit),
            features=payload["features"].tail(query.limit),
            signal_snapshot=payload["signal_snapshot"],
            prior_session=payload["prior_session"],
            model_predictions=payload["model_predictions"],
            day_type_summary=payload["day_type_summary"],
            briefing=payload["briefing"],
            auth_status=payload["auth_status"],
            data_source=str(payload["data_source"]),
            session_mode=str(payload["session_mode"]),
            as_of_timestamp=str(payload["as_of_timestamp"]),
            live_status=None,
            live_signals=None,
        )

    return _load_api_dashboard_context(base_url, query, prefer_live)


@st.cache_data(ttl=10, show_spinner=False)
def _load_api_dashboard_context(base_url: str, query: DashboardQuery, prefer_live: bool) -> DashboardContext:
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
