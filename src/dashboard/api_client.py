from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import streamlit as st


class DashboardApiError(RuntimeError):
    """Raised when the dashboard cannot retrieve data from the API."""


@dataclass(slots=True)
class DashboardQuery:
    symbol: str
    interval: str = "1min"
    limit: int = 200


def _client(base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url.rstrip("/"), timeout=15.0)


def _raise_for_error(response: httpx.Response) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = response.text[:200].strip()
        raise DashboardApiError(f"API request failed with {response.status_code}: {detail}") from exc


def fetch_json(base_url: str, path: str, params: dict[str, Any] | None = None, method: str = "GET", json_body: dict[str, Any] | None = None) -> dict[str, Any] | list[Any]:
    try:
        with _client(base_url) as client:
            response = client.request(method=method, url=path, params=params, json=json_body)
    except httpx.RequestError as exc:
        raise DashboardApiError("The analysis service is currently unavailable. Check the API connection and try again.") from exc
    _raise_for_error(response)
    try:
        return response.json()
    except ValueError as exc:
        raise DashboardApiError("The analysis service returned an unreadable response. Please try again.") from exc


@st.cache_data(ttl=10, show_spinner=False)
def fetch_analysis_context(base_url: str, query: DashboardQuery) -> dict[str, Any]:
    return fetch_json(base_url, "/analysis/context", params={"symbol": query.symbol, "interval": query.interval, "limit": query.limit})


@st.cache_data(ttl=10, show_spinner=False)
def fetch_live_status(base_url: str) -> dict[str, Any]:
    return fetch_json(base_url, "/live/status")


@st.cache_data(ttl=10, show_spinner=False)
def fetch_live_signals(base_url: str) -> dict[str, Any]:
    return fetch_json(base_url, "/live/signals/latest")


@st.cache_data(ttl=30, show_spinner=False)
def fetch_health(base_url: str) -> dict[str, Any]:
    return fetch_json(base_url, "/health")


@st.cache_data(ttl=30, show_spinner=False)
def fetch_auth_status(base_url: str, symbol: str) -> dict[str, Any]:
    return fetch_json(base_url, "/market/auth-status", params={"symbol": symbol})


def clear_dashboard_cache() -> None:
    fetch_analysis_context.clear()
    fetch_live_status.clear()
    fetch_live_signals.clear()
    fetch_health.clear()
    fetch_auth_status.clear()
