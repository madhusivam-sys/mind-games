from __future__ import annotations

import httpx
import pytest

from dashboard import api_client
from dashboard.api_client import DashboardApiError, fetch_json


def test_fetch_json_wraps_connection_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    monkeypatch.setattr(api_client, "_client", lambda base_url: httpx.Client(base_url=base_url, transport=httpx.MockTransport(handler)))

    with pytest.raises(DashboardApiError, match="currently unavailable"):
        fetch_json("http://127.0.0.1:8000", "/health")


def test_fetch_json_wraps_invalid_response(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text="not-json", request=request))
    monkeypatch.setattr(api_client, "_client", lambda base_url: httpx.Client(base_url=base_url, transport=transport))

    with pytest.raises(DashboardApiError, match="unreadable response"):
        fetch_json("http://127.0.0.1:8000", "/health")
