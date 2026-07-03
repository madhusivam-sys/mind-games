from __future__ import annotations

from dashboard.bootstrap import ensure_src_on_path

ensure_src_on_path()

import pandas as pd
import streamlit as st

from dashboard.api_client import DashboardApiError
from dashboard.components.cards import stat_card
from dashboard.components.tables import data_table
from dashboard.data import dashboard_sidebar, load_dashboard_context
from dashboard.theme import apply_theme, hero

apply_theme()
base_url, query, prefer_live = dashboard_sidebar()
hero("Trade Review", "Review recent bars, confirmed signals, and simple forward excursion context.")

try:
    context = load_dashboard_context(base_url, query, prefer_live)
except DashboardApiError as exc:
    st.error(str(exc))
    st.stop()

history = context.history.copy()
history["timestamp"] = pd.to_datetime(history["timestamp"])
history["forward_3bar_move"] = pd.to_numeric(history["close"], errors="coerce").shift(-3) - pd.to_numeric(history["close"], errors="coerce")

signal_frame = pd.DataFrame(context.signal_snapshot["scores"])
cols = st.columns(3)
with cols[0]:
    stat_card("Rows Reviewed", str(len(history)), query.symbol)
with cols[1]:
    stat_card("Confirmed Signals", str(len(signal_frame)), query.interval)
with cols[2]:
    expectancy = history["forward_3bar_move"].dropna().mean()
    stat_card("Avg +3 Bar Move", f"{expectancy:,.2f}", "simple proxy")

st.subheader("Confirmed Signal Snapshot")
data_table(signal_frame, ["timestamp", "symbol", "setup_name", "score", "label", "summary"], height=220)

st.subheader("Recent Replay Table")
data_table(history.tail(40), ["timestamp", "symbol", "open", "high", "low", "close", "volume", "forward_3bar_move"], height=380)
