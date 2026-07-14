from __future__ import annotations

from dashboard.api_catalog import endpoint_catalog, grouped_endpoints
from api.main import app


def test_api_console_catalog_paths_exist_in_openapi() -> None:
    openapi_paths = set(app.openapi()["paths"])
    missing = [endpoint.path for endpoint in endpoint_catalog() if endpoint.path not in openapi_paths]
    assert missing == []


def test_api_console_catalog_has_unique_name_and_path_pairs() -> None:
    identifiers = [(endpoint.method, endpoint.path, endpoint.name) for endpoint in endpoint_catalog()]
    assert len(identifiers) == len(set(identifiers))


def test_grouped_endpoints_preserve_catalog_count() -> None:
    grouped_count = sum(len(endpoints) for endpoints in grouped_endpoints().values())
    assert grouped_count == len(endpoint_catalog())
