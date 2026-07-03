from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


ACTIONABLE_ORDER = {"buy": 5, "sell": 5, "alert": 4, "warning": 3, "watch": 2, "high": 2, "medium": 1, "low": 0, "neutral": 0}


@dataclass(slots=True)
class TradeBrief:
    market_state: str
    bias: str
    primary_setup: dict[str, Any] | None
    watch_setup: dict[str, Any] | None
    summary: str
    trigger: str
    invalidation: str
    targets: list[str]
    structure_notes: list[str]
    key_levels: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _best_score(scores: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not scores:
        return None
    return sorted(
        scores,
        key=lambda score: (
            ACTIONABLE_ORDER.get(str(score.get("label", "neutral")), 0),
            float(score.get("score", 0)),
        ),
        reverse=True,
    )[0]


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _market_state(latest_bar: dict[str, Any], confirmed_scores: list[dict[str, Any]]) -> tuple[str, str, list[str]]:
    close = _to_float(latest_bar.get("close"), 0.0)
    vwap = _to_float(latest_bar.get("vwap"), close)
    vah = _to_float(latest_bar.get("vah"), close)
    val = _to_float(latest_bar.get("val"), close)
    poc_migration = _to_float(latest_bar.get("poc_migration"), 0.0)
    notes: list[str] = []

    if close > vah and poc_migration > 0:
        notes.append("Price is holding above value and POC is migrating higher.")
        return "Initiative auction above value", "bullish", notes
    if close < val and poc_migration < 0:
        notes.append("Price is holding below value and POC is migrating lower.")
        return "Initiative auction below value", "bearish", notes
    if abs(close - vwap) <= 10:
        notes.append("Price is rotating close to VWAP, so responsive trade logic matters more than chasing.")
        return "Balanced rotation around fair value", "two-way", notes

    breakout = next((score for score in confirmed_scores if score.get("setup_name") == "breakout_continuation"), None)
    if breakout and float(breakout.get("score", 0)) >= 50:
        notes.append("Breakout logic is active, but confirmation is still moderate.")
        return "Developing continuation auction", "bullish", notes

    notes.append("Structure is mixed, so confirmation matters more than anticipation.")
    return "Transitional auction", "neutral", notes


def _targets(primary: dict[str, Any] | None, latest_bar: dict[str, Any], prior_session: dict[str, Any]) -> tuple[str, list[str]]:
    close = _to_float(latest_bar.get("close"), 0.0)
    vwap = _to_float(latest_bar.get("vwap"), close)
    poc = _to_float(latest_bar.get("developing_poc"), close)
    vah = _to_float(latest_bar.get("vah"), close)
    val = _to_float(latest_bar.get("val"), close)
    prior_poc = _to_float(prior_session.get("poc"), poc)

    if primary is None:
        return (
            "Wait for a stronger 5-minute confirmation before treating the auction as actionable.",
            [
                "No confirmed trade plan yet.",
                f"Use VWAP {vwap:.2f} and value edges {val:.2f}/{vah:.2f} as the immediate decision zone.",
            ],
        )

    name = str(primary.get("setup_name"))
    if name == "breakout_continuation":
        return (
            f"Act only if price keeps holding above value and the next 5-minute close stays beyond {max(vah, close):.2f}.",
            [f"Continuation target above {close + 25:.2f}", f"If momentum fades, reassess near VWAP {vwap:.2f}"],
        )
    if name == "responsive_buy":
        return (
            f"Responsive buy remains valid only while lower value holds and price can rotate back through VWAP {vwap:.2f}.",
            [f"First target VWAP {vwap:.2f}", f"Stretch target developing or prior POC near {max(poc, prior_poc):.2f}"],
        )
    if name == "responsive_sell":
        return (
            f"Responsive sell remains valid only while upper value keeps rejecting and price can rotate back below VWAP {vwap:.2f}.",
            [f"First target VWAP {vwap:.2f}", f"Stretch target back toward POC {poc:.2f}"],
        )
    if name == "failed_breakout":
        return (
            f"Treat the move as a failed auction only if price keeps losing acceptance and cannot reclaim {vah:.2f} / VWAP {vwap:.2f}.",
            [f"First target VWAP {vwap:.2f}", f"Then monitor lower value near {val:.2f}"],
        )
    return (
        "Use the current setup only if the next 5-minute close keeps price, value, and VWAP aligned.",
        [f"Use VWAP {vwap:.2f} as the first decision point", f"Use POC {poc:.2f} as the secondary decision point"],
    )


def build_trade_brief(signal_snapshot: dict[str, Any], prior_session: dict[str, Any]) -> TradeBrief:
    confirmed_scores = list(signal_snapshot.get("scores", []))
    watch_scores = list(signal_snapshot.get("watch_scores_1m", []))
    latest_bar = dict(signal_snapshot.get("latest_bar", {}))

    primary = _best_score(confirmed_scores)
    watch = _best_score(watch_scores)
    market_state, bias, notes = _market_state(latest_bar, confirmed_scores)
    trigger, targets = _targets(primary, latest_bar, prior_session)
    close = _to_float(latest_bar.get("close"), 0.0)

    key_levels = {
        "poc": _to_float(latest_bar.get("developing_poc"), close),
        "vah": _to_float(latest_bar.get("vah"), close),
        "val": _to_float(latest_bar.get("val"), close),
        "vwap": _to_float(latest_bar.get("vwap"), close),
        "h4": _to_float(latest_bar.get("h4"), _to_float(prior_session.get("h4"), 0.0)),
        "l4": _to_float(latest_bar.get("l4"), _to_float(prior_session.get("l4"), 0.0)),
        "pivot": _to_float(latest_bar.get("pivot"), _to_float(prior_session.get("pivot"), 0.0)),
    }

    return TradeBrief(
        market_state=market_state,
        bias=bias,
        primary_setup=primary,
        watch_setup=watch,
        summary=str(primary.get("summary", "No strong confirmed setup yet.")) if primary else "No strong confirmed setup yet.",
        trigger=trigger,
        invalidation=str(primary.get("invalidation", "Stay neutral until the auction becomes clearer.")) if primary else "Stay neutral until the auction becomes clearer.",
        targets=targets,
        structure_notes=notes,
        key_levels=key_levels,
    )
