from __future__ import annotations

import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from dashboard.bootstrap import ensure_src_on_path

ensure_src_on_path()

import streamlit as st

from dashboard.api_client import DashboardApiError
from dashboard.components.cards import bullet_card, narrative_card, score_card, stat_card
from dashboard.data import dashboard_sidebar, load_dashboard_context
from dashboard.theme import apply_theme, hero, panel_end, panel_start


def main() -> None:
    apply_theme()
    base_url, query, prefer_live = dashboard_sidebar()
    hero(
        "Decision intelligence for the Indian market",
        "A focused workspace for market structure, intraday context, model evidence, review discipline and liquid F&O screening.",
        eyebrow="BAZAAR MIND GAMES",
        badges=["Auction structure", "Risk-first signals", "F&O radar", "Auditable models"],
    )

    try:
        context = load_dashboard_context(base_url, query, prefer_live)
    except DashboardApiError as exc:
        st.error(str(exc))
        st.stop()

    brief = context.briefing
    primary = brief.get("primary_setup")
    watch = brief.get("watch_setup")

    top_row = st.columns(4)
    with top_row[0]:
        stat_card("Market regime", str(brief.get("market_state", "Unknown")), str(brief.get("bias", "neutral")))
    with top_row[1]:
        stat_card("Data source", context.data_source, context.session_mode)
    with top_row[2]:
        stat_card("Last update", context.as_of_timestamp.replace("T", " "), query.symbol)
    with top_row[3]:
        auth_caption = str(context.auth_status.get("detail", "no auth detail"))
        stat_card("Auth", "ok" if context.auth_status.get("authorized") else "blocked", auth_caption)

    lower = st.columns([1.25, 1, 1])
    with lower[0]:
        panel_start()
        st.subheader("Primary thesis")
        if primary is not None:
            score_card(str(primary["setup_name"]).replace("_", " ").title(), str(primary["score"]), str(primary["label"]), tone=str(primary["label"]))
            st.write(str(brief.get("summary", "")))
            st.caption(str(brief.get("invalidation", "")))
        else:
            st.write("No clear confirmed idea yet. Stay selective and wait for better alignment.")
        panel_end()
    with lower[1]:
        narrative_card("Trigger", str(brief.get("trigger", "No trigger available.")))
        if watch is not None:
            narrative_card("1-Minute Watch", str(watch.get("summary", "")))
    with lower[2]:
        bullet_card("Targets", list(brief.get("targets", [])))
        bullet_card("Structure Notes", list(brief.get("structure_notes", [])))


if __name__ == "__main__":
    main()
