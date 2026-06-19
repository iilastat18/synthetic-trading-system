from __future__ import annotations

import pandas as pd
import streamlit as st


DESK_CSS = """
<style>
    :root {
        --bg: #0a1118;
        --bg-2: #0d151e;
        --panel: rgba(13, 21, 30, 0.96);
        --panel-strong: rgba(10, 17, 24, 0.98);
        --line: rgba(114, 133, 152, 0.18);
        --line-strong: rgba(114, 133, 152, 0.28);
        --text: #edf3f8;
        --muted: #90a2b4;
        --accent: #31c48d;
        --accent-2: #59a9ff;
        --warn: #f5b14c;
        --danger: #f16c6c;
        --success-soft: rgba(49, 196, 141, 0.12);
        --danger-soft: rgba(241, 108, 108, 0.12);
        --warn-soft: rgba(245, 177, 76, 0.12);
    }
    .stApp {
        color: var(--text);
        background:
            radial-gradient(circle at top left, rgba(89, 169, 255, 0.09), transparent 22%),
            linear-gradient(180deg, var(--bg) 0%, var(--bg-2) 100%);
    }
    #MainMenu,
    header[data-testid="stHeader"],
    [data-testid="stSidebarNav"] {
        display: none;
    }
    [data-testid="stAppViewContainer"] {
        background: transparent;
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(8, 15, 22, 0.98), rgba(10, 17, 24, 0.96));
        border-right: 1px solid var(--line);
    }
    [data-testid="stSidebar"] * {
        color: var(--text);
    }
    .block-container {
        max-width: 1480px;
        padding-top: 0.6rem;
        padding-bottom: 2.2rem;
    }
    .terminal-shell {
        border: 1px solid var(--line-strong);
        border-radius: 14px;
        background: linear-gradient(180deg, rgba(9, 16, 23, 0.99), rgba(10, 17, 24, 0.99));
        box-shadow: 0 14px 34px rgba(0, 0, 0, 0.28);
        padding: 0.9rem 1rem 0.8rem;
        margin-bottom: 0.8rem;
    }
    .terminal-head {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: flex-start;
        padding-bottom: 0.8rem;
        border-bottom: 1px solid var(--line);
        margin-bottom: 0.8rem;
    }
    .terminal-kicker {
        color: #7ec3ff;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-size: 0.7rem;
        margin-bottom: 0.2rem;
    }
    .terminal-title {
        font-size: 1.58rem;
        line-height: 1.05;
        font-weight: 800;
        color: var(--text);
        margin-bottom: 0.24rem;
    }
    .terminal-copy {
        color: var(--muted);
        font-size: 0.84rem;
        line-height: 1.55;
        max-width: 58rem;
    }
    .terminal-ribbon {
        display: flex;
        flex-wrap: wrap;
        gap: 0.45rem;
        justify-content: flex-end;
        max-width: 34rem;
    }
    .status-chip {
        padding: 0.24rem 0.52rem;
        border-radius: 999px;
        border: 1px solid var(--line);
        background: rgba(255, 255, 255, 0.03);
        color: #d8e4ef;
        font-size: 0.72rem;
        font-weight: 700;
        white-space: nowrap;
    }
    .status-chip-positive {
        color: #8ceacc;
        border-color: rgba(49, 196, 141, 0.24);
        background: rgba(49, 196, 141, 0.09);
    }
    .status-chip-negative {
        color: #ffb4b4;
        border-color: rgba(241, 108, 108, 0.24);
        background: rgba(241, 108, 108, 0.09);
    }
    .surface-tight {
        margin-bottom: 0.55rem;
    }
    .panel-footnote {
        color: var(--muted);
        font-size: 0.76rem;
        line-height: 1.45;
        margin-top: 0.45rem;
    }
    .symbol-strip {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.45rem;
        margin-bottom: 0.6rem;
    }
    .hero {
        position: relative;
        overflow: hidden;
        border: 1px solid var(--line-strong);
        border-radius: 16px;
        background: linear-gradient(180deg, rgba(13, 22, 31, 0.98), rgba(10, 17, 24, 0.98));
        box-shadow: 0 10px 28px rgba(0, 0, 0, 0.24);
        padding: 1.15rem 1.2rem;
        margin-bottom: 0.8rem;
    }
    .hero::after {
        content: "";
        position: absolute;
        top: -30%;
        right: -8%;
        width: 220px;
        height: 220px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(89,169,255,0.12), transparent 70%);
        pointer-events: none;
    }
    .hero-kicker {
        text-transform: uppercase;
        letter-spacing: 0.10em;
        font-size: 0.72rem;
        color: #7ec3ff;
        margin-bottom: 0.35rem;
    }
    .hero-title {
        font-size: 2.05rem;
        line-height: 1.04;
        font-weight: 820;
        color: var(--text);
        margin-bottom: 0.35rem;
    }
    .hero-copy {
        color: var(--muted);
        font-size: 0.92rem;
        line-height: 1.58;
        max-width: 64rem;
    }
    .hero-pills {
        margin-top: 0.7rem;
    }
    .pill {
        display: inline-block;
        margin: 0 0.35rem 0.35rem 0;
        padding: 0.24rem 0.58rem;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(114, 133, 152, 0.16);
        color: #d7e2ee;
        font-size: 0.74rem;
        font-weight: 700;
    }
    .surface {
        border: 1px solid var(--line);
        border-radius: 12px;
        background: linear-gradient(180deg, rgba(13, 21, 30, 0.98), rgba(11, 18, 25, 0.98));
        padding: 0.8rem 0.82rem 0.82rem;
        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.20);
        margin-bottom: 0.8rem;
    }
    .surface-label {
        display: inline-block;
        margin-bottom: 0.35rem;
        padding: 0.18rem 0.44rem;
        border-radius: 999px;
        background: rgba(89, 169, 255, 0.10);
        color: #92c8ff;
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }
    .panel-title {
        font-size: 1rem;
        font-weight: 760;
        color: var(--text);
        margin-top: 0.05rem;
        margin-bottom: 0.16rem;
    }
    .panel-copy {
        color: var(--muted);
        margin-bottom: 0.55rem;
        font-size: 0.86rem;
    }
    .summary-banner {
        border: 1px solid var(--line);
        border-radius: 10px;
        background: linear-gradient(135deg, rgba(14, 24, 33, 0.98), rgba(11, 18, 25, 0.98));
        padding: 0.7rem 0.8rem;
        margin-bottom: 0.75rem;
    }
    .summary-grid,
    .inspector-grid,
    .mini-stat-grid,
    .desk-subgrid {
        display: grid;
        gap: 0.55rem;
    }
    .summary-grid {
        grid-template-columns: repeat(4, minmax(0, 1fr));
    }
    .inspector-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
        margin-top: 0.18rem;
    }
    .mini-stat-grid {
        grid-template-columns: repeat(3, minmax(0, 1fr));
    }
    .desk-subgrid {
        grid-template-columns: repeat(4, minmax(0, 1fr));
        margin-bottom: 0.55rem;
    }
    .summary-cell,
    .inspector-card,
    .mini-stat,
    .desk-stat {
        border-radius: 10px;
        border: 1px solid var(--line);
        background: rgba(255, 255, 255, 0.025);
        padding: 0.56rem 0.62rem;
    }
    .summary-label,
    .inspector-kicker,
    .mini-stat-label,
    .desk-stat-label {
        color: var(--muted);
        font-size: 0.68rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.14rem;
    }
    .summary-value,
    .inspector-value,
    .mini-stat-value,
    .desk-stat-value {
        color: var(--text);
        font-size: 0.94rem;
        font-weight: 760;
    }
    .menu-strip {
        display: flex;
        gap: 1rem;
        align-items: center;
        padding: 0.2rem 0.15rem 0.35rem;
        color: var(--muted);
        font-size: 0.78rem;
        letter-spacing: 0.02em;
    }
    .workbench-tabs {
        display: flex;
        flex-wrap: wrap;
        gap: 0.4rem;
        margin-bottom: 0.8rem;
    }
    .workbench-tab {
        padding: 0.35rem 0.68rem;
        border-radius: 8px 8px 0 0;
        border: 1px solid var(--line);
        border-bottom: none;
        background: rgba(255, 255, 255, 0.04);
        color: #b8cade;
        font-size: 0.78rem;
        font-weight: 700;
    }
    .workbench-tab-active {
        background: linear-gradient(180deg, rgba(89,169,255,0.20), rgba(18, 30, 42, 0.98));
        color: white;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);
    }
    .command-strip {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: center;
        padding: 0.55rem 0.75rem;
        border: 1px solid var(--line);
        border-radius: 10px;
        background: linear-gradient(180deg, rgba(14, 23, 32, 0.98), rgba(11, 18, 25, 0.98));
        margin-bottom: 0.8rem;
    }
    .command-title {
        color: var(--text);
        font-size: 0.96rem;
        font-weight: 760;
        margin-bottom: 0.08rem;
    }
    .command-copy {
        color: var(--muted);
        font-size: 0.82rem;
    }
    .cover-grid {
        display: grid;
        grid-template-columns: 1.35fr 0.95fr;
        gap: 1rem;
        margin-bottom: 1rem;
    }
    .cover-card {
        border: 1px solid var(--line);
        border-radius: 14px;
        background: linear-gradient(180deg, rgba(11, 20, 29, 0.98), rgba(9, 16, 23, 0.98));
        padding: 1rem 1rem 0.9rem;
        box-shadow: 0 10px 24px rgba(0, 0, 0, 0.20);
    }
    .cover-title {
        font-size: 2.2rem;
        line-height: 1.0;
        font-weight: 840;
        color: var(--text);
        margin-bottom: 0.5rem;
    }
    .cover-copy,
    .cover-list,
    .dense-caption,
    .desk-note {
        color: var(--muted);
        font-size: 0.84rem;
        line-height: 1.62;
    }
    .cover-copy {
        max-width: 48rem;
        margin-bottom: 0.8rem;
    }
    .cover-list {
        margin: 0;
        padding-left: 1.1rem;
    }
    .cover-list li {
        margin-bottom: 0.12rem;
    }
    .note-band {
        border: 1px solid rgba(245, 177, 76, 0.18);
        border-radius: 10px;
        background: linear-gradient(135deg, rgba(245,177,76,0.08), rgba(89,169,255,0.06));
        padding: 0.68rem 0.75rem;
        color: #dbe7f4;
    }
    .severity-pill {
        display: inline-block;
        padding: 0.24rem 0.54rem;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 700;
        margin-right: 0.28rem;
        margin-bottom: 0.28rem;
        border: 1px solid var(--line);
        background: rgba(255, 255, 255, 0.03);
        color: #d4e2f1;
    }
    .severity-critical {
        background: rgba(241, 108, 108, 0.14);
        border-color: rgba(241, 108, 108, 0.22);
        color: #ffb4b4;
    }
    .severity-warn {
        background: rgba(245, 177, 76, 0.14);
        border-color: rgba(245, 177, 76, 0.22);
        color: #ffd394;
    }
    .severity-ok {
        background: rgba(49, 196, 141, 0.12);
        border-color: rgba(49, 196, 141, 0.20);
        color: #8ceacc;
    }
    .desk-note {
        border: 1px dashed var(--line);
        border-radius: 10px;
        padding: 0.55rem 0.62rem;
        background: rgba(255, 255, 255, 0.02);
        margin-top: 0.4rem;
    }
    .desk-divider {
        height: 1px;
        background: var(--line);
        margin: 0.55rem 0 0.7rem;
    }
    .empty-shell {
        border: 1px dashed rgba(114, 133, 152, 0.24);
        border-radius: 10px;
        background: rgba(255, 255, 255, 0.02);
        padding: 0.9rem;
        color: var(--muted);
    }
    div[data-testid="stMetric"] {
        border: 1px solid var(--line);
        border-radius: 10px;
        background: linear-gradient(180deg, rgba(14, 23, 32, 0.98), rgba(11, 18, 25, 0.98));
        padding: 0.6rem 0.72rem;
    }
    div[data-testid="stMetricLabel"] * {
        color: var(--muted);
    }
    div[data-testid="stMetricValue"] * {
        color: var(--text);
    }
    div[data-testid="stMetricDelta"] * {
        color: #8ad9ff;
    }
    div[data-testid="stDataFrame"],
    [data-testid="stDataEditor"] {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid var(--line);
    }
    [data-testid="stDataEditor"] * {
        color: var(--text);
    }
    div[data-testid="stTabs"] button {
        border-radius: 999px;
        background: transparent;
        color: var(--muted);
    }
    div[role="tablist"] {
        gap: 0.3rem;
    }
    div[data-baseweb="select"] > div,
    div[data-baseweb="input"] > div,
    div[data-baseweb="base-input"] > div,
    .stNumberInput > div > div,
    .stTextInput > div > div,
    .stTextArea textarea {
        background: rgba(255, 255, 255, 0.03);
        border-color: rgba(114, 133, 152, 0.18);
        color: var(--text);
    }
    .stButton > button {
        border-radius: 8px;
        border: 1px solid rgba(114, 133, 152, 0.18);
        min-height: 2.35rem;
        font-weight: 720;
        background: linear-gradient(180deg, rgba(18, 31, 43, 0.98), rgba(13, 23, 33, 0.98));
        color: var(--text);
    }
    .stButton > button:hover {
        border-color: rgba(49, 196, 141, 0.34);
        color: white;
    }
    .stRadio [role="radiogroup"] label,
    .stRadio [role="radiogroup"] div,
    .stCaption,
    .stMarkdown p,
    .stMarkdown li {
        color: var(--muted);
    }
    @media (max-width: 980px) {
        .terminal-head,
        .cover-grid,
        .summary-grid,
        .inspector-grid,
        .mini-stat-grid,
        .desk-subgrid,
        .symbol-strip {
            display: block;
        }
        .terminal-ribbon {
            justify-content: flex-start;
            margin-top: 0.65rem;
        }
        .desk-subgrid {
            grid-template-columns: 1fr;
        }
        .hero-title,
        .cover-title {
            font-size: 1.8rem;
        }
    }
</style>
"""


def apply_theme(mode: str = "desk") -> None:
    st.markdown(DESK_CSS, unsafe_allow_html=True)
    if mode == "cover":
        st.markdown(
            """
            <style>
                .block-container {
                    max-width: 1420px;
                    padding-top: 1rem;
                }
            </style>
            """,
            unsafe_allow_html=True,
        )


def fmt_money(value: float) -> str:
    return f"${value:,.0f}"


def fmt_money_precise(value: float) -> str:
    return f"${value:,.2f}"


def fmt_change(value: float) -> str:
    return f"{value:+.2f}%"


def classify_regime(market_df: pd.DataFrame) -> tuple[str, str]:
    avg_move = float(market_df.loc[~market_df["is_hedge"], "day_change_pct"].abs().mean())
    avg_spread = float(market_df.loc[~market_df["is_hedge"], "spread_bps"].mean())
    if avg_move >= 2.0 or avg_spread >= 15:
        return "High Volatility", "Spreads are wider and cross-book dispersion is elevated."
    if avg_move >= 1.0 or avg_spread >= 11:
        return "Active Session", "Synthetic book is rotating with enough movement to make fast hedging useful."
    return "Balanced Session", "Conditions are relatively orderly with tighter spreads and smoother rotation."


def render_surface_header(title: str, copy: str, label: str | None = None) -> None:
    st.markdown("<div class='surface'>", unsafe_allow_html=True)
    if label:
        st.markdown(f"<div class='surface-label'>{label}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='panel-title'>{title}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='panel-copy'>{copy}</div>", unsafe_allow_html=True)


def close_surface() -> None:
    st.markdown("</div>", unsafe_allow_html=True)
