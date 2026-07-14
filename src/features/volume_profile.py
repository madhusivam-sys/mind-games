from __future__ import annotations

from dataclasses import dataclass
import heapq
import math

import pandas as pd


def _developing_nodes(close: pd.Series, volume: pd.Series) -> tuple[list[float], list[float], list[str]]:
    """Calculate developing HVN/LVN and shape without rebuilding every bar prefix."""

    volume_by_price: dict[float, float] = {}
    min_heap: list[tuple[float, float]] = []
    max_heap: list[tuple[float, float]] = []
    total = 0.0
    total_squares = 0.0
    hvn: list[float] = []
    lvn: list[float] = []
    shape: list[str] = []

    for price_value, volume_value in zip(close.round(2), volume.fillna(0.0), strict=True):
        price = float(price_value)
        traded_volume = float(volume_value)
        previous = volume_by_price.get(price, 0.0)
        updated = previous + traded_volume
        volume_by_price[price] = updated
        total += traded_volume
        total_squares += updated * updated - previous * previous
        heapq.heappush(min_heap, (updated, price))
        heapq.heappush(max_heap, (-updated, -price))

        while min_heap and volume_by_price[min_heap[0][1]] != min_heap[0][0]:
            heapq.heappop(min_heap)
        while max_heap and volume_by_price[-max_heap[0][1]] != -max_heap[0][0]:
            heapq.heappop(max_heap)

        bucket_count = len(volume_by_price)
        mean = total / bucket_count
        variance = (total_squares - (total * total / bucket_count)) / (bucket_count - 1) if bucket_count > 1 else 0.0
        standard_deviation = math.sqrt(max(0.0, variance))
        lvn.append(float(min_heap[0][1]))
        hvn.append(float(-max_heap[0][1]))
        shape.append("b_shape" if standard_deviation > mean else "balanced")
    return hvn, lvn, shape


@dataclass(slots=True)
class VolumeProfileEngine:
    """Approximate high-volume and low-volume nodes using close-price aggregation."""

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        sessions: list[pd.DataFrame] = []
        for _, session in frame.groupby(["symbol", "session_date"], sort=False):
            session = session.copy()
            hvn, lvn, shape = _developing_nodes(session["close"], session["volume"])
            session["hvn"] = hvn
            session["lvn"] = lvn
            session["distance_to_hvn"] = session["close"] - session["hvn"]
            session["distance_to_lvn"] = session["close"] - session["lvn"]
            session["breakout_through_lvn"] = ((session["close"] > session["lvn"]) & (session["close"].shift(1) <= session["lvn"].shift(1))).fillna(False).astype(int)
            session["rejection_from_hvn"] = ((session["high"] >= session["hvn"]) & (session["close"] < session["hvn"])).astype(int)
            session["distribution_shape"] = shape
            sessions.append(session)
        return pd.concat(sessions, ignore_index=True)
