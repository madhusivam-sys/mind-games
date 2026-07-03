from __future__ import annotations

import pandas as pd

from features.feature_store import load_sample_features
from rules.alert_engine import AlertEngine
from rules.setup_scores import SetupScoreEngine


def test_setup_score_engine_returns_required_setups() -> None:
    row = load_sample_features().iloc[-1]
    scores = SetupScoreEngine().score_row(row)
    assert {score.setup_name for score in scores} == {"responsive_buy", "responsive_sell", "breakout_continuation", "failed_breakout", "trap_detection", "absorption_warning", "confluence_score"}
    assert all(0 <= score.score <= 100 for score in scores)
    assert all(score.summary for score in scores)


def test_setup_scores_reward_auction_market_alignment() -> None:
    row = load_sample_features().iloc[-1].copy()
    row["acceptance_above_prior_value"] = 1
    row["poc_migration"] = 12.0
    row["vwap_reclaim"] = 1
    row["vwap_slope"] = 6.0
    row["cvd_slope"] = 10.0
    row["price_delta_divergence"] = 0
    row["price_cvd_divergence"] = 0
    row["breakout_through_lvn"] = 1
    row["distance_to_h4"] = 4.0
    row["distance_to_h3"] = 3.0
    row["distance_to_poc"] = 3.0
    row["distance_to_vwap"] = 2.0
    row["distance_to_pivot"] = 3.0
    row["close"] = max(float(row["close"]), float(row["vah"]) + 5.0, float(row["h4"]) + 2.0)
    row["vwap"] = float(row["close"]) - 4.0

    scores = {score.setup_name: score for score in SetupScoreEngine().score_row(row)}

    assert scores["breakout_continuation"].score >= 70
    assert scores["breakout_continuation"].label == "buy"
    assert scores["confluence_score"].score >= 70
    assert scores["confluence_score"].label == "high"
    assert "because" in scores["breakout_continuation"].summary


def test_alert_engine_returns_alert_objects() -> None:
    frame = load_sample_features().tail(5).copy()
    frame["failed_breakout_score"] = 75
    alerts = AlertEngine().build(frame)
    assert alerts
