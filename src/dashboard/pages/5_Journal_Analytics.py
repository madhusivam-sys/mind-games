from __future__ import annotations

from dashboard.bootstrap import ensure_src_on_path

ensure_src_on_path()

import pandas as pd
import streamlit as st

from dashboard.api_client import DashboardApiError
from dashboard.components.cards import narrative_card, stat_card
from dashboard.components.tables import data_table
from dashboard.data import dashboard_sidebar, load_dashboard_context
from dashboard.theme import apply_theme, hero

apply_theme()
base_url, query, prefer_live = dashboard_sidebar()
hero("Journal analytics", "See which setup families are dominating and whether confirmation is improving decision quality.", eyebrow="PROCESS ANALYTICS", badges=["Setup mix", "Watch quality", "Behavioral review"])

try:
    context = load_dashboard_context(base_url, query, prefer_live)
except DashboardApiError as exc:
    st.error(str(exc))
    st.stop()

scores = pd.DataFrame(context.signal_snapshot["scores"])
watch = pd.DataFrame(context.signal_snapshot["watch_scores_1m"])

cols = st.columns(3)
with cols[0]:
    stat_card("Confirmed Setups", str(len(scores)), query.symbol)
with cols[1]:
    stat_card("Watch Setups", str(len(watch)), query.interval)
with cols[2]:
    top_label = scores["label"].mode().iloc[0] if not scores.empty else "none"
    stat_card("Dominant Label", str(top_label), "current snapshot")

if not scores.empty:
    summary = scores.groupby("label", dropna=False)["score"].agg(["count", "mean"]).reset_index()
    st.subheader("Confirmed setup mix")
    data_table(summary, ["label", "count", "mean"], height=220)

if not watch.empty:
    st.subheader("1-minute watch list")
    data_table(watch, ["setup_name", "score", "label", "summary"], height=260)

narrative_card("Analyst Note", "Use this page to track which setup families are dominating the current session, then journal whether the 5-minute confirmation improved trade quality versus the 1-minute watch list.")
