from __future__ import annotations

from dashboard.bootstrap import ensure_src_on_path

ensure_src_on_path()

import pandas as pd
import streamlit as st

from dashboard.api_client import DashboardApiError
from dashboard.components.cards import bullet_card, narrative_card, score_card, stat_card
from dashboard.components.charts import price_chart, score_distribution
from dashboard.components.tables import data_table
from dashboard.data import dashboard_sidebar, load_dashboard_context
from dashboard.theme import apply_theme, hero

ACTIONABLE_ORDER = {"buy": 5, "sell": 5, "alert": 4, "warning": 3, "watch": 2, "high": 2, "medium": 1, "low": 0, "neutral": 0}


def _best_score(scores: list[dict[str, object]]) -> dict[str, object] | None:
    if not scores:
        return None
    return sorted(scores, key=lambda score: (ACTIONABLE_ORDER.get(str(score.get("label", "neutral")), 0), float(score.get("score", 0))), reverse=True)[0]


apply_theme()
base_url, query, prefer_live = dashboard_sidebar()
hero("Intraday command center", "Read the confirmed market thesis, live triggers, invalidation and watch conditions without losing the chart context.", eyebrow="LIVE DECISION DESK", badges=["5-minute confirmation", "1-minute watch", "Risk levels", "Live context"])

try:
    context = load_dashboard_context(base_url, query, prefer_live)
except DashboardApiError as exc:
    st.error(str(exc))
    st.stop()

active_payload = context.live_signals or context.signal_snapshot
confirmed_scores = active_payload.get("scores", context.signal_snapshot.get("scores", []))
watch_scores = active_payload.get("watch_scores_1m", context.signal_snapshot.get("watch_scores_1m", []))
latest_bar = active_payload.get("latest_bar", context.signal_snapshot["latest_bar"])
brief = context.briefing
primary = brief.get("primary_setup") or _best_score(confirmed_scores)
watch = brief.get("watch_setup") or _best_score(watch_scores)

status_row = st.columns(4)
with status_row[0]:
    stat_card("Market State", str(brief.get("market_state", "Unknown")), str(brief.get("bias", "neutral")))
with status_row[1]:
    stat_card("Data Source", context.data_source, context.session_mode)
with status_row[2]:
    stat_card("As Of", context.as_of_timestamp.replace("T", " "), query.symbol)
with status_row[3]:
    stat_card("Auth", "ok" if context.auth_status.get("authorized") else "blocked", str(context.auth_status.get("detail", "")))

brief_row = st.columns([1.25, 1, 1])
with brief_row[0]:
    if primary is not None:
        score_card(str(primary["setup_name"]).replace("_", " ").title(), str(primary["score"]), str(primary["label"]), tone=str(primary["label"]))
        st.write(str(brief.get("summary", primary.get("summary", ""))))
    else:
        narrative_card("Primary Setup", "No clear confirmed setup yet.")
with brief_row[1]:
    narrative_card("Trigger", str(brief.get("trigger", "No trigger available.")))
    narrative_card("Invalidation", str(brief.get("invalidation", primary.get("invalidation", "Wait for stronger structure.")) if primary else "Wait for stronger structure."))
with brief_row[2]:
    bullet_card("Targets", list(brief.get("targets", [])))
    level_items = [f"{key.upper()} {value:.2f}" for key, value in dict(brief.get("key_levels", {})).items()]
    bullet_card("Key Levels", level_items)

split = st.columns([1.5, 1])
with split[0]:
    price_chart(context.history.tail(90), title=f"{query.symbol} Price, VWAP, and Value")
with split[1]:
    if watch is not None:
        narrative_card("1-Minute Watch", str(watch.get("summary", "")))
    else:
        narrative_card("1-Minute Watch", "No watch setup currently deserves attention.")
    bullet_card("Structure Notes", list(brief.get("structure_notes", [])))

charts = st.columns(2)
with charts[0]:
    score_distribution(confirmed_scores, "5-Minute Confirmed Scores")
with charts[1]:
    score_distribution(watch_scores, "1-Minute Watch Scores")

st.subheader("Setup ranking")
action_frame = pd.DataFrame(confirmed_scores)
if action_frame.empty:
    st.info("No confirmed scores available.")
else:
    data_table(action_frame.sort_values(by=["score"], ascending=False), ["setup_name", "score", "label", "summary", "invalidation"], height=260)

st.subheader("Market alerts")
alert_frame = pd.DataFrame(active_payload.get("alerts", context.signal_snapshot.get("alerts", [])))
if alert_frame.empty:
    st.info("No alerts in the latest snapshot.")
else:
    data_table(alert_frame, ["timestamp", "symbol", "category", "message"], height=220)
