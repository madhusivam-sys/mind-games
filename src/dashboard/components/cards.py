from __future__ import annotations

from html import escape

import streamlit as st


def stat_card(title: str, value: str, caption: str, tone: str = "neutral") -> None:
    st.markdown(
        f"""
        <div class='bm-card'>
            <div class='bm-kicker'>{escape(title)}</div>
            <div class='bm-value'>{escape(value)}</div>
            <div class='bm-caption'>{escape(caption)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def score_card(title: str, value: str, caption: str, tone: str = "neutral") -> None:
    safe_tone = tone if tone in {"buy", "sell", "high", "watch", "warning", "alert", "neutral"} else "neutral"
    st.markdown(
        f"""
        <div class='bm-card'>
            <div class='bm-score-pill {safe_tone}'>{escape(caption)}</div>
            <div class='bm-kicker'>{escape(title)}</div>
            <div class='bm-value'>{escape(value)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def narrative_card(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class='bm-card'>
            <div class='bm-kicker'>{escape(title)}</div>
            <div class='bm-caption'>{escape(body)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def bullet_card(title: str, items: list[str]) -> None:
    bullet_rows = "".join(f"<li>{escape(item)}</li>" for item in items) if items else "<li>No current notes.</li>"
    st.markdown(
        f"""
        <div class='bm-card'>
            <div class='bm-kicker'>{escape(title)}</div>
            <div class='bm-caption'><ul>{bullet_rows}</ul></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
