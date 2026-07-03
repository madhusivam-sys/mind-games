from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from utils.config import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)

TradeCallback = Callable[[Any], None]
GreekCallback = Callable[[Any], None]
BidAskCallback = Callable[[Any], None]
BarCallback = Callable[[Any], None]
Factory = Callable[..., Any]


class LiveMarketDataClientError(RuntimeError):
    """Raised when the TrueData live client cannot be started safely."""


@dataclass(slots=True)
class LiveCallbacks:
    """User-provided live event callbacks."""

    on_trade: TradeCallback | None = None
    on_greek: GreekCallback | None = None
    on_bidask: BidAskCallback | None = None
    on_bar: BarCallback | None = None


@dataclass(slots=True)
class TrueDataLiveClient:
    """Thin wrapper around `truedata.TD_live` with env-backed config and safe shutdown."""

    username: str | None = None
    password: str | None = None
    url: str | None = None
    live_port: int | None = None
    full_feed: bool | None = None
    dry_run: bool | None = None
    log_level: int = logging.WARNING
    td_factory: Factory | None = None
    callbacks: LiveCallbacks = field(default_factory=LiveCallbacks)
    client: Any | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        settings = get_settings()
        self.username = self.username or settings.truedata_live_username
        self.password = self.password or settings.truedata_live_password
        self.url = self.url or settings.truedata_live_url
        self.live_port = self.live_port or settings.truedata_live_port
        self.full_feed = settings.truedata_live_full_feed if self.full_feed is None else self.full_feed
        self.dry_run = settings.truedata_live_dry_run if self.dry_run is None else self.dry_run

    def start(self) -> Any:
        """Instantiate the vendor client and register callbacks."""

        if self.client is not None:
            return self.client
        if not self.username or not self.password:
            raise LiveMarketDataClientError("TRUEDATA_LIVE_USERNAME and TRUEDATA_LIVE_PASSWORD must be configured.")

        factory = self.td_factory or self._import_factory()
        try:
            self.client = factory(
                self.username,
                self.password,
                url=self.url,
                live_port=self.live_port,
                log_level=self.log_level,
                full_feed=self.full_feed,
                dry_run=self.dry_run,
            )
        except Exception as exc:
            detail = "Invalid User Credentials" if "Invalid User Credentials" in str(exc) else str(exc)
            raise LiveMarketDataClientError(f"Unable to start TrueData live client: {detail}") from exc
        self._register_callbacks(self.client)
        logger.info("Started TrueData live client url=%s port=%s full_feed=%s", self.url, self.live_port, self.full_feed)
        return self.client

    def stop(self) -> None:
        """Close the vendor client if it exposes a shutdown method."""

        if self.client is None:
            return
        close_fn = getattr(self.client, "disconnect", None) or getattr(self.client, "close", None) or getattr(self.client, "stop", None)
        if callable(close_fn):
            close_fn()
        self.client = None
        logger.info("Stopped TrueData live client")

    def run_forever(self, sleep_seconds: float = 5.0) -> None:
        """Keep the process alive until interrupted, then shut down cleanly."""

        import time

        self.start()
        try:
            while True:
                time.sleep(sleep_seconds)
        except KeyboardInterrupt:
            logger.warning("Interrupted TrueData live client loop")
        finally:
            self.stop()

    def _register_callbacks(self, client: Any) -> None:
        self._decorate(client, "full_feed_trade_callback", self.callbacks.on_trade, "trade")
        self._decorate(client, "greek_callback", self.callbacks.on_greek, "greek")
        self._decorate(client, "bidask_callback", self.callbacks.on_bidask, "bidask")
        self._decorate(client, "full_feed_bar_callback", self.callbacks.on_bar, "bar")

    def _decorate(self, client: Any, decorator_name: str, callback: Callable[[Any], None] | None, label: str) -> None:
        if callback is None:
            return
        decorator = getattr(client, decorator_name, None)
        if decorator is None or not callable(decorator):
            raise LiveMarketDataClientError(f"TrueData client does not expose {decorator_name} for {label} callbacks.")
        decorator(callback)

    @staticmethod
    def _import_factory() -> Factory:
        try:
            from truedata import TD_live  # type: ignore
        except ImportError as exc:
            raise LiveMarketDataClientError("The `truedata` package is not installed. Install it before using live market data.") from exc
        return TD_live
