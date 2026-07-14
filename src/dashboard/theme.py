from __future__ import annotations

from html import escape
import hmac
from pathlib import Path

import streamlit as st

from utils.config import get_settings


CHARCOAL = "#333333"
TEAL = "#20959A"
INDIGO = "#383861"
GREEN = "#3C7B53"
OLIVE = "#86894B"
GOLD = "#D5A63D"
CANVAS = "#F6F4EE"
SURFACE = "#FFFEFA"
MUTED = "#6F746F"
SUCCESS = GREEN
WARNING = "#B7791F"
DANGER = "#B84A3A"
LOGO_PATH = Path(__file__).resolve().parent / "assets" / "bmg-logo.png"


def apply_theme() -> None:
    """Apply the Bazaar Mind Games brand system across every Streamlit page."""

    st.set_page_config(page_title="Bazaar Mind Games", page_icon=str(LOGO_PATH), layout="wide", initial_sidebar_state="expanded")
    if LOGO_PATH.exists():
        st.logo(str(LOGO_PATH), size="large")
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Lato:ital,wght@0,400;0,700;1,400&family=Montserrat:ital,wght@0,500;0,600;0,700;1,500&display=swap');
        :root {{
            --bmg-charcoal: {CHARCOAL}; --bmg-teal: {TEAL}; --bmg-indigo: {INDIGO};
            --bmg-green: {GREEN}; --bmg-olive: {OLIVE}; --bmg-gold: {GOLD};
            --bmg-canvas: {CANVAS}; --bmg-surface: {SURFACE}; --bmg-muted: {MUTED};
            --bmg-success: {SUCCESS}; --bmg-warning: {WARNING}; --bmg-danger: {DANGER};
            --bmg-border: rgba(56,56,97,.12); --bmg-shadow: 0 12px 32px rgba(51,51,51,.065);
        }}
        html, body, [class*="css"], [data-testid="stAppViewContainer"] {{ font-family: 'Lato', sans-serif; color: var(--bmg-charcoal); }}
        h1, h2, h3, h4, h5, h6, .stMetric label {{ font-family: 'Montserrat', sans-serif !important; }}
        .stApp {{
            background: radial-gradient(circle at 92% -8%, rgba(32,149,154,.10), transparent 28rem),
                        radial-gradient(circle at 8% 102%, rgba(134,137,75,.07), transparent 25rem), var(--bmg-canvas);
        }}
        header[data-testid="stHeader"] {{ background: rgba(246,244,238,.88); backdrop-filter: blur(14px); border-bottom: 1px solid rgba(56,56,97,.07); }}
        .block-container {{ max-width: 1480px; padding: 1.35rem 2rem 3rem; }}

        div[data-testid="stSidebar"] {{ background: #FCFAF4; border-right: 1px solid var(--bmg-border); }}
        div[data-testid="stSidebarContent"] {{ padding-top: .4rem; }}
        div[data-testid="stSidebar"] [data-testid="stLogo"] {{
            height: 172px; margin: .25rem .55rem 1rem; padding: .65rem;
            border-radius: 18px; background: linear-gradient(145deg, #FFFEFA, #F0EEE5);
            border: 1px solid rgba(56,56,97,.13); box-shadow: 0 14px 32px rgba(56,56,97,.13);
            overflow: visible;
        }}
        div[data-testid="stSidebar"] [data-testid="stLogo"] img {{
            width: 100%; max-height: 158px; object-fit: contain; transform: scale(1.18);
            filter: drop-shadow(0 7px 10px rgba(51,51,51,.18));
        }}
        div[data-testid="stSidebarNav"] {{ padding-top: .15rem; }}
        div[data-testid="stSidebarNav"] a {{ border-radius: 10px; margin: 2px 8px; padding: .62rem .72rem; font-family: 'Montserrat', sans-serif; font-size: .84rem; font-weight: 500; color: #565A58; transition: background .15s ease, color .15s ease; }}
        div[data-testid="stSidebarNav"] a:hover {{ background: rgba(32,149,154,.08); color: var(--bmg-teal); }}
        div[data-testid="stSidebarNav"] a[aria-current="page"] {{ background: var(--bmg-indigo); color: white; box-shadow: 0 8px 20px rgba(56,56,97,.16); }}
        div[data-testid="stSidebar"] hr {{ border-color: var(--bmg-border); }}

        .bmg-hero {{ position: relative; overflow: hidden; padding: 1.45rem 1.55rem 1.35rem; border-radius: 18px; background: rgba(255,254,250,.86); border: 1px solid var(--bmg-border); box-shadow: var(--bmg-shadow); margin-bottom: 1.15rem; }}
        .bmg-hero:before {{ content: ""; position: absolute; inset: 0 auto 0 0; width: 4px; background: linear-gradient(180deg, var(--bmg-teal), var(--bmg-indigo)); }}
        .bmg-hero:after {{ content: ""; position: absolute; width: 210px; height: 210px; right: -85px; top: -115px; border-radius: 50%; background: rgba(32,149,154,.065); }}
        .bmg-eyebrow {{ color: var(--bmg-olive); font-family: 'Montserrat', sans-serif; font-size: .68rem; font-weight: 700; letter-spacing: .15em; text-transform: uppercase; }}
        .bmg-hero h1 {{ margin: .3rem 0 .35rem; max-width: 1050px; color: var(--bmg-charcoal); font-size: clamp(3rem, 4.5vw, 3.75rem); font-weight: 700; letter-spacing: .02em; line-height: 1.08; }}
        .bmg-hero p {{ max-width: 850px; margin: 0; color: var(--bmg-muted); font-size: .98rem; line-height: 1.55; }}
        .bmg-hero-meta {{ display: flex; gap: .42rem; flex-wrap: wrap; margin-top: .85rem; }}
        .bmg-hero-chip {{ padding: .25rem .52rem; border-radius: 999px; background: rgba(32,149,154,.07); border: 1px solid rgba(32,149,154,.14); color: #25777A; font-family: 'Montserrat', sans-serif; font-size: .65rem; font-weight: 600; }}

        .bm-panel, div[data-testid="stVerticalBlockBorderWrapper"] {{ background: rgba(255,254,250,.88); border: 1px solid var(--bmg-border); border-radius: 14px; box-shadow: var(--bmg-shadow); }}
        .bm-panel {{ padding: 1rem 1.1rem; }}
        .bm-card {{ background: rgba(255,254,250,.94); border: 1px solid var(--bmg-border); border-radius: 14px; padding: 1rem 1.05rem; min-height: 118px; box-shadow: var(--bmg-shadow); }}
        .bm-kicker {{ color: var(--bmg-olive); font-family: 'Montserrat', sans-serif; font-size: .66rem; font-weight: 700; text-transform: uppercase; letter-spacing: .14em; margin-bottom: .45rem; }}
        .bm-value {{ color: var(--bmg-charcoal); font-family: 'Montserrat', sans-serif; font-size: 1.65rem; font-weight: 700; line-height: 1.12; letter-spacing: -.03em; overflow-wrap: anywhere; }}
        .bm-caption {{ margin-top: .35rem; color: var(--bmg-muted); font-size: .82rem; line-height: 1.48; }}
        .bm-caption ul {{ margin: .2rem 0 0; padding-left: 1.05rem; }}
        .bm-caption li {{ margin: .24rem 0; }}
        .bm-score-pill {{ display: inline-block; padding: .22rem .5rem; border-radius: 999px; font-family: 'Montserrat', sans-serif; font-size: .67rem; font-weight: 700; margin-bottom: .55rem; background: rgba(56,56,97,.08); color: var(--bmg-indigo); }}
        .bm-score-pill.buy, .bm-score-pill.high {{ background: rgba(60,123,83,.12); color: var(--bmg-success); }}
        .bm-score-pill.watch, .bm-score-pill.warning {{ background: rgba(183,121,31,.12); color: var(--bmg-warning); }}
        .bm-score-pill.sell, .bm-score-pill.alert {{ background: rgba(184,74,58,.12); color: var(--bmg-danger); }}
        .bm-mono {{ font-family: ui-monospace, 'SFMono-Regular', Consolas, monospace; }}

        h2 {{ color: var(--bmg-charcoal); font-size: clamp(2rem, 3vw, 2.25rem) !important; letter-spacing: .04em; font-weight: 700; }}
        h3 {{ color: var(--bmg-indigo); font-size: 1.33rem !important; letter-spacing: .15em; text-transform: uppercase; font-weight: 700; }}
        p, li {{ color: var(--bmg-charcoal); }}
        small, .stCaptionContainer, [data-testid="stCaptionContainer"] {{ color: var(--bmg-olive) !important; font-size: .8rem !important; font-weight: 600; letter-spacing: .05em; }}
        div[data-testid="stMetric"] {{ background: rgba(255,254,250,.92); border: 1px solid var(--bmg-border); border-radius: 14px; padding: .85rem 1rem; box-shadow: var(--bmg-shadow); }}
        div[data-testid="stMetricLabel"] {{ color: var(--bmg-olive); letter-spacing: .08em; text-transform: uppercase; }}
        div[data-testid="stMetricValue"] {{ color: var(--bmg-charcoal); font-family: 'Montserrat', sans-serif; }}

        .stButton > button, .stDownloadButton > button, .stLinkButton > a {{ min-height: 2.65rem; border-radius: 9px; border: 1px solid rgba(56,56,97,.22); background: var(--bmg-surface); color: var(--bmg-indigo); font-family: 'Montserrat', sans-serif; font-weight: 700; letter-spacing: .02em; }}
        .stButton > button[kind="primary"] {{ background: var(--bmg-indigo); border-color: var(--bmg-indigo); color: white; box-shadow: 0 8px 18px rgba(56,56,97,.15); }}
        .stButton > button[kind="primary"]:hover {{ background: #2F2F55; border-color: #2F2F55; }}
        .stDownloadButton > button:hover, .stButton > button:not([kind="primary"]):hover, .stLinkButton > a:hover {{ background: rgba(32,149,154,.08); border-color: var(--bmg-teal); color: #176F73; }}
        .stButton > button:disabled, .stDownloadButton > button:disabled {{ background: #ECEAE3 !important; color: #626663 !important; border-color: rgba(51,51,51,.18) !important; opacity: .78; }}
        [data-testid="stPageLink"] a {{ min-height: 3rem; display: flex; align-items: center; justify-content: center; border-radius: 10px; background: var(--bmg-indigo); color: #FFFFFF !important; border: 1px solid var(--bmg-indigo); font-family: 'Montserrat', sans-serif; font-weight: 700; text-decoration: none; box-shadow: 0 8px 18px rgba(56,56,97,.15); }}
        [data-testid="stPageLink"] a:hover {{ background: #2F2F55; border-color: #2F2F55; color: #FFFFFF !important; }}
        div[data-baseweb="input"] > div, div[data-baseweb="select"] > div, textarea {{ background: rgba(255,254,250,.96) !important; border-color: var(--bmg-border) !important; border-radius: 9px !important; }}
        div[data-baseweb="input"]:focus-within > div, div[data-baseweb="select"]:focus-within > div {{ border-color: var(--bmg-teal) !important; box-shadow: 0 0 0 2px rgba(32,149,154,.10); }}
        label, [data-testid="stWidgetLabel"] p {{ color: var(--bmg-charcoal) !important; font-weight: 600; }}
        button[data-baseweb="tab"] {{ color: #555A57; font-family: 'Montserrat', sans-serif; font-size: .82rem; font-weight: 700; }}
        button[data-baseweb="tab"][aria-selected="true"] {{ color: #176F73 !important; }}

        div[data-testid="stDataFrame"] {{ border-radius: 12px; overflow: hidden; border: 1px solid var(--bmg-border); box-shadow: var(--bmg-shadow); }}
        div[data-testid="stExpander"] {{ background: rgba(255,254,250,.75); border: 1px solid var(--bmg-border); border-radius: 12px; }}
        div[data-testid="stAlert"] {{ border-radius: 11px; border-width: 1px; }}
        div[data-testid="stPlotlyChart"] {{ background: rgba(255,254,250,.75); border: 1px solid var(--bmg-border); border-radius: 14px; padding: .35rem; box-shadow: var(--bmg-shadow); }}
        @media (max-width: 900px) {{ .block-container {{ padding: 1rem .9rem 2rem; }} .bmg-hero {{ padding: 1.2rem 1.15rem; }} .bm-card {{ min-height: auto; }} }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    _require_dashboard_password()


def _require_dashboard_password() -> None:
    settings = get_settings()
    configured_password = settings.dashboard_password
    if not configured_password:
        if settings.app_env.lower() in {"production", "prod", "staging"}:
            st.error("DASHBOARD_PASSWORD must be configured before this dashboard can run.")
            st.stop()
        st.sidebar.warning("Development mode: dashboard password is not configured.")
        return
    if st.session_state.get("_dashboard_authenticated"):
        if st.sidebar.button("Lock dashboard", key="_lock_dashboard", width="stretch"):
            st.session_state["_dashboard_authenticated"] = False
            st.rerun()
        return

    hero("Private Workspace", "Enter the dashboard password to continue.", eyebrow="BAZAAR MIND GAMES")
    supplied = st.text_input("Dashboard Password", type="password", key="_dashboard_password_input")
    if st.button("Unlock Workspace", type="primary", key="_unlock_dashboard"):
        if hmac.compare_digest(supplied, configured_password):
            st.session_state["_dashboard_authenticated"] = True
            st.rerun()
        st.error("Incorrect password.")
    st.stop()


def hero(title: str, subtitle: str, eyebrow: str = "MARKET INTELLIGENCE", badges: list[str] | None = None) -> None:
    chips = "".join(f"<span class='bmg-hero-chip'>{escape(item)}</span>" for item in (badges or []))
    metadata = f"<div class='bmg-hero-meta'>{chips}</div>" if chips else ""
    st.markdown(
        f"<section class='bmg-hero'><div class='bmg-eyebrow'>{escape(eyebrow)}</div><h1>{escape(title)}</h1><p>{escape(subtitle)}</p>{metadata}</section>",
        unsafe_allow_html=True,
    )


def panel_start() -> None:
    st.markdown("<div class='bm-panel'>", unsafe_allow_html=True)


def panel_end() -> None:
    st.markdown("</div>", unsafe_allow_html=True)
