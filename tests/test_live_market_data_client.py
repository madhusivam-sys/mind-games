from __future__ import annotations

import pytest

from integrations.live_market_data_client import LiveCallbacks, LiveMarketDataClientError, TrueDataLiveClient


class FakeTDLive:
    def __init__(self, username: str, password: str, **kwargs: object) -> None:
        self.username = username
        self.password = password
        self.kwargs = kwargs
        self.registered: dict[str, object] = {}
        self.closed = False

    def full_feed_trade_callback(self, callback):
        self.registered["trade"] = callback
        return callback

    def greek_callback(self, callback):
        self.registered["greek"] = callback
        return callback

    def bidask_callback(self, callback):
        self.registered["bidask"] = callback
        return callback

    def full_feed_bar_callback(self, callback):
        self.registered["bar"] = callback
        return callback

    def disconnect(self) -> None:
        self.closed = True


class FailingTDLive:
    def __init__(self, username: str, password: str, **kwargs: object) -> None:
        raise ValueError("Invalid User Credentials")


def test_truedata_live_client_registers_callbacks_and_stops() -> None:
    events: list[tuple[str, object]] = []

    client = TrueDataLiveClient(
        username="user",
        password="pass",
        td_factory=FakeTDLive,
        callbacks=LiveCallbacks(
            on_trade=lambda payload: events.append(("trade", payload)),
            on_greek=lambda payload: events.append(("greek", payload)),
            on_bidask=lambda payload: events.append(("bidask", payload)),
            on_bar=lambda payload: events.append(("bar", payload)),
        ),
    )

    vendor = client.start()
    assert isinstance(vendor, FakeTDLive)
    assert set(vendor.registered) == {"trade", "greek", "bidask", "bar"}

    vendor.registered["trade"]({"ltp": 100})
    vendor.registered["bar"]({"close": 101})
    assert events == [("trade", {"ltp": 100}), ("bar", {"close": 101})]

    client.stop()
    assert vendor.closed is True
    assert client.client is None


def test_truedata_live_client_requires_credentials() -> None:
    client = TrueDataLiveClient(username="configured", password="configured", td_factory=FakeTDLive)
    client.username = None
    client.password = None

    with pytest.raises(LiveMarketDataClientError, match="TRUEDATA_LIVE_USERNAME and TRUEDATA_LIVE_PASSWORD"):
        client.start()


def test_truedata_live_client_wraps_vendor_start_errors() -> None:
    client = TrueDataLiveClient(username="user", password="pass", td_factory=FailingTDLive)

    with pytest.raises(LiveMarketDataClientError, match="Unable to start TrueData live client: Invalid User Credentials"):
        client.start()
