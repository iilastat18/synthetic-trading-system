from __future__ import annotations

import streamlit as st

from src.mm_system import (
    advance_mm_system,
    build_mm_system,
    hedge_region_inventory,
    hedge_symbol_inventory,
    hedge_books_frame,
    market_movers_frame,
    market_overview_history_frame,
    region_risk_frame,
    system_metrics,
)
from src.ui import apply_theme, fmt_money, fmt_money_precise


@st.cache_data
def load_snapshot() -> dict:
    state = build_mm_system(seed=29)
    for _ in range(8):
        state = advance_mm_system(state, shock_boost=0.10)
    hedge_symbol_inventory(state, "ALP_ETF")
    hedge_region_inventory(state, "US")
    return {
        "metrics": system_metrics(state),
        "movers": market_movers_frame(state),
        "market": market_overview_history_frame(state),
        "hedges": hedge_books_frame(state),
        "region": region_risk_frame(state),
        "events": state.events,
    }


st.set_page_config(
    page_title="Synthetic Market Maker Cover",
    page_icon=":desktop_computer:",
    layout="wide",
)
apply_theme("cover")
data = load_snapshot()
metrics = data["metrics"]
movers_df = data["movers"]
market_df = data["market"]
hedges_df = data["hedges"]
region_df = data["region"]
events_df = data["events"]
latest_market = market_df.groupby("region", as_index=False).tail(1).sort_values("market_index", ascending=False)

st.markdown(
    (
        "<div class='terminal-shell'>"
        "<div class='terminal-head'>"
        "<div>"
        "<div class='terminal-kicker'>Portfolio Project 04</div>"
        "<div class='terminal-title'>Synthetic Market Maker System</div>"
        "<div class='terminal-copy'>"
        "A public-safe trading front-end demo with synthetic market movement, live ISIN drift, regional hedge baskets, "
        "and trader workflows like manual hedge tickets and basket overrides."
        "</div>"
        "</div>"
        "<div class='terminal-ribbon'>"
        "<span class='status-chip'>Single-screen terminal</span>"
        "<span class='status-chip'>Synthetic market feed</span>"
        "<span class='status-chip'>ISIN change tape</span>"
        "<span class='status-chip'>Trader hedge controls</span>"
        "</div>"
        "</div>"
        "</div>"
    ),
    unsafe_allow_html=True,
)

metric_cols = st.columns(5)
metric_cols[0].metric("Gross Inventory", fmt_money(metrics["gross_inventory_usd"]))
metric_cols[1].metric("Net Beta", fmt_money_precise(metrics["net_inventory_usd"]))
metric_cols[2].metric("Hedge Notional", fmt_money(metrics["hedge_notional"]))
metric_cols[3].metric("Enabled Quotes", f"{int(metrics['enabled_quotes']):,}")
metric_cols[4].metric("Hard Errors", f"{int(metrics['hard_errors'])}")

left, right = st.columns([1.18, 0.82], gap="large")
with left:
    st.dataframe(
        latest_market.loc[:, ["region", "market_index", "avg_move_pct", "avg_spread_bps", "stressed_symbols"]].style.format(
            {
                "market_index": "{:.2f}",
                "avg_move_pct": "{:+.2f}%",
                "avg_spread_bps": "{:.2f}",
                "stressed_symbols": "{:,.0f}",
            }
        ),
        width="stretch",
        hide_index=True,
        height=180,
    )
    st.dataframe(
        movers_df.head(8).loc[:, ["symbol", "region", "mid", "last_move_pct", "spread_bps", "inventory_qty", "state"]].style.format(
            {
                "mid": "{:.2f}",
                "last_move_pct": "{:+.2f}%",
                "spread_bps": "{:.1f}",
                "inventory_qty": "{:,.0f}",
            }
        ),
        width="stretch",
        hide_index=True,
        height=260,
    )
with right:
    st.dataframe(hedges_df, width="stretch", hide_index=True, height=190)
    st.dataframe(region_df, width="stretch", hide_index=True, height=170)
    st.dataframe(events_df.head(6), width="stretch", hide_index=True, height=170)
