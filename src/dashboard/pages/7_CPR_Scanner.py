from __future__ import annotations

from html import escape
import sys
from datetime import date
from pathlib import Path

import httpx
import pandas as pd
import plotly.express as px
import streamlit as st

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from dashboard.cpr_scanner_view import prepare_action_table
from dashboard.theme import apply_theme, hero
from integrations.telegram_client import TelegramError, send_telegram_message
from services.cpr_scanner import (
    BhavcopyError,
    attach_mwpl_snapshot,
    download_bhavcopy_history,
    download_mwpl_snapshot,
    load_bhavcopy_files,
    scan_latest,
    telegram_report,
)
from utils.config import get_settings


def _store_scan(history: pd.DataFrame) -> None:
    if "mwpl_utilization_pct" not in history:
        try:
            history = attach_mwpl_snapshot(history, download_mwpl_snapshot())
        except (BhavcopyError, httpx.HTTPError, OSError):
            pass
    with st.spinner("Calculating CPR, OI and MWPL structures…"):
        st.session_state["cpr_results"] = scan_latest(history)
        st.session_state["cpr_rows"] = len(history)


def _scanner_styles() -> None:
    st.markdown(
        """
        <style>
        .cpr-hero {
            position: relative; overflow: hidden; padding: 1.65rem 1.8rem;
            border-radius: 26px; margin-bottom: 1rem; color: #f8fafc;
            background: linear-gradient(128deg, #111c2c 0%, #1d3652 70%, #215c58 120%);
            box-shadow: 0 22px 48px rgba(15, 23, 42, .18);
        }
        .cpr-hero:after {
            content: ""; position: absolute; width: 260px; height: 260px;
            right: -80px; top: -120px; border-radius: 999px;
            background: rgba(69, 201, 167, .13); border: 1px solid rgba(255,255,255,.08);
        }
        .cpr-eyebrow { color: #79dec2; font-size: .72rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }
        .cpr-hero h1 { margin: .28rem 0 .38rem; font-size: clamp(1.8rem, 4vw, 2.55rem); letter-spacing: -.045em; }
        .cpr-hero p { max-width: 760px; margin: 0; color: rgba(248,250,252,.72); line-height: 1.55; }
        .cpr-badges { display: flex; gap: .48rem; flex-wrap: wrap; margin-top: 1rem; }
        .cpr-badge { padding: .28rem .58rem; border-radius: 999px; font-size: .72rem; font-weight: 600; background: rgba(255,255,255,.09); border: 1px solid rgba(255,255,255,.1); }
        .cpr-kpi { min-height: 116px; padding: 1rem 1.05rem; border-radius: 14px; background: rgba(255,254,250,.92); border: 1px solid rgba(56,56,97,.12); box-shadow: 0 12px 28px rgba(51,51,51,.055); }
        .cpr-kpi-label { color: #86894B; font-family: 'Montserrat', sans-serif; font-size: .68rem; letter-spacing: .12em; font-weight: 700; text-transform: uppercase; }
        .cpr-kpi-value { margin-top: .28rem; color: #333333; font-family: 'Montserrat', sans-serif; font-size: 1.72rem; font-weight: 700; letter-spacing: -.04em; }
        .cpr-kpi-note { margin-top: .22rem; color: #6F746F; font-size: .78rem; }
        .cpr-section { margin: 1.35rem 0 .55rem; }
        .cpr-section h2 { margin: 0; color: #333333; font-size: 1.2rem; letter-spacing: -.02em; }
        .cpr-section p { margin: .2rem 0 0; color: #6F746F; font-size: .85rem; }
        .cpr-focus { min-height: 204px; padding: 1.05rem; border-radius: 14px; background: rgba(255,254,250,.92); border: 1px solid rgba(56,56,97,.12); box-shadow: 0 13px 30px rgba(51,51,51,.06); }
        .cpr-focus.bullish { border-top: 3px solid #3C7B53; }
        .cpr-focus.bearish { border-top: 3px solid #B84A3A; }
        .cpr-focus.neutral { border-top: 3px solid #64748b; }
        .cpr-focus-top { display: flex; justify-content: space-between; align-items: center; color: #86894B; font-family: 'Montserrat', sans-serif; font-size: .68rem; font-weight: 700; text-transform: uppercase; letter-spacing: .09em; }
        .cpr-focus-symbol { margin-top: .72rem; color: #333333; font-family: 'Montserrat', sans-serif; font-size: 1.55rem; font-weight: 700; letter-spacing: -.04em; }
        .cpr-focus-price { color: #6F746F; font-family: ui-monospace, Consolas, monospace; font-size: .88rem; }
        .cpr-focus-score { display: inline-flex; margin-top: .72rem; padding: .26rem .55rem; border-radius: 999px; background: rgba(56,56,97,.07); color: #383861; font-size: .75rem; font-weight: 700; }
        .cpr-focus-trigger { margin-top: .72rem; color: #333333; font-size: .84rem; line-height: 1.4; }
        .cpr-focus-meta { margin-top: .42rem; color: #6F746F; font-size: .75rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .cpr-empty { padding: 2.4rem 1rem; text-align: center; border: 1px dashed rgba(24,37,53,.16); border-radius: 22px; background: rgba(255,255,255,.55); }
        .cpr-empty strong { display: block; margin-bottom: .3rem; color: #182535; font-size: 1.08rem; }
        div[data-testid="stExpander"] { border: 1px solid rgba(24,37,53,.08); border-radius: 18px; background: rgba(255,255,255,.58); }
        div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 20px; border-color: rgba(24,37,53,.08); background: rgba(255,255,255,.7); }
        div[data-testid="stDataFrame"] { box-shadow: 0 12px 30px rgba(15,23,42,.05); }
        @media (max-width: 760px) { .cpr-hero { padding: 1.3rem; } .cpr-focus { min-height: auto; } }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _hero() -> None:
    hero(
        "CPR futures radar",
        "Rank the 50 most liquid NSE stock futures with CPR structure, all-expiry open interest and official MWPL crowding.",
        eyebrow="NSE DERIVATIVES",
        badges=["FUTSTK only", "Top 50 liquidity", "Nearest-expiry CPR", "9 PM Telegram"],
    )


def _kpi(label: str, value: str, note: str) -> None:
    st.markdown(
        f'<div class="cpr-kpi"><div class="cpr-kpi-label">{escape(label)}</div><div class="cpr-kpi-value">{escape(value)}</div><div class="cpr-kpi-note">{escape(note)}</div></div>',
        unsafe_allow_html=True,
    )


def _section(title: str, caption: str) -> None:
    st.markdown(
        f'<div class="cpr-section"><h2>{escape(title)}</h2><p>{escape(caption)}</p></div>',
        unsafe_allow_html=True,
    )


def _focus_card(rank: int, candidate: pd.Series) -> None:
    direction = str(candidate["direction"])
    tone = direction.lower() if direction in {"Bullish", "Bearish", "Neutral"} else "neutral"
    oi = str(candidate.get("oi_view", "OI unavailable"))
    mwpl = str(candidate.get("mwpl_view", "MWPL unavailable"))
    st.markdown(
        f"""
        <div class="cpr-focus {tone}">
          <div class="cpr-focus-top"><span>#{rank} · {escape(str(candidate['plan']))}</span><span>Liq #{int(candidate['liquidity_rank'])}</span></div>
          <div class="cpr-focus-symbol">{escape(str(candidate['symbol']))}</div>
          <div class="cpr-focus-price">₹{float(candidate['close']):,.2f} · {escape(direction)}</div>
          <div class="cpr-focus-score">Score {int(candidate['score'])} · CPR {int(candidate['technical_score'])} · OI {int(candidate['oi_score']):+d}</div>
          <div class="cpr-focus-trigger">{escape(str(candidate['trigger']))}</div>
          <div class="cpr-focus-meta">{escape(oi)} · MWPL {escape(mwpl)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _scan_controls(results: pd.DataFrame | None) -> None:
    with st.expander("Run or refresh the scan", expanded=results is None):
        source_tab, upload_tab, rules_tab = st.tabs(["Official NSE data", "Upload files", "Methodology"])
        with source_tab:
            left, middle = st.columns([1.15, 1])
            with left:
                as_of = st.date_input("Latest trading date", value=date.today(), max_value=date.today())
            with middle:
                history_days = st.slider("History", min_value=5, max_value=40, value=20, help="Twenty sessions is recommended for stable liquidity and CPR percentiles.")
            st.caption("Downloads only official NSE F&O files and keeps stock futures (STF/FUTSTK).")
            if st.button("Download and run scan", type="primary", width="stretch"):
                try:
                    with st.spinner("Downloading official NSE end-of-day files…"):
                        history = download_bhavcopy_history(as_of, history_days, ("FO",))
                    _store_scan(history)
                    st.rerun()
                except (BhavcopyError, httpx.HTTPError, OSError) as exc:
                    st.error(str(exc))

        with upload_tab:
            uploads = st.file_uploader(
                "NSE F&O bhavcopy files",
                type=["csv", "zip"],
                accept_multiple_files=True,
                help="Upload at least five daily files; twenty is recommended.",
            )
            if st.button("Scan uploaded files", disabled=not uploads, width="stretch"):
                try:
                    history = load_bhavcopy_files([(upload.name, upload.getvalue()) for upload in uploads])
                    _store_scan(history)
                    st.rerun()
                except (BhavcopyError, ValueError) as exc:
                    st.error(str(exc))

        with rules_tab:
            rules_left, rules_right = st.columns(2)
            with rules_left:
                st.markdown(
                    """
                    **Price structure**

                    - Narrow, ascending and descending CPR
                    - Virgin, inside and outside CPR
                    - Trend reversal and developing CPR
                    - Camarilla S3 / R3 proximity
                    """
                )
            with rules_right:
                st.markdown(
                    """
                    **Participation and risk**

                    - OI aggregated across every stock-futures expiry
                    - Top 50 by 20-session median FUTSTK turnover
                    - MWPL 80%+ penalized; 95% or ban status blocked
                    - Technical watchlist only—not an execution signal
                    """
                )


def _results_board(results: pd.DataFrame) -> None:
    latest_date = max(results["session_date"])
    eligible = results.get("eligible", pd.Series(True, index=results.index)).fillna(False)
    high_confluence = eligible & results["score"].ge(4)
    crowded = results.get("mwpl_utilization_pct", pd.Series(index=results.index, dtype=float)).ge(80)
    bullish = results["direction"].eq("Bullish").sum()
    bearish = results["direction"].eq("Bearish").sum()

    cards = st.columns(4)
    with cards[0]:
        _kpi("Market date", str(latest_date), "Latest completed NSE session")
    with cards[1]:
        _kpi("Liquid universe", f"{len(results)} / 50", "Re-ranked every scan")
    with cards[2]:
        _kpi("Actionable", str(int(high_confluence.sum())), "Eligible with score 4+")
    with cards[3]:
        _kpi("Bias", f"{bullish} ↑  {bearish} ↓", f"{int(crowded.sum())} crowded by MWPL")

    action_table = prepare_action_table(results)
    _section("Tonight's radar", "The highest-ranked eligible contracts after CPR, OI and MWPL scoring.")

    filter_left, filter_bias, filter_status, filter_score = st.columns([1.55, 1, 1, 1])
    with filter_left:
        symbol_query = st.text_input("Search symbol", placeholder="e.g. RELIANCE", label_visibility="collapsed")
    with filter_bias:
        bias_filter = st.selectbox("Bias", ["All biases", "Bullish", "Bearish", "Neutral"], label_visibility="collapsed")
    with filter_status:
        status_filter = st.selectbox("Status", ["All statuses", "Track", "Crowding risk", "Avoid fresh positions"], label_visibility="collapsed")
    with filter_score:
        maximum_score = max(1, int(results["score"].max()))
        minimum_score = st.selectbox("Minimum score", list(range(0, maximum_score + 1)), index=min(3, maximum_score), format_func=lambda value: f"Score {value}+", label_visibility="collapsed")

    filtered = action_table[action_table["score"] >= minimum_score].copy()
    if symbol_query.strip():
        filtered = filtered[filtered["symbol"].str.contains(symbol_query.strip(), case=False, regex=False)]
    if bias_filter != "All biases":
        filtered = filtered[filtered["direction"] == bias_filter]
    if status_filter != "All statuses":
        filtered = filtered[filtered["status"] == status_filter]

    st.caption(f"{len(filtered)} of {len(results)} contracts · CPR uses nearest expiry · OI and liquidity use all expiries")
    focus_mask = filtered.get("eligible", pd.Series(True, index=filtered.index)).fillna(False).astype(bool)
    focus = filtered[focus_mask].head(3)
    if not focus.empty:
        focus_columns = st.columns(3)
        for rank, (_, candidate) in enumerate(focus.iterrows(), start=1):
            with focus_columns[rank - 1]:
                _focus_card(rank, candidate)

    _section("Action table", "Scan quickly here, then open one contract below for the complete evidence trail.")
    if filtered.empty:
        st.warning("No contracts match these filters. Clear the symbol or lower the score threshold.")
        return

    display = filtered[["liquidity_rank", "symbol", "bias", "score", "technical_score", "oi_score", "oi_view", "mwpl_view", "status", "trigger"]]
    st.dataframe(
        display,
        width="stretch",
        hide_index=True,
        height=min(590, 76 + (len(display.head(14)) * 35)),
        column_config={
            "liquidity_rank": st.column_config.NumberColumn("Liq #", format="%d", width="small"),
            "symbol": st.column_config.TextColumn("Future", width="small"),
            "bias": st.column_config.TextColumn("Bias", width="small"),
            "score": st.column_config.ProgressColumn("Total", min_value=0, max_value=maximum_score, width="small"),
            "technical_score": st.column_config.NumberColumn("CPR", format="%d", width="small"),
            "oi_score": st.column_config.NumberColumn("OI", format="%+d", width="small"),
            "oi_view": st.column_config.TextColumn("OI regime", width="medium"),
            "mwpl_view": st.column_config.TextColumn("MWPL", width="small"),
            "status": st.column_config.TextColumn("Risk state", width="medium"),
            "trigger": st.column_config.TextColumn("Review level", width="large"),
        },
    )

    _section("Contract review", "A compact score breakdown and the exact levels behind the selected row.")
    selected_symbol = st.selectbox("Select contract", filtered["symbol"].tolist(), label_visibility="collapsed")
    selected = filtered[filtered["symbol"] == selected_symbol].iloc[0]
    detail_left, detail_middle, detail_right = st.columns([1.15, 1, 1])
    with detail_left:
        with st.container(border=True):
            st.caption("PRICE STRUCTURE")
            st.metric(str(selected["symbol"]), f"₹{float(selected['close']):,.2f}", str(selected["bias"]))
            st.write(f"**CPR:** {selected['cpr_band']}")
            st.caption(str(selected["trigger"]))
    with detail_middle:
        with st.container(border=True):
            st.caption("SCORE BREAKDOWN")
            st.metric("Total score", int(selected["score"]), f"CPR {int(selected['technical_score'])} · OI {int(selected['oi_score']):+d}")
            st.write(f"**OI:** {selected['oi_view']}")
            st.write(f"**MWPL:** {selected['mwpl_view']} ({int(selected['mwpl_score']):+d})")
    with detail_right:
        with st.container(border=True):
            st.caption("WHY IT RANKED")
            st.write(str(selected["reasons"]))
            st.caption(f"{selected['status']} · Liquidity rank #{int(selected['liquidity_rank'])}")

    with st.expander("Compare leading scores"):
        top = filtered.head(15)
        chart = px.bar(
            top.sort_values("score"), x="score", y="symbol", color="direction", orientation="h",
            color_discrete_map={"Bullish": "#0f9d7a", "Bearish": "#c2410c", "Neutral": "#64748b"},
        )
        chart.update_layout(
            height=max(320, len(top) * 28), margin=dict(l=0, r=0, t=10, b=0), legend_title_text="",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="Confluence score", yaxis_title="",
        )
        st.plotly_chart(chart, width="stretch")

    action_left, action_right = st.columns(2)
    with action_left:
        st.download_button(
            "Download filtered CSV", filtered.to_csv(index=False).encode("utf-8"),
            file_name=f"cpr-scanner-{latest_date}.csv", mime="text/csv", width="stretch",
        )
    with action_right:
        settings = get_settings()
        configured = bool(settings.telegram_bot_token and settings.telegram_chat_id)
        if configured:
            if st.button("Send filtered report to Telegram", width="stretch"):
                try:
                    send_telegram_message(settings.telegram_bot_token or "", settings.telegram_chat_id or "", telegram_report(filtered))
                    st.success("Report sent to Telegram.")
                except TelegramError as exc:
                    st.error(str(exc))
        else:
            st.button("Telegram is not configured", disabled=True, width="stretch")


def _legacy_main() -> None:
    apply_theme()
    hero(
        "FUTSTK CPR Action Board",
        "A clean end-of-day shortlist from NSE stock futures—ranked by confluence, with the CPR level and technical condition to review next.",
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
            - **Liquidity universe:** only the top 50 underlyings by 20-session median aggregate FUTSTK turnover are retained. All expiries are included.
            - **OI interpretation:** price up/OI up = long buildup; price down/OI up = short buildup; price up/OI down = short covering; price down/OI down = long unwinding.
            - **MWPL gate:** 80%+ reduces the score, 90%+ applies a stronger penalty, and 95% or an official “No Fresh Positions” status blocks fresh-position candidates.

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
    cards[1].metric("Liquid universe", f"{len(results):,} / 50")
    cards[2].metric("High-confluence", f"{len(strong):,}")
    cards[3].metric("Bias split", f"{len(bullish)} ↑ / {len(bearish)} ↓")

    action_table = prepare_action_table(results)
    st.subheader("Action board")
    filter_left, filter_middle, filter_right = st.columns([1.5, 1, 1])
    with filter_left:
        symbol_query = st.text_input("Find a stock future", placeholder="Type a symbol, e.g. LT")
    with filter_middle:
        bias_filter = st.selectbox("Bias", ["All", "Bullish", "Bearish", "Neutral"])
    with filter_right:
        max_score = max(1, int(results["score"].max()))
        minimum_score = st.slider("Minimum confluence", min_value=0, max_value=max_score, value=min(3, max_score))

    filtered = action_table[action_table["score"] >= minimum_score].copy()
    if symbol_query.strip():
        filtered = filtered[filtered["symbol"].str.contains(symbol_query.strip(), case=False, regex=False)]
    if bias_filter != "All":
        filtered = filtered[filtered["direction"] == bias_filter]

    st.caption(f"Showing {len(filtered):,} of {len(results):,} top-liquid FUTSTK underlyings · CPR uses nearest expiry; OI and liquidity aggregate all expiries")
    focus = filtered.head(3)
    if not focus.empty:
        st.markdown("#### Tonight's focus")
        focus_columns = st.columns(3)
        for rank, (_, candidate) in enumerate(focus.iterrows(), start=1):
            with focus_columns[rank - 1]:
                with st.container(border=True):
                    st.caption(f"#{rank} · {candidate['plan']}")
                    st.metric(str(candidate["symbol"]), f"₹{float(candidate['close']):,.2f}", str(candidate["bias"]))
                    st.write(f"**Score {int(candidate['score'])}** · {int(candidate['conditions'])} conditions")
                    st.caption(str(candidate["trigger"]))

    if filtered.empty:
        st.warning("No contracts match these filters. Lower the confluence threshold or clear the symbol search.")
        return

    display = filtered[["status", "liquidity_rank", "plan", "symbol", "bias", "score", "technical_score", "oi_score", "close", "oi_view", "mwpl_view", "trigger", "reasons"]]
    st.dataframe(
        display,
        width="stretch",
        hide_index=True,
        height=min(620, 82 + (len(display.head(14)) * 36)),
        column_config={
            "status": st.column_config.TextColumn("Status", width="medium"),
            "liquidity_rank": st.column_config.NumberColumn("Liq #", format="%d", width="small"),
            "plan": st.column_config.TextColumn("Watch plan", width="medium"),
            "symbol": st.column_config.TextColumn("Contract", width="small"),
            "bias": st.column_config.TextColumn("Bias", width="small"),
            "score": st.column_config.ProgressColumn("Score", min_value=0, max_value=max_score, width="small"),
            "technical_score": st.column_config.NumberColumn("CPR", format="%d", width="small"),
            "oi_score": st.column_config.NumberColumn("OI", format="%+d", width="small"),
            "conditions": st.column_config.NumberColumn("Checks", format="%d", width="small"),
            "close": st.column_config.NumberColumn("Close", format="₹ %.2f", width="small"),
            "oi_view": st.column_config.TextColumn("OI regime", width="medium"),
            "mwpl_view": st.column_config.TextColumn("MWPL", width="small"),
            "trigger": st.column_config.TextColumn("Review trigger", width="large"),
            "cpr_band": st.column_config.TextColumn("CPR band", width="medium"),
            "cpr_width_pct": st.column_config.NumberColumn("Width", format="%.3f%%", width="small"),
            "reasons": st.column_config.TextColumn("Why it ranked", width="large"),
        },
    )

    detail_left, detail_right = st.columns([1.2, 1])
    with detail_left:
        selected_symbol = st.selectbox("Inspect one contract", filtered["symbol"].tolist())
        selected = filtered[filtered["symbol"] == selected_symbol].iloc[0]
        st.write(str(selected["reasons"]))
        st.caption(f"Watch plan: {selected['plan']} · {selected['status']} · {selected['trigger']} · liquidity rank #{int(selected['liquidity_rank'])}")
    with detail_right:
        st.metric("CPR band", str(selected["cpr_band"]), f"{float(selected['cpr_width_pct']):.3f}% wide")
        st.write(f"**OI:** {selected['oi_view']} · score {int(selected['oi_score']):+d}")
        st.write(f"**MWPL:** {selected['mwpl_view']} · score {int(selected['mwpl_score']):+d}")
        st.caption("Decision-support only. Confirm live price structure and risk before taking any action.")

    with st.expander("View confluence chart"):
        top = filtered.head(15)
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


def main() -> None:
    apply_theme()
    _scanner_styles()
    _hero()

    results = st.session_state.get("cpr_results")
    _scan_controls(results)

    results = st.session_state.get("cpr_results")
    if results is None:
        st.markdown(
            '<div class="cpr-empty"><strong>Your evening radar is ready to be built.</strong>Run an official NSE scan above. The board will keep only the 50 most liquid stock futures and rank them with CPR, OI and MWPL context.</div>',
            unsafe_allow_html=True,
        )
        return
    if results.empty:
        st.warning("The supplied files did not contain enough consecutive history to compare CPR structures.")
        return
    _results_board(results)


if __name__ == "__main__":
    main()
