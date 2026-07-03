from __future__ import annotations

import httpx
import pandas as pd
import pytest

from integrations.market_data_client import MarketDataClientError, TrueDataMarketDataClient


@pytest.fixture()
def sample_csv() -> str:
    return """timestamp,open,high,low,close,volume,bid_volume,ask_volume
2026-03-18 09:15:00,22450,22460,22440,22455,1200,590,610
2026-03-18 09:16:00,22455,22470,22450,22468,1400,680,720
"""


def test_truedata_market_data_client_normalizes_csv(sample_csv: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/getlastnbars"
        assert request.headers["Authorization"] == "Bearer secret"
        return httpx.Response(200, text=sample_csv)

    client = TrueDataMarketDataClient(
        base_url="https://history.truedata.in",
        bearer_token="secret",
        http_client=httpx.Client(transport=httpx.MockTransport(handler), timeout=1.0),
        timeout_seconds=1.0,
    )

    payload = client.fetch_history(symbol="NIFTY-I", interval="1min", limit=2)

    assert list(payload.frame.columns[:11]) == [
        "timestamp",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "delta",
        "cvd",
        "bid_volume",
        "ask_volume",
    ]
    assert payload.frame["symbol"].iloc[-1] == "NIFTY-I"
    assert "session_date" in payload.frame.columns
    assert "bar_index" in payload.frame.columns
    assert pd.api.types.is_datetime64_any_dtype(payload.frame["timestamp"])


def test_truedata_market_data_client_retries_timeout_then_succeeds(sample_csv: str) -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(200, text=sample_csv)

    client = TrueDataMarketDataClient(
        base_url="https://history.truedata.in",
        bearer_token="secret",
        http_client=httpx.Client(transport=httpx.MockTransport(handler), timeout=1.0),
        max_retries=1,
        timeout_seconds=1.0,
    )

    payload = client.fetch_latest(symbol="BANKNIFTY-I")

    assert attempts["count"] == 2
    assert payload.frame.iloc[-1]["symbol"] == "BANKNIFTY-I"


def test_truedata_market_data_client_raises_clear_error_when_unconfigured() -> None:
    client = TrueDataMarketDataClient(
        base_url="https://history.truedata.in",
        bearer_token="configured",
        http_client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=""))),
    )
    client.bearer_token = None

    with pytest.raises(MarketDataClientError, match="TRUEDATA_BEARER_TOKEN is not configured"):
        client.fetch_latest(symbol="NIFTY-I")


def test_truedata_market_data_client_ltp_bulk_uses_expected_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/getLTPBulk"
        assert request.url.params["symbols"] == "NIFTY-I,BANKNIFTY-I"
        return httpx.Response(200, text="symbol,ltp\nNIFTY-I,25000\nBANKNIFTY-I,51000\n")

    client = TrueDataMarketDataClient(
        base_url="https://history.truedata.in",
        bearer_token="secret",
        http_client=httpx.Client(transport=httpx.MockTransport(handler), timeout=1.0),
    )

    payload = client.fetch_ltp_bulk(symbols=["NIFTY-I", "BANKNIFTY-I"])

    assert payload.frame["symbol"].tolist() == ["NIFTY-I", "BANKNIFTY-I"]



def test_truedata_market_data_client_option_chain_uses_expected_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/getSymbolOptionChain"
        assert request.url.params["symbol"] == "NIFTY"
        assert request.url.params["expiry"] == "250327"
        return httpx.Response(200, text="symbol,expiry,strike,option_type,ltp\nNIFTY,250327,25000,CE,125.5\n")

    client = TrueDataMarketDataClient(
        base_url="https://history.truedata.in",
        bearer_token="secret",
        http_client=httpx.Client(transport=httpx.MockTransport(handler), timeout=1.0),
    )

    payload = client.fetch_option_chain(symbol="NIFTY", expiry="250327")

    assert payload.frame.iloc[0]["option_type"] == "CE"
