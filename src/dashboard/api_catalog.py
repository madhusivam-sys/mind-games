from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


HttpMethod = Literal["GET", "POST"]


@dataclass(frozen=True, slots=True)
class EndpointSpec:
    """Declarative metadata for one REST endpoint exposed in the API console."""

    name: str
    method: HttpMethod
    path: str
    group: str
    description: str
    default_params: dict[str, Any] = field(default_factory=dict)
    default_json: dict[str, Any] | None = None


def endpoint_catalog() -> list[EndpointSpec]:
    """Return the API endpoints that the lightweight dashboard console can exercise."""

    return [
        EndpointSpec("Health", "GET", "/health", "System", "Backend liveness check."),
        EndpointSpec("Upload CSV Snapshot", "POST", "/upload", "CSV Analysis", "Load sample or configured CSV data.", default_json={"symbol": "NIFTY_FUT"}),
        EndpointSpec("Latest Snapshot", "POST", "/snapshot", "CSV Analysis", "Return the latest engineered feature row.", default_json={"symbol": "NIFTY_FUT"}),
        EndpointSpec("Current Signals", "POST", "/signals", "CSV Analysis", "Return rule-based setup scores for CSV-backed analysis.", default_json={"symbol": "NIFTY_FUT"}),
        EndpointSpec("Current Alerts", "POST", "/alerts", "CSV Analysis", "Return alert payloads for CSV-backed analysis.", default_json={"symbol": "NIFTY_FUT"}),
        EndpointSpec("Prior Session Summary", "POST", "/prior-session-summary", "CSV Analysis", "Return prior POC, value area, Camarilla, and pivot context.", default_json={"symbol": "NIFTY_FUT"}),
        EndpointSpec("Model Predictions", "POST", "/model-predictions", "CSV Analysis", "Run available baseline model predictions.", default_json={"symbol": "NIFTY_FUT"}),
        EndpointSpec("Market Auth Status", "GET", "/market/auth-status", "Live Market Data", "Check live REST data authorization.", default_params={"symbol": "NIFTY-I"}),
        EndpointSpec("Analysis Context", "GET", "/analysis/context", "Live Market Data", "Full backend-owned context payload used by the dashboard.", default_params={"symbol": "NIFTY-I", "interval": "1min", "limit": 240}),
        EndpointSpec("Market Latest", "GET", "/market/latest", "Live Market Data", "Latest bar for a symbol.", default_params={"symbol": "NIFTY-I"}),
        EndpointSpec("Market History", "GET", "/market/history", "Live Market Data", "Historical bars for a symbol and interval.", default_params={"symbol": "NIFTY-I", "interval": "1min", "limit": 200}),
        EndpointSpec("Market Ticks", "GET", "/market/ticks", "Live Market Data", "Tick or interval tick history.", default_params={"symbol": "NIFTY-I", "interval": "tick", "limit": 200}),
        EndpointSpec("LTP Bulk", "GET", "/market/ltp-bulk", "Live Market Data", "Bulk last traded prices.", default_params={"symbols": "NIFTY-I,BANKNIFTY-I"}),
        EndpointSpec("Index Components", "GET", "/market/index-components", "Live Market Data", "Index constituent lookup.", default_params={"indexName": "NIFTY 50"}),
        EndpointSpec("Option Chain", "GET", "/market/option-chain", "Live Market Data", "Option chain snapshot for symbol and expiry.", default_params={"symbol": "NIFTY", "expiry": "250327"}),
        EndpointSpec("Top Gainers", "GET", "/market/top-gainers", "Live Market Data", "Top gaining instruments for a segment.", default_params={"segment": "NSEEQ", "topn": 50}),
        EndpointSpec("Top Losers", "GET", "/market/top-losers", "Live Market Data", "Top losing instruments for a segment.", default_params={"segment": "NSEEQ", "topn": 50}),
        EndpointSpec("Signals Latest", "GET", "/signals/latest", "Signals", "Latest live/historical setup scores.", default_params={"symbol": "NIFTY-I", "interval": "1min", "limit": 200}),
        EndpointSpec("Live Start", "POST", "/live/start", "Live Runtime", "Start live backfill/runtime analysis.", default_params={"symbols": "NIFTY-I,BANKNIFTY-I"}),
        EndpointSpec("Live Stop", "POST", "/live/stop", "Live Runtime", "Stop live runtime analysis."),
        EndpointSpec("Live Status", "GET", "/live/status", "Live Runtime", "Inspect live runtime state."),
        EndpointSpec("Live Signals Latest", "GET", "/live/signals/latest", "Live Runtime", "Latest live runtime signal bundle."),
        EndpointSpec("Live Snapshot", "GET", "/live/snapshot", "Live Runtime", "Latest live runtime data snapshot.", default_params={"include_open_bar": True}),
    ]


def grouped_endpoints() -> dict[str, list[EndpointSpec]]:
    """Group endpoint specs for compact UI rendering and future navigation changes."""

    grouped: dict[str, list[EndpointSpec]] = {}
    for endpoint in endpoint_catalog():
        grouped.setdefault(endpoint.group, []).append(endpoint)
    return grouped
