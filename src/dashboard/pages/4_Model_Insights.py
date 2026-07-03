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
hero("Model Insights", "Model output now shares the same backend context, source stamp, and auth state as the trading brief.")

try:
    context = load_dashboard_context(base_url, query, prefer_live)
except DashboardApiError as exc:
    st.error(str(exc))
    st.stop()

predictions = context.model_predictions
cols = st.columns(4)
with cols[0]:
    stat_card("Day Type", str(predictions.get("day_type_model")), "model output")
with cols[1]:
    stat_card("Breakout Prob.", str(predictions.get("breakout_model")), "probability")
with cols[2]:
    stat_card("Reversal Prob.", str(predictions.get("reversal_model")), "probability")
with cols[3]:
    stat_card("As Of", context.as_of_timestamp.replace("T", " "), context.data_source)

summary = context.day_type_summary
if summary:
    narrative_card("Day Type Summary", str(summary[0]))

for model_name in ["day_type_model", "breakout_model", "reversal_model"]:
    if predictions.get(model_name) is None:
        st.info(f"{model_name} is not available yet.")

report_frame = pd.DataFrame([{"model": key, "value": value} for key, value in predictions.items()])
data_table(report_frame, ["model", "value"], height=220)
