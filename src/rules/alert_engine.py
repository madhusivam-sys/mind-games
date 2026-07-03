from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class Alert:
    timestamp: pd.Timestamp
    symbol: str
    category: str
    message: str


class AlertEngine:
    def build(self, frame: pd.DataFrame) -> list[Alert]:
        alerts: list[Alert] = []
        for _, row in frame.iterrows():
            if abs(row.get("distance_to_vah", 999.0)) <= 8 and row.get("close", 0.0) < row.get("vah", 0.0): alerts.append(Alert(row["timestamp"], row["symbol"], "VAH rejection", "Price rejected near VAH."))
            if abs(row.get("distance_to_val", 999.0)) <= 8 and row.get("close", 0.0) > row.get("val", 0.0): alerts.append(Alert(row["timestamp"], row["symbol"], "VAL rejection", "Price rejected near VAL."))
            if row.get("poc_migration", 0.0) > 0: alerts.append(Alert(row["timestamp"], row["symbol"], "POC migration up", "Developing POC is shifting higher."))
            if row.get("poc_migration", 0.0) < 0: alerts.append(Alert(row["timestamp"], row["symbol"], "POC migration down", "Developing POC is shifting lower."))
            if row.get("vwap_reclaim", 0) == 1: alerts.append(Alert(row["timestamp"], row["symbol"], "VWAP reclaim", "Price reclaimed VWAP."))
            if row.get("absorption_proxy", 0) == 1: alerts.append(Alert(row["timestamp"], row["symbol"], "Absorption", "Absorption proxy is active."))
            if row.get("trapped_buyer_proxy", 0) == 1 or row.get("trapped_seller_proxy", 0) == 1: alerts.append(Alert(row["timestamp"], row["symbol"], "Trap detected", "Trap proxy triggered."))
            if row.get("breakout_through_lvn", 0) == 1 and row.get("aggression_score", 0.0) >= 60: alerts.append(Alert(row["timestamp"], row["symbol"], "High confluence breakout", "LVN breakout with strong aggression."))
            if row.get("failed_breakout_score", 0.0) >= 60: alerts.append(Alert(row["timestamp"], row["symbol"], "Failed auction", "Failed breakout conditions are active."))
        return alerts
