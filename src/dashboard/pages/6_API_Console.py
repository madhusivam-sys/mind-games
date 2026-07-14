from __future__ import annotations

from dashboard.bootstrap import ensure_src_on_path

ensure_src_on_path()

import json
from typing import Any

import pandas as pd
import streamlit as st

from dashboard.api_catalog import EndpointSpec, grouped_endpoints
from dashboard.api_client import DashboardApiError, fetch_json
from dashboard.components.tables import data_table
from dashboard.data import default_base_url
from dashboard.theme import apply_theme, hero


def _parse_json_object(raw: str, label: str) -> dict[str, Any]:
    """Parse a user-editable JSON object from the endpoint console."""

    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        raise DashboardApiError(f"{label} must be valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise DashboardApiError(f"{label} must be a JSON object.")
    return payload


def _response_preview(payload: dict[str, Any] | list[Any]) -> None:
    """Render JSON and a table preview for REST responses."""

    st.json(payload, expanded=False)
    records = payload if isinstance(payload, list) else payload.get("data") if isinstance(payload.get("data"), list) else None
    if records:
        data_table(pd.DataFrame(records).head(100), height=260)


def _endpoint_panel(base_url: str, endpoint: EndpointSpec) -> None:
    """Render a compact callable panel for one endpoint."""

    with st.expander(f"{endpoint.method} {endpoint.path} - {endpoint.name}", expanded=False):
        st.caption(endpoint.description)
        cols = st.columns([1, 1])
        with cols[0]:
            params_raw = st.text_area(
                "Query Params",
                value=json.dumps(endpoint.default_params, indent=2),
                key=f"{endpoint.path}:{endpoint.name}:params",
                height=120,
            )
        with cols[1]:
            body_raw = st.text_area(
                "JSON Body",
                value=json.dumps(endpoint.default_json or {}, indent=2),
                key=f"{endpoint.path}:{endpoint.name}:body",
                height=120,
                disabled=endpoint.method == "GET",
            )
        if st.button("Send", key=f"{endpoint.path}:{endpoint.name}:send"):
            try:
                params = _parse_json_object(params_raw, "Query Params")
                body = None if endpoint.method == "GET" else _parse_json_object(body_raw, "JSON Body")
                payload = fetch_json(base_url, endpoint.path, params=params, method=endpoint.method, json_body=body)
            except DashboardApiError as exc:
                st.error(str(exc))
            else:
                _response_preview(payload)


apply_theme()
st.sidebar.markdown("### API connection")
base_url = st.sidebar.text_input("API Base URL", value=default_base_url(), key="api_console_base_url")
hero("REST API console", "Inspect and call the platform's data services from one controlled diagnostics workspace.", eyebrow="DEVELOPER TOOLS", badges=["Endpoint catalog", "Diagnostics", "JSON explorer"])

for group, endpoints in grouped_endpoints().items():
    st.subheader(group)
    for endpoint in endpoints:
        _endpoint_panel(base_url, endpoint)
