from __future__ import annotations

from dashboard.bootstrap import ensure_src_on_path

ensure_src_on_path()

import streamlit as st

from dashboard.api_client import DashboardApiError
from dashboard.components.cards import bullet_card, narrative_card, stat_card
from dashboard.components.tables import data_table
from dashboard.data import dashboard_sidebar, load_dashboard_context
from dashboard.theme import apply_theme, hero

apply_theme()
base_url, query, prefer_live = dashboard_sidebar()
hero("Pre-Market Structure", "Prior value, Camarilla, CPR, session mode, and the source state behind the briefing.")

try:
    context = load_dashboard_context(base_url, query, prefer_live)
except DashboardApiError as exc:
    st.error(str(exc))
    st.stop()

prior = context.prior_session
row = st.columns(4)
with row[0]:
    stat_card("Prior POC", f"{float(prior['poc']):,.2f}", prior['session_date'])
with row[1]:
    stat_card("Prior VAH", f"{float(prior['vah']):,.2f}", "value high")
with row[2]:
    stat_card("Prior VAL", f"{float(prior['val']):,.2f}", "value low")
with row[3]:
    stat_card("Pivot", f"{float(prior['pivot']):,.2f}", context.data_source)

cards = st.columns(3)
with cards[0]:
    bullet_card("Camarilla Map", [f"H3 {float(prior['h3']):,.2f}", f"H4 {float(prior.get('h4', 0.0)):.2f}", f"L3 {float(prior['l3']):,.2f}", f"L4 {float(prior.get('l4', 0.0)):.2f}"])
with cards[1]:
    narrative_card("Auction Frame", f"Acceptance around {float(prior['poc']):,.2f} is balance; initiative above {float(prior['vah']):,.2f} or below {float(prior['val']):,.2f} matters most.")
with cards[2]:
    narrative_card("Data Status", f"Mode {context.session_mode} | As of {context.as_of_timestamp.replace('T', ' ')}")

st.subheader("Auth Diagnostics")
data_table(
    st.session_state.get("_auth_frame") if False else __import__('pandas').DataFrame([context.auth_status]),
    ["configured", "authorized", "detail", "symbol", "as_of"],
    height=140,
)

st.subheader("Recent Context Bar")
history = context.features.copy() if not context.features.empty else context.history.copy()
previous_frame = history[history["session_date"] == prior["session_date"]].tail(1) if "session_date" in history.columns else history.tail(1)
data_table(previous_frame, ["timestamp", "symbol", "developing_poc", "vah", "val", "h3", "h4", "l3", "l4", "pivot", "bc", "tc"], height=150)
