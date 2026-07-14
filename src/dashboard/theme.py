from __future__ import annotations

import hmac

import streamlit as st

from utils.config import get_settings


ACCENT = "#c58b2a"
SURFACE = "#fff9ef"
DEEP = "#182535"
MUTED = "#64748b"
SUCCESS = "#0f9d7a"
WARNING = "#d97706"
DANGER = "#c2410c"


def apply_theme() -> None:
    """Apply a warm, modern trading-workstation theme."""

    st.set_page_config(page_title="Bazaar Mind Games", layout="wide", initial_sidebar_state="expanded")
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
        :root {{
            --accent: {ACCENT};
            --surface: {SURFACE};
            --deep: {DEEP};
            --muted: {MUTED};
            --success: {SUCCESS};
            --warning: {WARNING};
            --danger: {DANGER};
        }}
        html, body, [class*="css"]  {{
            font-family: 'Space Grotesk', sans-serif;
        }}
        .stApp {{
            background:
                radial-gradient(circle at top right, rgba(197,139,42,0.18), transparent 26%),
                linear-gradient(180deg, #fcfaf5 0%, #f2eee5 100%);
            color: var(--deep);
        }}
        .block-container {{
            padding-top: 1.4rem;
            padding-bottom: 2rem;
        }}
        div[data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #0f172a 0%, #14223a 100%);
        }}
        div[data-testid="stSidebar"] * {{
            color: #f8fafc;
        }}
        .bm-panel {{
            background: rgba(255,255,255,0.84);
            border: 1px solid rgba(24,37,53,0.08);
            border-radius: 24px;
            padding: 1rem 1.1rem;
            box-shadow: 0 20px 40px rgba(15,23,42,0.08);
            backdrop-filter: blur(12px);
        }}
        .bm-hero {{
            padding: 1.35rem 1.5rem;
            border-radius: 28px;
            background: linear-gradient(135deg, rgba(24,37,53,0.96), rgba(38,56,82,0.92));
            color: #fff8ee;
            box-shadow: 0 24px 50px rgba(24,37,53,0.24);
            margin-bottom: 1rem;
        }}
        .bm-hero h1 {{
            margin: 0;
            font-size: 2rem;
            letter-spacing: -0.03em;
        }}
        .bm-hero p {{
            margin: 0.45rem 0 0 0;
            color: rgba(255,248,238,0.76);
        }}
        .bm-card {{
            background: rgba(255,255,255,0.9);
            border: 1px solid rgba(24,37,53,0.08);
            border-radius: 22px;
            padding: 1rem;
            min-height: 126px;
            box-shadow: 0 16px 32px rgba(15,23,42,0.06);
        }}
        .bm-kicker {{
            color: var(--muted);
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            margin-bottom: 0.5rem;
        }}
        .bm-value {{
            font-size: 1.9rem;
            font-weight: 700;
            color: var(--deep);
            line-height: 1.05;
        }}
        .bm-caption {{
            margin-top: 0.35rem;
            color: var(--muted);
            font-size: 0.9rem;
        }}
        .bm-score-pill {{
            display: inline-block;
            padding: 0.25rem 0.55rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 700;
            margin-bottom: 0.55rem;
            background: rgba(24,37,53,0.08);
            color: var(--deep);
        }}
        .bm-score-pill.buy, .bm-score-pill.high {{ background: rgba(15,157,122,0.15); color: var(--success); }}
        .bm-score-pill.watch, .bm-score-pill.warning {{ background: rgba(217,119,6,0.15); color: var(--warning); }}
        .bm-score-pill.sell, .bm-score-pill.alert {{ background: rgba(194,65,12,0.15); color: var(--danger); }}
        .bm-mono {{
            font-family: 'IBM Plex Mono', monospace;
        }}
        div[data-testid="stDataFrame"] {{
            border-radius: 18px;
            overflow: hidden;
            border: 1px solid rgba(24,37,53,0.08);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    _require_dashboard_password()


def _require_dashboard_password() -> None:
    configured_password = get_settings().dashboard_password
    if not configured_password:
        return
    if st.session_state.get("_dashboard_authenticated"):
        if st.sidebar.button("Lock dashboard", key="_lock_dashboard"):
            st.session_state["_dashboard_authenticated"] = False
            st.rerun()
        return

    st.title("Bazaar Mind Games")
    st.caption("Enter the private dashboard password to continue.")
    supplied = st.text_input("Dashboard password", type="password", key="_dashboard_password_input")
    if st.button("Unlock", type="primary", key="_unlock_dashboard"):
        if hmac.compare_digest(supplied, configured_password):
            st.session_state["_dashboard_authenticated"] = True
            st.rerun()
        st.error("Incorrect password.")
    st.stop()


def hero(title: str, subtitle: str) -> None:
    st.markdown(f"<section class='bm-hero'><h1>{title}</h1><p>{subtitle}</p></section>", unsafe_allow_html=True)


def panel_start() -> None:
    st.markdown("<div class='bm-panel'>", unsafe_allow_html=True)


def panel_end() -> None:
    st.markdown("</div>", unsafe_allow_html=True)
