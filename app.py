from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from src.mm_system import (
    MMSystemState,
    advance_mm_system,
    build_mm_system,
    clear_region_hedge_override,
    clear_symbol_hedge_override,
    flatten_region_hedge,
    hedge_blotter_frame,
    hedge_books_frame,
    hedge_region_inventory,
    hedge_symbol_inventory,
    isin_history_frame,
    manual_hedge_ticket,
    market_movers_frame,
    market_overview_history_frame,
    region_hedge_choices,
    region_risk_frame,
    risk_book_frame,
    set_region_hedge_override,
    set_symbol_hedge_override,
    system_metrics,
    touch_monitor_frame,
)
from src.ui import apply_theme, close_surface, fmt_change, fmt_money, fmt_money_precise, render_surface_header


st.set_page_config(
    page_title="Synthetic Market Maker System",
    page_icon=":desktop_computer:",
    layout="wide",
)
apply_theme("desk")

REGION_COLORS = ["#59A9FF", "#31C48D", "#F5B14C"]


def init_system(seed: int = 19) -> None:
    st.session_state.mm_system = build_mm_system(seed=seed)
    st.session_state.live_refresh_seen = -1
    st.session_state.system_message = ("info", "Synthetic market-maker system initialised.")


def chart_theme(chart: alt.Chart) -> alt.Chart:
    return (
        chart.configure_view(strokeOpacity=0)
        .configure_axis(
            labelColor="#90a2b4",
            titleColor="#90a2b4",
            gridColor="rgba(114, 133, 152, 0.14)",
            domainColor="rgba(114, 133, 152, 0.22)",
            tickColor="rgba(114, 133, 152, 0.22)",
        )
        .configure_legend(
            labelColor="#d7e2ee",
            titleColor="#90a2b4",
            orient="top-left",
        )
    )


def selected_symbol_row(system: MMSystemState, symbol: str) -> pd.Series:
    return system.touch.loc[system.touch["symbol"] == symbol].iloc[0]


def render_terminal_header(system: MMSystemState, selected_row: pd.Series, auto_live: bool, refresh_ms: int) -> None:
    move_value = float(selected_row["last_move_pct"])
    move_class = "status-chip-positive" if move_value >= 0 else "status-chip-negative"
    clock_hour = 9 + system.cycle // 180
    clock_minute = 30 + (system.cycle // 30) % 60
    clock_second = (system.cycle * 2) % 60
    st.markdown(
        (
            "<div class='terminal-shell'>"
            "<div class='terminal-head'>"
            "<div>"
            "<div class='terminal-kicker'>Synthetic Market Maker Terminal</div>"
            f"<div class='terminal-title'>{selected_row['symbol']} · {selected_row['region']} Book</div>"
            "<div class='terminal-copy'>"
            "Single-screen trader view with synthetic market movement, live ISIN drift, regional hedge baskets, "
            "manual hedge tickets, and basket override controls. Everything here is synthetic and public-safe."
            "</div>"
            "</div>"
            "<div class='terminal-ribbon'>"
            f"<span class='status-chip'>{'Live feed ON' if auto_live else 'Live feed OFF'}</span>"
            f"<span class='status-chip'>Cycle {system.cycle}</span>"
            f"<span class='status-chip'>Clock {clock_hour:02d}:{clock_minute:02d}:{clock_second:02d}</span>"
            f"<span class='status-chip'>Refresh {refresh_ms} ms</span>"
            f"<span class='status-chip {move_class}'>{selected_row['symbol']} {fmt_change(move_value)}</span>"
            f"<span class='status-chip'>Basket {selected_row['hedge_symbol']}</span>"
            "</div>"
            "</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_market_chart(market_history: pd.DataFrame) -> None:
    if market_history.empty:
        st.markdown("<div class='empty-shell'>Waiting for market history...</div>", unsafe_allow_html=True)
        return

    chart = (
        alt.Chart(market_history)
        .mark_line(interpolate="monotone", strokeWidth=2.4)
        .encode(
            x=alt.X("cycle:Q", title="Cycle"),
            y=alt.Y("market_index:Q", title="Synthetic market index", scale=alt.Scale(zero=False)),
            color=alt.Color(
                "region:N",
                scale=alt.Scale(domain=["Europe", "US", "Asia"], range=REGION_COLORS),
                legend=alt.Legend(title="Region"),
            ),
            tooltip=[
                alt.Tooltip("time:N", title="Time"),
                alt.Tooltip("region:N", title="Region"),
                alt.Tooltip("market_index:Q", title="Index", format=".2f"),
                alt.Tooltip("avg_move_pct:Q", title="Avg move %", format=".2f"),
                alt.Tooltip("avg_spread_bps:Q", title="Spread bps", format=".2f"),
                alt.Tooltip("stressed_symbols:Q", title="Stressed"),
            ],
        )
        .properties(height=300)
    )
    st.altair_chart(chart_theme(chart), use_container_width=True)


def render_symbol_history_chart(history: pd.DataFrame) -> None:
    if history.empty:
        st.markdown("<div class='empty-shell'>Waiting for ISIN history...</div>", unsafe_allow_html=True)
        return

    price_chart = (
        alt.Chart(history)
        .mark_line(color="#59A9FF", strokeWidth=2.4, interpolate="monotone")
        .encode(
            x=alt.X("cycle:Q", title=None),
            y=alt.Y("mid:Q", title="Mid", scale=alt.Scale(zero=False)),
            tooltip=[
                alt.Tooltip("time:N", title="Time"),
                alt.Tooltip("mid:Q", title="Mid", format=".2f"),
                alt.Tooltip("last_move_pct:Q", title="Move %", format=".2f"),
                alt.Tooltip("spread_bps:Q", title="Spread bps", format=".1f"),
            ],
        )
        .properties(height=200)
    )
    inventory_chart = (
        alt.Chart(history)
        .mark_bar(size=10)
        .encode(
            x=alt.X("cycle:Q", title="Cycle"),
            y=alt.Y("inventory_qty:Q", title="Inventory"),
            color=alt.condition(alt.datum.inventory_qty >= 0, alt.value("#31C48D"), alt.value("#F16C6C")),
            tooltip=[
                alt.Tooltip("time:N", title="Time"),
                alt.Tooltip("inventory_qty:Q", title="Inventory", format=".0f"),
                alt.Tooltip("beta_exposure:Q", title="Beta", format=".2f"),
                alt.Tooltip("state:N", title="State"),
            ],
        )
        .properties(height=110)
    )
    st.altair_chart(chart_theme(alt.vconcat(price_chart, inventory_chart).resolve_scale(x="shared")), use_container_width=True)


if "mm_system" not in st.session_state:
    init_system()

system: MMSystemState = st.session_state.mm_system

control_cols = st.columns([0.85, 1.15, 0.9, 0.9, 0.9, 0.95, 1.0])
with control_cols[0]:
    auto_live = st.toggle("Live Feed", value=True, key="terminal_live_feed")
with control_cols[1]:
    refresh_ms = st.slider("Refresh (ms)", min_value=900, max_value=3500, value=1400, step=100, key="terminal_refresh_ms")
with control_cols[2]:
    step_market = st.button("Step Market", width="stretch")
with control_cols[3]:
    pulse_market = st.button("Pulse Vol", width="stretch")
with control_cols[4]:
    stabilize_market = st.button("Stabilize", width="stretch")
with control_cols[5]:
    reset_seed = st.number_input("Seed", min_value=1, max_value=9999, value=int(system.seed), step=1)
with control_cols[6]:
    regenerate_system = st.button("Regenerate", width="stretch")

refresh_count = None
if auto_live:
    refresh_count = st_autorefresh(interval=refresh_ms, key="mm_live_refresh")

if regenerate_system:
    init_system(seed=int(reset_seed))
    st.rerun()

system = st.session_state.mm_system
if auto_live and refresh_count is not None and refresh_count != st.session_state.get("live_refresh_seen", -1):
    st.session_state.mm_system = advance_mm_system(system, shock_boost=0.0)
    st.session_state.live_refresh_seen = refresh_count
    system = st.session_state.mm_system
elif step_market:
    st.session_state.mm_system = advance_mm_system(system, shock_boost=0.0)
    st.session_state.system_message = ("info", "Stepped the synthetic market by one cycle.")
    st.rerun()
elif pulse_market:
    st.session_state.mm_system = advance_mm_system(system, shock_boost=0.30)
    st.session_state.system_message = ("warning", "Injected a volatility pulse into the synthetic market.")
    st.rerun()
elif stabilize_market:
    st.session_state.mm_system = advance_mm_system(system, shock_boost=-0.12)
    st.session_state.system_message = ("success", "Applied a calmer pass across the synthetic book.")
    st.rerun()

system = st.session_state.mm_system
symbols = system.touch["symbol"].tolist()
if "selected_symbol" not in st.session_state and symbols:
    st.session_state.selected_symbol = symbols[0]
selected_symbol = st.session_state.selected_symbol
selected_row = selected_symbol_row(system, selected_symbol)

metrics = system_metrics(system)
touch_df = touch_monitor_frame(system)
risk_df = risk_book_frame(system)
region_df = region_risk_frame(system)
hedge_df = hedge_books_frame(system)
blotter_df = hedge_blotter_frame(system)
events_df = system.events.copy()
movers_df = market_movers_frame(system)
market_history = market_overview_history_frame(system)
selected_history = isin_history_frame(system, selected_symbol)
message_level, message_text = st.session_state.get("system_message", ("info", "Synthetic market feed ready."))

render_terminal_header(system, selected_row, auto_live=auto_live, refresh_ms=refresh_ms)

if message_level == "success":
    st.success(message_text)
elif message_level == "warning":
    st.warning(message_text)
else:
    st.info(message_text)

metric_cols = st.columns(6)
metric_cols[0].metric("Gross Inventory", fmt_money(metrics["gross_inventory_usd"]))
metric_cols[1].metric("Net Beta", fmt_money_precise(metrics["net_inventory_usd"]))
metric_cols[2].metric("Hedge Notional", fmt_money(metrics["hedge_notional"]))
metric_cols[3].metric("Hard Errors", f"{int(metrics['hard_errors'])}")
metric_cols[4].metric("Enabled Quotes", f"{int(metrics['enabled_quotes']):,}")
metric_cols[5].metric("Selected Move", fmt_change(float(selected_row["last_move_pct"])))

left_col, right_col = st.columns([1.3, 0.92], gap="large")

with left_col:
    render_surface_header(
        "Market Moving",
        "Cross-book movement by region. This is the synthetic market pulse driving everything else on the terminal.",
        label="Market",
    )
    market_filter = st.multiselect(
        "Region",
        options=["Europe", "US", "Asia"],
        default=["Europe", "US", "Asia"],
        key="market_region_filter",
    )
    market_view = market_history.loc[market_history["region"].isin(market_filter)] if market_filter else market_history.iloc[0:0]
    render_market_chart(market_view)
    movers_view = movers_df.head(6).loc[
        :,
        ["symbol", "region", "mid", "last_move_pct", "spread_bps", "inventory_qty", "state"],
    ]
    st.dataframe(
        movers_view.style.format(
            {
                "mid": "{:.2f}",
                "last_move_pct": "{:+.2f}%",
                "spread_bps": "{:.1f}",
                "inventory_qty": "{:,.0f}",
            }
        ),
        width="stretch",
        hide_index=True,
        height=230,
    )
    st.markdown(
        "<div class='panel-footnote'>Top movers are ranked by absolute last move, so the tape always surfaces the most active names first.</div>",
        unsafe_allow_html=True,
    )
    close_surface()

    render_surface_header(
        "ISIN Changes",
        "Selected symbol history with live price drift, inventory swings, and quote-state changes over recent cycles.",
        label="ISIN",
    )
    st.markdown(
        (
            "<div class='symbol-strip'>"
            f"<div class='desk-stat'><div class='desk-stat-label'>ISIN</div><div class='desk-stat-value'>{selected_row['isin']}</div></div>"
            f"<div class='desk-stat'><div class='desk-stat-label'>Venue</div><div class='desk-stat-value'>{selected_row['venue']}</div></div>"
            f"<div class='desk-stat'><div class='desk-stat-label'>Bid / Ask</div><div class='desk-stat-value'>{selected_row['bid']:.2f} / {selected_row['ask']:.2f}</div></div>"
            f"<div class='desk-stat'><div class='desk-stat-label'>Mapped Hedge</div><div class='desk-stat-value'>{selected_row['hedge_symbol']}</div></div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )
    render_symbol_history_chart(selected_history)
    change_tape = selected_history.loc[
        :,
        ["time", "mid", "last_move_pct", "spread_bps", "inventory_qty", "beta_exposure", "state"],
    ].tail(10)
    change_tape = change_tape.sort_values("time", ascending=False)
    st.dataframe(
        change_tape.style.format(
            {
                "mid": "{:.2f}",
                "last_move_pct": "{:+.2f}%",
                "spread_bps": "{:.1f}",
                "inventory_qty": "{:,.0f}",
                "beta_exposure": "{:,.2f}",
            }
        ),
        width="stretch",
        hide_index=True,
        height=250,
    )
    close_surface()

with right_col:
    render_surface_header(
        "Trader Console",
        "Focus a symbol, inspect its inventory build-up, and hedge or override the basket mapping without leaving the front-end.",
        label="Trader",
    )
    symbol_lookup = {
        row.symbol: f"{row.symbol} · {row.isin} · {row.region}"
        for row in system.touch.loc[:, ["symbol", "isin", "region"]].itertuples(index=False)
    }
    selected_symbol = st.selectbox(
        "Focus Symbol",
        symbols,
        key="selected_symbol",
        format_func=lambda symbol: symbol_lookup.get(symbol, symbol),
    )
    selected_row = selected_symbol_row(system, selected_symbol)
    selected_region = str(selected_row["region"])
    selected_hedge = str(selected_row["hedge_symbol"])
    selected_region_hedges = region_hedge_choices(system, selected_region)
    selected_hedge_row = system.hedges.loc[system.hedges["symbol"] == selected_hedge].iloc[0]
    manual_default_index = selected_region_hedges.index(selected_hedge) if selected_hedge in selected_region_hedges else 0

    st.markdown(
        (
            "<div class='desk-subgrid'>"
            f"<div class='desk-stat'><div class='desk-stat-label'>State</div><div class='desk-stat-value'>{selected_row['state']}</div></div>"
            f"<div class='desk-stat'><div class='desk-stat-label'>Inventory</div><div class='desk-stat-value'>{int(selected_row['inventory_qty']):,}</div></div>"
            f"<div class='desk-stat'><div class='desk-stat-label'>Beta</div><div class='desk-stat-value'>{fmt_money_precise(float(selected_row['beta_exposure']))}</div></div>"
            f"<div class='desk-stat'><div class='desk-stat-label'>Coverage</div><div class='desk-stat-value'>{float(selected_row['coverage_pct']):.2f}</div></div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )
    button_cols = st.columns(3)
    with button_cols[0]:
        if st.button("Hedge Selected", width="stretch"):
            result = hedge_symbol_inventory(system, selected_symbol)
            st.session_state.system_message = ("success" if "Hedged" in result else "info", result)
            st.rerun()
    with button_cols[1]:
        if st.button("Hedge Region", width="stretch"):
            result = hedge_region_inventory(system, selected_region, hedge_symbol=selected_hedge)
            st.session_state.system_message = ("success" if "Hedged" in result else "info", result)
            st.rerun()
    with button_cols[2]:
        if st.button("Flatten Hedge", width="stretch"):
            result = flatten_region_hedge(system, selected_region, hedge_symbol=selected_hedge)
            st.session_state.system_message = ("warning" if "Flattened" in result else "info", result)
            st.rerun()

    st.caption(
        f"Current basket position: {selected_hedge} {int(selected_hedge_row['quantity'])} @ {float(selected_hedge_row['last_price']):.2f}."
    )

    with st.form("manual_hedge_ticket_form", border=False):
        ticket_cols = st.columns([1.08, 0.78, 0.8])
        with ticket_cols[0]:
            manual_basket = st.selectbox("Manual Basket", selected_region_hedges, index=manual_default_index)
        with ticket_cols[1]:
            manual_side = st.selectbox("Side", ["BUY", "SELL"])
        with ticket_cols[2]:
            manual_qty = st.number_input(
                "Quantity",
                min_value=1,
                max_value=250000,
                value=max(int(selected_row["suggested_hedge_qty"]), 1),
                step=25,
            )
        manual_reason = st.text_input("Reason", value=f"Inventory rebalance for {selected_symbol}")
        submit_manual = st.form_submit_button("Send Manual Hedge", width="stretch")
    if submit_manual:
        result = manual_hedge_ticket(
            system,
            hedge_symbol=manual_basket,
            side=manual_side,
            quantity=int(manual_qty),
            reason=manual_reason.strip() or "Manual hedge",
            source_symbol=selected_symbol,
            region=selected_region,
        )
        st.session_state.system_message = ("success" if "Manual hedge sent" in result else "info", result)
        st.rerun()

    with st.form("basket_override_form", border=False):
        override_cols = st.columns([1.0, 1.0])
        with override_cols[0]:
            override_scope = st.radio("Override Scope", ["Selected Symbol", "Selected Region"], horizontal=True)
        with override_cols[1]:
            override_basket = st.selectbox("Override Basket", selected_region_hedges, index=manual_default_index)
        action_cols = st.columns(2)
        with action_cols[0]:
            apply_override = st.form_submit_button("Apply Override", width="stretch")
        with action_cols[1]:
            clear_override = st.form_submit_button("Clear Override", width="stretch")
    if apply_override:
        if override_scope == "Selected Symbol":
            result = set_symbol_hedge_override(system, symbol=selected_symbol, hedge_symbol=override_basket)
        else:
            result = set_region_hedge_override(system, region=selected_region, hedge_symbol=override_basket)
        st.session_state.system_message = ("success" if "Applied" in result else "info", result)
        st.rerun()
    if clear_override:
        if override_scope == "Selected Symbol":
            result = clear_symbol_hedge_override(system, symbol=selected_symbol)
        else:
            result = clear_region_hedge_override(system, region=selected_region)
        st.session_state.system_message = ("warning" if "Cleared" in result else "info", result)
        st.rerun()
    close_surface()

    render_surface_header(
        "Regional Risk",
        "Inventory and basket exposure side by side, so the trader can judge whether the book is actually covered.",
        label="Risk",
    )
    st.dataframe(
        region_df.style.format(
            {
                "gross_inventory": "{:,.2f}",
                "beta_net": "{:,.2f}",
                "hedge_notional": "{:,.2f}",
                "post_hedge_net": "{:,.2f}",
                "coverage_pct": "{:.2f}",
            }
        ),
        width="stretch",
        hide_index=True,
        height=190,
    )
    st.dataframe(
        hedge_df.style.format(
            {
                "last_price": "{:.2f}",
                "avg_cost": "{:.2f}",
                "market_value": "{:,.2f}",
                "unrealized_pnl": "{:,.2f}",
                "realized_pnl": "{:,.2f}",
            }
        ),
        width="stretch",
        hide_index=True,
        height=220,
    )
    close_surface()

    render_surface_header(
        "Action Feed",
        "Manual tickets, one-click hedges, and system alerts stay visible while the market keeps moving.",
        label="Feed",
    )
    st.dataframe(blotter_df.head(8), width="stretch", hide_index=True, height=180)
    st.dataframe(events_df.head(8), width="stretch", hide_index=True, height=190)
    close_surface()

render_surface_header(
    "Live ISIN Board",
    "Dense board view for the whole synthetic book. This keeps the app reading like a front-end system instead of a static mock.",
    label="Board",
)
board_cols = st.columns([1.22, 0.78], gap="large")
with board_cols[0]:
    board_view = touch_df.sort_values(["last_move_pct", "quote_age_ms"], ascending=[False, False]).loc[
        :,
        [
            "symbol",
            "isin",
            "region",
            "venue",
            "bid",
            "ask",
            "last_move_pct",
            "spread_bps",
            "quote_age_ms",
            "inventory_qty",
            "coverage_pct",
            "state",
            "hedge_symbol",
        ],
    ]
    st.dataframe(
        board_view.style.format(
            {
                "bid": "{:.2f}",
                "ask": "{:.2f}",
                "last_move_pct": "{:+.2f}%",
                "spread_bps": "{:.1f}",
                "quote_age_ms": "{:,.0f}",
                "inventory_qty": "{:,.0f}",
                "coverage_pct": "{:.2f}",
            }
        ),
        width="stretch",
        hide_index=True,
        height=360,
    )
with board_cols[1]:
    top_risk = risk_df.reindex(risk_df["beta_exposure"].abs().sort_values(ascending=False).index).head(8)
    st.dataframe(
        top_risk.loc[:, ["symbol", "region", "mid", "last_move_pct", "inventory_qty", "beta_exposure", "suggested_hedge_qty", "hedge_symbol"]].style.format(
            {
                "mid": "{:.2f}",
                "last_move_pct": "{:+.2f}%",
                "inventory_qty": "{:,.0f}",
                "beta_exposure": "{:,.2f}",
                "suggested_hedge_qty": "{:,.0f}",
            }
        ),
        width="stretch",
        hide_index=True,
        height=360,
    )
close_surface()
