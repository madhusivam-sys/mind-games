from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from utils.math_utils import clip_score


@dataclass(slots=True)
class ScoreResult:
    timestamp: pd.Timestamp
    symbol: str
    setup_name: str
    score: int
    label: str
    reasons: list[str] = field(default_factory=list)
    invalidation: str = ""
    summary: str = ""


class SetupScoreEngine:
    """Auction-market oriented scoring for intraday index futures."""

    def score_row(self, row: pd.Series) -> list[ScoreResult]:
        return [
            self._responsive_buy(row),
            self._responsive_sell(row),
            self._breakout(row),
            self._failed_breakout(row),
            self._trap(row),
            self._absorption(row),
            self._confluence(row),
        ]

    def score_frame(self, frame: pd.DataFrame) -> list[ScoreResult]:
        results: list[ScoreResult] = []
        for _, row in frame.iterrows():
            results.extend(self.score_row(row))
        return results

    @staticmethod
    def _is_near(level_distance: float, threshold: float = 10.0) -> bool:
        return abs(level_distance) <= threshold

    @staticmethod
    def _accepted_above_value(row: pd.Series) -> bool:
        return bool(row.get("acceptance_above_prior_value", 0) == 1 or row.get("close", 0.0) > row.get("vah", float("inf")))

    @staticmethod
    def _accepted_below_value(row: pd.Series) -> bool:
        return bool(row.get("acceptance_below_prior_value", 0) == 1 or row.get("close", 0.0) < row.get("val", float("-inf")))

    @staticmethod
    def _summary(setup_name: str, label: str, reasons: list[str]) -> str:
        pretty_name = setup_name.replace("_", " ")
        if reasons:
            return f"{pretty_name.title()} is {label} because {reasons[0].rstrip('.')}."
        return f"{pretty_name.title()} is {label} with limited confirming evidence."

    def _responsive_buy(self, row: pd.Series) -> ScoreResult:
        score = 0.0
        reasons: list[str] = []

        if self._is_near(row.get("distance_to_val", 999.0), 12.0):
            score += 22
            reasons.append("Price is testing the lower value edge.")
        if row.get("close", 0.0) > row.get("val", float("inf")) and row.get("low", 0.0) <= row.get("val", float("-inf")):
            score += 16
            reasons.append("Value rejection suggests responsive buyers at VAL.")
        if row.get("vwap_reclaim", 0) == 1:
            score += 16
            reasons.append("VWAP reclaim supports return toward fair value.")
        if row.get("poc_migration", 0.0) > 0:
            score += 12
            reasons.append("Developing POC is migrating higher.")
        if row.get("price_delta_divergence", 0) == 1 and row.get("delta", 0.0) < 0:
            score += 14
            reasons.append("Negative delta is not producing downside continuation.")
        if row.get("price_cvd_divergence", 0) == 1 and row.get("cvd_slope", 0.0) < 0:
            score += 10
            reasons.append("CVD divergence suggests weak downside acceptance.")
        if row.get("absorption_proxy", 0) == 1:
            score += 12
            reasons.append("Absorption is active at lower prices.")
        if self._is_near(row.get("distance_to_l3", 999.0), 10.0) or self._is_near(row.get("distance_to_l4", 999.0), 10.0):
            score += 14
            reasons.append("Camarilla support is aligned with the auction response.")

        label = "buy" if score >= 72 else "watch" if score >= 48 else "neutral"
        return ScoreResult(row["timestamp"], row["symbol"], "responsive_buy", clip_score(score), label, reasons, "Invalidate on acceptance below VAL/session low or failure back under VWAP.", self._summary("responsive_buy", label, reasons))

    def _responsive_sell(self, row: pd.Series) -> ScoreResult:
        score = 0.0
        reasons: list[str] = []

        if self._is_near(row.get("distance_to_vah", 999.0), 12.0):
            score += 22
            reasons.append("Price is testing the upper value edge.")
        if row.get("close", 0.0) < row.get("vah", float("-inf")) and row.get("high", 0.0) >= row.get("vah", float("inf")):
            score += 16
            reasons.append("Value rejection suggests responsive sellers at VAH.")
        if row.get("distance_to_vwap", 0.0) > 0 and row.get("close", 0.0) < row.get("open", 0.0):
            score += 12
            reasons.append("Price is rotating back from above VWAP.")
        if row.get("poc_migration", 0.0) < 0:
            score += 12
            reasons.append("Developing POC is migrating lower.")
        if row.get("price_delta_divergence", 0) == 1 and row.get("delta", 0.0) > 0:
            score += 14
            reasons.append("Positive delta is not producing upside continuation.")
        if row.get("price_cvd_divergence", 0) == 1 and row.get("cvd_slope", 0.0) > 0:
            score += 10
            reasons.append("CVD divergence suggests weak upside acceptance.")
        if row.get("absorption_proxy", 0) == 1:
            score += 12
            reasons.append("Absorption is active at higher prices.")
        if self._is_near(row.get("distance_to_h3", 999.0), 10.0) or self._is_near(row.get("distance_to_h4", 999.0), 10.0):
            score += 14
            reasons.append("Camarilla resistance is aligned with the auction response.")

        label = "sell" if score >= 72 else "watch" if score >= 48 else "neutral"
        return ScoreResult(row["timestamp"], row["symbol"], "responsive_sell", clip_score(score), label, reasons, "Invalidate on acceptance above VAH/session high or clean reclaim over VWAP.", self._summary("responsive_sell", label, reasons))

    def _breakout(self, row: pd.Series) -> ScoreResult:
        score = 0.0
        reasons: list[str] = []

        if self._accepted_above_value(row):
            score += 22
            reasons.append("Price is accepting above value.")
        if row.get("breakout_through_lvn", 0) == 1:
            score += 14
            reasons.append("The move is breaking through a low-volume pocket.")
        if row.get("poc_migration", 0.0) > 0:
            score += 16
            reasons.append("Developing POC is shifting upward with the move.")
        if row.get("vwap_slope", 0.0) > 0 and row.get("close", 0.0) > row.get("vwap", 0.0):
            score += 14
            reasons.append("VWAP slope and location support higher acceptance.")
        if row.get("cvd_slope", 0.0) > 0:
            score += 10
            reasons.append("CVD slope is confirming initiative buying.")
        if row.get("price_cvd_divergence", 0) == 0 and row.get("price_delta_divergence", 0) == 0:
            score += 10
            reasons.append("Price is not diverging from delta/CVD.")
        if self._is_near(row.get("distance_to_h4", 999.0), 12.0) or row.get("close", 0.0) > row.get("h4", float("inf")):
            score += 14
            reasons.append("Camarilla H4 participation adds breakout confluence.")

        label = "buy" if score >= 74 else "watch" if score >= 50 else "neutral"
        return ScoreResult(row["timestamp"], row["symbol"], "breakout_continuation", clip_score(score), label, reasons, "Invalidate on failure back into value, flat POC migration, or bearish divergence.", self._summary("breakout_continuation", label, reasons))

    def _failed_breakout(self, row: pd.Series) -> ScoreResult:
        score = 0.0
        reasons: list[str] = []

        if row.get("breakout_through_lvn", 0) == 1 and row.get("price_cvd_divergence", 0) == 1:
            score += 26
            reasons.append("Breakout is not being confirmed by CVD.")
        if row.get("breakout_through_lvn", 0) == 1 and row.get("price_delta_divergence", 0) == 1:
            score += 18
            reasons.append("Delta is diverging from the breakout attempt.")
        if row.get("rejection_from_hvn", 0) == 1:
            score += 18
            reasons.append("Auction is rejecting at a high-volume node.")
        if row.get("poc_migration", 0.0) <= 0:
            score += 14
            reasons.append("POC is not migrating with the attempted upside auction.")
        if row.get("close", 0.0) < row.get("vwap", 0.0):
            score += 10
            reasons.append("Loss of VWAP suggests failed acceptance.")
        if row.get("absorption_proxy", 0) == 1:
            score += 10
            reasons.append("Absorption warns of initiative failure.")

        label = "alert" if score >= 60 else "neutral"
        return ScoreResult(row["timestamp"], row["symbol"], "failed_breakout", clip_score(score), label, reasons, "Invalidate if value is reclaimed with rising POC and confirming CVD.", self._summary("failed_breakout", label, reasons))

    def _trap(self, row: pd.Series) -> ScoreResult:
        score = 0.0
        reasons: list[str] = []

        if row.get("trapped_buyer_proxy", 0) == 1:
            score += 22
            reasons.append("Buyer trap proxy is active.")
        if row.get("trapped_seller_proxy", 0) == 1:
            score += 22
            reasons.append("Seller trap proxy is active.")
        if row.get("price_delta_divergence", 0) == 1:
            score += 18
            reasons.append("Price and delta are diverging.")
        if row.get("price_cvd_divergence", 0) == 1:
            score += 18
            reasons.append("Price and CVD are diverging.")
        if row.get("breakout_through_lvn", 0) == 1 and row.get("poc_migration", 0.0) == 0:
            score += 10
            reasons.append("Breakout lacks POC migration support.")
        if row.get("close", 0.0) < row.get("vwap", float("inf")) < row.get("high", float("-inf")):
            score += 10
            reasons.append("VWAP reclaim failed after extension.")

        label = "alert" if score >= 60 else "neutral"
        return ScoreResult(row["timestamp"], row["symbol"], "trap_detection", clip_score(score), label, reasons, "Invalidate when delta/CVD realign and the market finds acceptance beyond the trap area.", self._summary("trap_detection", label, reasons))

    def _absorption(self, row: pd.Series) -> ScoreResult:
        score = 0.0
        reasons: list[str] = []

        if row.get("absorption_proxy", 0) == 1:
            score += 40
            reasons.append("Absorption proxy is active.")
        if row.get("imbalance_cluster_count", 0) >= 2:
            score += 16
            reasons.append("Stacked imbalances suggest one-sided initiative flow meeting resistance.")
        if row.get("price_delta_divergence", 0) == 1:
            score += 12
            reasons.append("Delta is not confirming the move.")
        if row.get("price_cvd_divergence", 0) == 1:
            score += 12
            reasons.append("CVD is not confirming the move.")
        if self._is_near(row.get("distance_to_poc", 999.0), 8.0):
            score += 10
            reasons.append("Absorption is happening near the current fair-value pivot.")

        label = "warning" if score >= 60 else "neutral"
        return ScoreResult(row["timestamp"], row["symbol"], "absorption_warning", clip_score(score), label, reasons, "Invalidate once aggressive flow resolves through the area with confirming POC migration.", self._summary("absorption_warning", label, reasons))

    def _confluence(self, row: pd.Series) -> ScoreResult:
        score = 0.0
        reasons: list[str] = []

        for condition, text, weight in [
            (self._is_near(row.get("distance_to_poc", 999.0), 8.0), "Current price is anchored near developing POC.", 16),
            (self._is_near(row.get("distance_to_vwap", 999.0), 8.0), "VWAP is overlapping current auction price.", 14),
            (self._is_near(row.get("distance_to_h3", 999.0), 8.0) or self._is_near(row.get("distance_to_l3", 999.0), 8.0), "Camarilla level overlaps the current auction zone.", 16),
            (self._is_near(row.get("distance_to_pivot", 999.0), 8.0), "CPR pivot is in play.", 12),
            (row.get("poc_migration", 0.0) != 0, "POC is actively migrating.", 16),
            (row.get("vwap_reclaim", 0) == 1, "VWAP reclaim adds structural confirmation.", 12),
            (row.get("price_delta_divergence", 0) == 0 and row.get("price_cvd_divergence", 0) == 0, "Order flow is aligned with price.", 14),
        ]:
            if condition:
                score += weight
                reasons.append(text)

        label = "high" if score >= 72 else "medium" if score >= 44 else "low"
        return ScoreResult(row["timestamp"], row["symbol"], "confluence_score", clip_score(score), label, reasons, "Invalidate when value, VWAP, and order flow lose alignment.", self._summary("confluence_score", label, reasons))
