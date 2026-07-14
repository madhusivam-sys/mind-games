from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from dashboard.theme import apply_theme, hero
from integrations.telegram_client import TelegramError, send_telegram_message
from services.cpr_scanner import BhavcopyError, download_bhavcopy_history, load_bhavcopy_files, scan_latest, telegram_report
from utils.config import get_settings


def _store_scan(history: pd.DataFrame) -> None:
    with st.spinner("Calculating CPR and Camarilla structures…"):
        st.session_state["cpr_results"] = scan_latest(history)
        st.session_state["cpr_rows"] = len(history)


def main() -> None:
    apply_theme()
    hero(
        "NSE CPR Scanner",
        "End-of-day stock discovery from official NSE bhavcopy data. Every watchlist candidate includes the exact technical conditions that put it on the list.",
    )

    source_tab, upload_tab, rules_tab = st.tabs(["Download from NSE", "Upload bhavcopies", "How signals work"])
    with source_tab:
        left, middle = st.columns([1.1, 1])
        with left:
            as_of = st.date_input("Latest trading date", value=date.today(), max_value=date.today())
        with middle:
            history_days = st.slider("Trading days", min_value=5, max_value=40, value=20)
        st.caption("Only NSE stock futures from the F&O bhavcopy are screened. Modern STF rows are shown as legacy FUTSTK. Holidays and missing dates are skipped automatically.")
        if st.button("Download & scan", type="primary", width="stretch"):
            try:
                with st.spinner("Downloading official NSE end-of-day files…"):
                    history = download_bhavcopy_history(as_of, history_days, ("FO",))
                _store_scan(history)
            except (BhavcopyError, OSError) as exc:
                st.error(str(exc))

    with upload_tab:
        uploads = st.file_uploader(
            "Choose daily NSE bhavcopy CSV or ZIP files",
            type=["csv", "zip"],
            accept_multiple_files=True,
            help="Use at least 5 recent trading days for useful narrow/ascending CPR comparisons.",
        )
        if st.button("Scan uploaded files", disabled=not uploads, width="stretch"):
            try:
                history = load_bhavcopy_files([(upload.name, upload.getvalue()) for upload in uploads])
                _store_scan(history)
            except (BhavcopyError, ValueError) as exc:
                st.error(str(exc))

    with rules_tab:
        st.markdown(
            """
            - **Narrow CPR:** current width is in the lowest 30% of the last 20 observations and no wider than 0.70% of pivot.
            - **Ascending / descending:** the whole CPR moves above / below the previous CPR.
            - **Trend reversal:** an end-of-day pivot/CPR reclaim or rejection, confirmed against the prior pivot relationship.
            - **Virgin CPR:** the session's range never touched its CPR.
            - **Inside / outside CPR:** today's range of BC–TC is contained by, or contains, the previous CPR.
            - **Camarilla S3 / R3:** close is within 0.35% of the prior-range S3 or R3 level.
            - **Developing CPR:** tomorrow's CPR, calculated from today's completed high, low, and close.

            Only NSE stock futures are screened. Modern UDiFF `STF` rows are normalized to legacy `FUTSTK`; cash equities, index futures, and all options are excluded.

            Results are technical watchlist candidates, not buy/sell signals. Corporate actions and unusual volume should be checked separately.
            """
        )

    results = st.session_state.get("cpr_results")
    if results is None:
        st.info("Start with an NSE download or upload several daily bhavcopies.")
        return
    if results.empty:
        st.warning("The files did not contain enough consecutive history to compare CPR structures.")
        return

    latest_date = max(results["session_date"])
    strong = results[results["score"] >= 4]
    bullish = results[results["direction"] == "Bullish"]
    bearish = results[results["direction"] == "Bearish"]
    cards = st.columns(4)
    cards[0].metric("As of", str(latest_date))
    cards[1].metric("Symbols evaluated", f"{len(results):,}")
    cards[2].metric("High-confluence", f"{len(strong):,}")
    cards[3].metric("Bias split", f"{len(bullish)} ↑ / {len(bearish)} ↓")

    st.subheader("Stocks to track")
    asset_filter = st.multiselect("Asset type", sorted(results["asset_type"].unique()), default=sorted(results["asset_type"].unique()))
    direction_filter = st.multiselect("Direction", ["Bullish", "Bearish", "Neutral"], default=["Bullish", "Bearish", "Neutral"])
    filtered = results[results["asset_type"].isin(asset_filter) & results["direction"].isin(direction_filter)].copy()
    st.dataframe(
        filtered[["symbol", "asset_type", "direction", "score", "close", "cpr_width_pct", "pivot", "developing_pivot", "reasons"]],
        width="stretch",
        hide_index=True,
        column_config={
            "score": st.column_config.ProgressColumn("Confluence", min_value=0, max_value=max(10, int(results["score"].max()))),
            "cpr_width_pct": st.column_config.NumberColumn("CPR width %", format="%.3f%%"),
        },
    )

    top = filtered.head(20)
    if not top.empty:
        chart = px.bar(top.sort_values("score"), x="score", y="symbol", color="direction", orientation="h", color_discrete_map={"Bullish": "#0f9d7a", "Bearish": "#c2410c", "Neutral": "#64748b"})
        chart.update_layout(height=max(320, len(top) * 28), margin=dict(l=0, r=0, t=12, b=0), legend_title_text="")
        st.plotly_chart(chart, width="stretch")

    st.download_button(
        "Download results CSV",
        filtered.to_csv(index=False).encode("utf-8"),
        file_name=f"cpr-scanner-{latest_date}.csv",
        mime="text/csv",
        width="stretch",
    )

    st.subheader("Telegram report")
    settings = get_settings()
    configured = bool(settings.telegram_bot_token and settings.telegram_chat_id)
    st.caption("Nightly delivery is scheduled for 9:00 PM Asia/Kolkata when the scheduler service is running.")
    if configured:
        if st.button("Send this report now", width="stretch"):
            try:
                send_telegram_message(settings.telegram_bot_token or "", settings.telegram_chat_id or "", telegram_report(filtered))
                st.success("Report sent to Telegram.")
            except TelegramError as exc:
                st.error(str(exc))
    else:
        st.warning("Add TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to enable delivery.")


if __name__ == "__main__":
    main()
