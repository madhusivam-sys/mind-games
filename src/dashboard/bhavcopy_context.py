from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from dashboard.api_client import DashboardQuery
from services.cpr_scanner import build_scan_features


def build_bhavcopy_payload(
    history: pd.DataFrame,
    results: pd.DataFrame,
    query: DashboardQuery,
) -> dict[str, Any]:
    """Translate the official NSE FUTSTK scan into the shared dashboard contract."""

    if history.empty or results.empty:
        raise ValueError("Run the NSE F&O Bhavcopy scanner before selecting it as the analysis source.")

    ranked = results.sort_values(["eligible", "score", "liquidity_rank"], ascending=[False, False, True])
    symbol = query.symbol if query.symbol in set(ranked["symbol"].astype(str)) else str(ranked.iloc[0]["symbol"])
    scan_row = ranked[ranked["symbol"].astype(str).eq(symbol)].iloc[0]

    features = build_scan_features(history)
    selected = features[features["symbol"].astype(str).eq(symbol)].sort_values("session_date").copy()
    if selected.empty:
        raise ValueError(f"No normalized FUTSTK history is available for {symbol}.")

    selected["timestamp"] = pd.to_datetime(selected["session_date"])
    selected["developing_poc"] = selected["developing_pivot"]
    selected["vah"] = selected["tc"]
    selected["val"] = selected["bc"]
    selected["vwap"] = selected["close"]
    selected["poc_migration"] = selected["developing_pivot"] - selected["pivot"]
    latest = selected.iloc[-1]

    prior_range = _number(latest.get("prev_high")) - _number(latest.get("prev_low"))
    prior_close = _number(latest.get("prev_close"), _number(latest.get("close")))
    h4 = prior_close + (prior_range * 1.1 / 2.0)
    l4 = prior_close - (prior_range * 1.1 / 2.0)
    prior_session = {
        "symbol": symbol,
        "session_date": str(latest["session_date"]),
        "poc": _number(latest.get("pivot")),
        "vah": _number(latest.get("tc")),
        "val": _number(latest.get("bc")),
        "h3": _number(latest.get("h3")),
        "h4": h4,
        "l3": _number(latest.get("l3")),
        "l4": l4,
        "pivot": _number(latest.get("pivot")),
        "bc": _number(latest.get("bc")),
        "tc": _number(latest.get("tc")),
    }

    direction = str(scan_row.get("direction", "Neutral"))
    label = {"Bullish": "buy", "Bearish": "sell"}.get(direction, "watch")
    score = int(scan_row.get("score", 0))
    technical_score = int(scan_row.get("technical_score", 0))
    oi_score = int(scan_row.get("oi_score", 0))
    mwpl_score = int(scan_row.get("mwpl_score", 0))
    summary = str(scan_row.get("reasons", "No configured CPR condition"))
    trigger = _trigger(direction, scan_row)
    invalidation = _invalidation(direction, scan_row)
    timestamp = pd.Timestamp(latest["timestamp"]).isoformat()

    primary = {
        "timestamp": timestamp,
        "symbol": symbol,
        "setup_name": "cpr_oi_confluence",
        "score": score,
        "label": label,
        "summary": summary,
        "reasons": summary,
        "invalidation": invalidation,
    }
    participation = {
        "timestamp": timestamp,
        "symbol": symbol,
        "setup_name": "open_interest_alignment",
        "score": oi_score,
        "label": "high" if oi_score > 0 else "warning" if oi_score < 0 else "neutral",
        "summary": str(scan_row.get("oi_regime", "Indeterminate")),
        "reasons": str(scan_row.get("oi_regime", "Indeterminate")),
        "invalidation": "Reassess when price and aggregate open interest no longer confirm each other.",
    }
    scores = [primary, participation]
    signal_snapshot = {
        "scores": scores,
        "watch_scores_1m": [],
        "alerts": [],
        "latest_bar": _json_row(latest),
        "latest_confirmed_bar": _json_row(latest),
    }

    total_scale = max(1, technical_score + abs(oi_score) + abs(mwpl_score))
    breakout_evidence = min(1.0, max(0.0, technical_score / max(8.0, total_scale)))
    reversal_evidence = 1.0 if bool(latest.get("bullish_reversal", False) or latest.get("bearish_reversal", False)) else 0.0
    structure_label = _structure_label(latest)
    model_predictions = {
        "day_type_model": structure_label,
        "breakout_model": round(breakout_evidence, 3),
        "reversal_model": round(reversal_evidence, 3),
        "technical_score": technical_score,
        "oi_score": oi_score,
        "mwpl_score": mwpl_score,
    }

    developing_pivot = _number(latest.get("developing_pivot"))
    briefing = {
        "market_state": f"{direction} End-Of-Day CPR Structure",
        "bias": direction.lower(),
        "primary_setup": primary,
        "watch_setup": None,
        "summary": summary,
        "trigger": trigger,
        "invalidation": invalidation,
        "targets": [f"Developing Pivot {developing_pivot:,.2f}", f"Camarilla H3/L3 {_number(latest.get('h3')):,.2f} / {_number(latest.get('l3')):,.2f}"],
        "structure_notes": [
            f"Open Interest: {scan_row.get('oi_regime', 'Indeterminate')} ({_signed(scan_row.get('oi_change_pct'))})",
            f"MWPL Utilization: {_percentage(scan_row.get('mwpl_utilization_pct'))}",
            f"Liquidity Rank: #{int(scan_row.get('liquidity_rank', 0))} In The FUTSTK Universe",
        ],
        "key_levels": {
            "poc": developing_pivot,
            "vah": _number(latest.get("tc")),
            "val": _number(latest.get("bc")),
            "vwap": _number(latest.get("close")),
            "h4": h4,
            "l4": l4,
            "pivot": _number(latest.get("pivot")),
        },
    }

    return {
        "symbol": symbol,
        "history": selected.reset_index(drop=True),
        "features": selected.reset_index(drop=True),
        "signal_snapshot": signal_snapshot,
        "prior_session": prior_session,
        "model_predictions": model_predictions,
        "day_type_summary": [{"symbol": symbol, "structure": structure_label, "direction": direction, "evidence": summary}],
        "briefing": briefing,
        "auth_status": {
            "configured": True,
            "authorized": True,
            "detail": "Official NSE F&O Bhavcopy Loaded",
            "symbol": symbol,
            "as_of": timestamp,
        },
        "data_source": "NSE F&O Bhavcopy",
        "session_mode": "End-Of-Day",
        "as_of_timestamp": timestamp,
    }


def _number(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return default if np.isnan(result) else result


def _json_row(row: pd.Series) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in row.items():
        if pd.isna(value):
            result[key] = None
        elif hasattr(value, "isoformat"):
            result[key] = value.isoformat()
        elif isinstance(value, np.generic):
            result[key] = value.item()
        else:
            result[key] = value
    return result


def _trigger(direction: str, row: pd.Series) -> str:
    if direction == "Bullish":
        return f"Sustain Above TC {_number(row.get('tc')):,.2f}"
    if direction == "Bearish":
        return f"Sustain Below BC {_number(row.get('bc')):,.2f}"
    return f"Wait For A Break Beyond BC/TC {_number(row.get('bc')):,.2f}–{_number(row.get('tc')):,.2f}"


def _invalidation(direction: str, row: pd.Series) -> str:
    if direction == "Bullish":
        return f"Bullish Structure Weakens Below BC {_number(row.get('bc')):,.2f}."
    if direction == "Bearish":
        return f"Bearish Structure Weakens Above TC {_number(row.get('tc')):,.2f}."
    return "Stay Neutral Until Price Accepts Outside The CPR Band."


def _structure_label(row: pd.Series) -> str:
    if bool(row.get("narrow_cpr", False)):
        return "Potential Expansion"
    if bool(row.get("inside_cpr", False)):
        return "Contracting Structure"
    if bool(row.get("outside_cpr", False)):
        return "Expanding Structure"
    return "Directional Structure"


def _percentage(value: object) -> str:
    number = _number(value, float("nan"))
    return "Unavailable" if np.isnan(number) else f"{number:.1f}%"


def _signed(value: object) -> str:
    number = _number(value, float("nan"))
    return "Unavailable" if np.isnan(number) else f"{number:+.1f}%"
