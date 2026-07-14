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
hero("Model Insights", "Use statistical evidence alongside the same market context shown across the workspace.", eyebrow="QUANTITATIVE EVIDENCE", badges=["Day Type", "Breakout Evidence", "Reversal Evidence"])

try:
    context = load_dashboard_context(base_url, query, prefer_live)
except DashboardApiError as exc:
    st.error(str(exc))
    st.stop()

predictions = context.model_predictions
cols = st.columns(4)
if context.data_source == "NSE F&O Bhavcopy":
    with cols[0]:
        stat_card("Structure Type", str(predictions.get("day_type_model")), "Daily CPR Classification")
    with cols[1]:
        stat_card("CPR Score", str(predictions.get("technical_score", 0)), "Technical Confluence")
    with cols[2]:
        stat_card("OI Score", f"{int(predictions.get('oi_score', 0)):+d}", "Participation Alignment")
    with cols[3]:
        stat_card("MWPL Score", f"{int(predictions.get('mwpl_score', 0)):+d}", "Crowding Adjustment")
    narrative_card(
        "Bhavcopy Engine Interpretation",
        "CPR, all-expiry open interest, liquidity rank and MWPL are calculated from the official NSE F&O Bhavcopy. These are evidence scores, not predictive probabilities.",
    )
else:
    st.warning(
        str(
            predictions.get(
                "model_notice",
                "These experimental baseline models are not calibrated for trading use.",
            )
        )
    )
    with cols[0]:
        stat_card("Day Type", str(predictions.get("day_type_model")), "Model Output")
    with cols[1]:
        stat_card("Breakout Probability", str(predictions.get("breakout_model")), "Probability")
    with cols[2]:
        stat_card("Reversal Probability", str(predictions.get("reversal_model")), "Probability")
    with cols[3]:
        stat_card("As Of", context.as_of_timestamp.replace("T", " "), context.data_source)

summary = context.day_type_summary
if summary:
    narrative_card("Day Type Summary", str(summary[0]))

if context.data_source != "NSE F&O Bhavcopy":
    for model_name in ["day_type_model", "breakout_model", "reversal_model"]:
        if predictions.get(model_name) is None:
            st.info(f"{model_name.replace('_', ' ').title()} Is Not Available Yet.")

report_frame = pd.DataFrame([{"model": key, "value": value} for key, value in predictions.items()])
data_table(report_frame, ["model", "value"], height=220)
