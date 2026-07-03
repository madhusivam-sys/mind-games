from __future__ import annotations

import streamlit as st


def stat_card(title: str, value: str, caption: str, tone: str = "neutral") -> None:
    st.markdown(
        f"""
        <div class='bm-card'>
            <div class='bm-kicker'>{title}</div>
            <div class='bm-value'>{value}</div>
            <div class='bm-caption'>{caption}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def score_card(title: str, value: str, caption: str, tone: str = "neutral") -> None:
    st.markdown(
        f"""
        <div class='bm-card'>
            <div class='bm-score-pill {tone}'>{caption}</div>
            <div class='bm-kicker'>{title}</div>
            <div class='bm-value'>{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def narrative_card(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class='bm-card'>
            <div class='bm-kicker'>{title}</div>
            <div class='bm-caption'>{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def bullet_card(title: str, items: list[str]) -> None:
    bullet_rows = "".join(f"<li>{item}</li>" for item in items) if items else "<li>No current notes.</li>"
    st.markdown(
        f"""
        <div class='bm-card'>
            <div class='bm-kicker'>{title}</div>
            <div class='bm-caption'><ul>{bullet_rows}</ul></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
