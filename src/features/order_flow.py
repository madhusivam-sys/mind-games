from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(slots=True)
class OrderFlowEngine:
    window: int = 5
    imbalance_threshold: float = 1.5

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        working = frame.copy()
        if working["delta"].isna().all():
            proxy_range = (working["high"] - working["low"]).replace(0.0, np.nan)
            working["delta"] = (((working["close"] - working["open"]) / proxy_range).fillna(0.0) * working["volume"])
        grouped = working.groupby(["symbol", "session_date"], sort=False)
        working["rolling_delta"] = grouped["delta"].rolling(self.window, min_periods=1).sum().reset_index(level=[0, 1], drop=True)
        if working["cvd"].isna().all():
            working["cvd"] = grouped["delta"].cumsum()
        working["cvd_slope"] = grouped["cvd"].diff(self.window).fillna(grouped["cvd"].diff()).fillna(0.0)
        working["delta_slope"] = grouped["delta"].diff(self.window).fillna(grouped["delta"].diff()).fillna(0.0)

        price_change = grouped["close"].diff(self.window).fillna(grouped["close"].diff()).fillna(0.0)
        working["price_delta_divergence"] = (np.sign(price_change) * np.sign(working["delta_slope"]) < 0).astype(int)
        working["price_cvd_divergence"] = (np.sign(price_change) * np.sign(working["cvd_slope"]) < 0).astype(int)

        ask = pd.to_numeric(working["ask_volume"], errors="coerce").fillna(working["volume"] * 0.5)
        bid = pd.to_numeric(working["bid_volume"], errors="coerce").fillna(working["volume"] * 0.5)
        imbalance_ratio = (ask + 1.0) / (bid + 1.0)
        imbalance = ((imbalance_ratio > self.imbalance_threshold) | (imbalance_ratio < 1 / self.imbalance_threshold)).astype(int)
        working["imbalance_cluster_count"] = imbalance.groupby([working["symbol"], working["session_date"]], sort=False).rolling(self.window, min_periods=1).sum().reset_index(level=[0, 1], drop=True)
        working["stacked_bid_imbalance"] = (imbalance_ratio < 1 / self.imbalance_threshold).astype(int)
        working["stacked_ask_imbalance"] = (imbalance_ratio > self.imbalance_threshold).astype(int)

        weak_move = ((working["close"] - working["open"]).abs() / (working["high"] - working["low"]).replace(0.0, np.nan)).fillna(0.0)
        delta_intensity = (working["delta"].abs() / working["volume"].replace(0.0, np.nan)).fillna(0.0)
        working["absorption_proxy"] = ((delta_intensity > 0.35) & (weak_move < 0.35)).astype(int)
        rel_volume = (working["volume"] / grouped["volume"].expanding().mean().reset_index(level=[0, 1], drop=True).replace(0.0, np.nan)).fillna(0.0)
        working["aggression_score"] = (delta_intensity.clip(0.0, 1.0) * 50 + rel_volume.clip(0.0, 3.0) * 10 + working["imbalance_cluster_count"].clip(0.0, self.window) * (40 / self.window)).clip(0.0, 100.0)
        working["trapped_buyer_proxy"] = ((working["price_delta_divergence"] == 1) & (working["close"] < working["open"]) & (working["delta"] > 0)).astype(int)
        working["trapped_seller_proxy"] = ((working["price_delta_divergence"] == 1) & (working["close"] > working["open"]) & (working["delta"] < 0)).astype(int)
        return working
