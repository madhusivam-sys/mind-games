from __future__ import annotations

import pandas as pd


def prepare_action_table(results: pd.DataFrame) -> pd.DataFrame:
    """Build presentation-only watch plans from ranked scanner output."""

    table = results.copy()
    table["plan"] = table["direction"].map(
        {"Bullish": "Track strength", "Bearish": "Track weakness", "Neutral": "Wait for break"}
    ).fillna("Review")
    table["bias"] = table["direction"].map(
        {"Bullish": "Bullish ↑", "Bearish": "Bearish ↓", "Neutral": "Neutral •"}
    ).fillna(table["direction"])
    table["trigger"] = table.apply(_trigger_text, axis=1)
    table["cpr_band"] = table.apply(lambda row: f"{float(row['bc']):,.2f} – {float(row['tc']):,.2f}", axis=1)
    table["conditions"] = table["reasons"].map(_condition_count)
    table["oi_view"] = table.apply(_oi_text, axis=1)
    table["mwpl_view"] = table.apply(_mwpl_text, axis=1)
    table["status"] = table.apply(_status_text, axis=1)
    return table


def _oi_text(row: pd.Series) -> str:
    change = row.get("oi_change_pct")
    if pd.isna(change):
        return "Unavailable"
    return f"{row.get('oi_regime', 'Indeterminate')} ({float(change):+.1f}%)"


def _mwpl_text(row: pd.Series) -> str:
    utilization = row.get("mwpl_utilization_pct")
    if pd.isna(utilization):
        return "Unavailable"
    return f"{float(utilization):.1f}%"


def _status_text(row: pd.Series) -> str:
    eligible = row.get("eligible")
    ban_value = row.get("mwpl_ban", False)
    banned = bool(ban_value) if pd.notna(ban_value) else False
    if (eligible is not None and not bool(eligible)) or banned:
        return "Avoid fresh positions"
    utilization = row.get("mwpl_utilization_pct")
    if pd.notna(utilization) and float(utilization) >= 80:
        return "Crowding risk"
    return "Track"


def _trigger_text(row: pd.Series) -> str:
    if row["direction"] == "Bullish":
        return f"Sustain above TC {float(row['tc']):,.2f}"
    if row["direction"] == "Bearish":
        return f"Sustain below BC {float(row['bc']):,.2f}"
    return f"Break CPR {float(row['bc']):,.2f}–{float(row['tc']):,.2f}"


def _condition_count(reasons: object) -> int:
    text = str(reasons)
    if not text or text == "No configured CPR condition":
        return 0
    return len([reason for reason in text.split(" · ") if reason])
