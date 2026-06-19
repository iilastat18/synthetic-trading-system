from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from src.quote_monitor import AUTO_TRADERS, REQUEST_GROUPS, SETTINGS_ROWS


BASE_INSTRUMENTS = [
    ("XS0000001001", "ALP_ETF", "Alpha Europe ETF", "ETF", "XHAN", "Europe", "HXEU", 1.04, 780, 220_000, 2400),
    ("XS0000001002", "BRV_ETC", "Bravo ETC", "ETC", "XHAN", "Europe", "HXEU", 0.92, 320, 95_000, 800),
    ("XS0000001003", "CRN_FUND", "Crown Fund", "Fund", "XHAN", "Europe", "HXEU", 0.76, 460, 140_000, 1100),
    ("DE000A1EWWW0", "DLT_DE", "Delta Germany", "Shares", "XHAN", "Europe", "HXEU", 1.11, 910, 180_000, 2600),
    ("FR0000004001", "ION_FR", "Ion France", "Shares", "XPAR", "Europe", "HXEU", 0.98, 840, 155_000, 2100),
    ("NL0000005001", "NOVA_NL", "Nova Netherlands", "ETF", "XAMS", "Europe", "HXEU", 0.88, 520, 165_000, 1400),
    ("US0000002001", "EVO_US", "Evo Retail US", "Shares", "XNAS", "US", "HXUS", 1.18, 870, 245_000, 2800),
    ("US0000002002", "FOR_US", "Forum Health US", "Shares", "BATS", "US", "HXUS", 0.84, 760, 130_000, 1900),
    ("US0000002003", "QNT_US", "Quantix Tech US", "ETF", "ARCX", "US", "HXUS", 1.09, 640, 200_000, 1700),
    ("JP0000003001", "GAI_JP", "Gaia Japan", "Shares", "XTKS", "Asia", "HXAS", 1.13, 620, 150_000, 1600),
    ("JP0000003002", "HZN_JP", "Horizon APAC", "ETF", "XHKG", "Asia", "HXAS", 0.91, 540, 175_000, 1450),
    ("JP0000003003", "ORB_SG", "Orbit Singapore", "Shares", "XSES", "Asia", "HXAS", 1.06, 590, 142_000, 1500),
]

HEDGE_BASKETS = [
    ("HXEU", "Europe Core Hedge", "Europe", 100.0),
    ("HXEU_GROWTH", "Europe Growth Basket", "Europe", 104.0),
    ("HXUS", "US Core Hedge", "US", 103.0),
    ("HXUS_TECH", "US Tech Basket", "US", 108.0),
    ("HXAS", "Asia Core Hedge", "Asia", 98.0),
    ("HXAS_HIGHBETA", "Asia High Beta Basket", "Asia", 101.0),
]

MAX_HISTORY_CYCLES = 180


@dataclass
class MMSystemState:
    seed: int
    cycle: int
    touch: pd.DataFrame
    hedges: pd.DataFrame
    history: pd.DataFrame
    groups: pd.DataFrame
    settings: pd.DataFrame
    events: pd.DataFrame
    hedge_blotter: pd.DataFrame


def _clock_for_cycle(cycle: int) -> datetime:
    return datetime(2026, 6, 18, 9, 30) + timedelta(seconds=cycle * 2)


def _clock_str(cycle: int, offset_seconds: int = 0) -> str:
    return (_clock_for_cycle(cycle) - timedelta(seconds=offset_seconds)).strftime("%H:%M:%S")


def _apply_fill(position_qty: int, avg_cost: float, realized_pnl: float, delta_qty: int, fill_price: float) -> tuple[int, float, float]:
    if delta_qty == 0:
        return position_qty, avg_cost, realized_pnl

    old_qty = int(position_qty)
    old_cost = float(avg_cost)
    signed_qty = int(delta_qty)
    realized_delta = 0.0

    if old_qty == 0 or old_qty * signed_qty > 0:
        new_qty = old_qty + signed_qty
        total_cost = old_cost * abs(old_qty) + fill_price * abs(signed_qty)
        new_cost = total_cost / abs(new_qty) if new_qty != 0 else 0.0
        return new_qty, new_cost, realized_pnl

    close_qty = min(abs(old_qty), abs(signed_qty))
    if old_qty > 0:
        realized_delta = close_qty * (fill_price - old_cost)
    else:
        realized_delta = close_qty * (old_cost - fill_price)

    remaining_qty = old_qty + signed_qty
    if remaining_qty == 0:
        return 0, 0.0, realized_pnl + realized_delta
    if old_qty * remaining_qty > 0:
        return remaining_qty, old_cost, realized_pnl + realized_delta
    return remaining_qty, fill_price, realized_pnl + realized_delta


def _build_groups(seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 503)
    rows: list[dict[str, Any]] = []
    for idx, (name, asset_class, venue, request_type, mode, throttle_ms, size_cap, status) in enumerate(REQUEST_GROUPS):
        rows.append(
            {
                "row_key": name,
                "group": name,
                "asset_class": asset_class,
                "venue": venue,
                "request_type": request_type,
                "mode": mode,
                "throttle_ms": throttle_ms,
                "size_cap": size_cap,
                "heartbeat_s": round(float(rng.uniform(2.0, 6.0)), 1),
                "last_update_s": round(float(rng.uniform(0.2, 4.5)), 2),
                "priority": ["P1", "P2", "P2", "P3"][idx % 4],
                "status": status,
                "enabled": status != "Paused",
            }
        )
    return pd.DataFrame(rows)


def _build_settings(seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 907)
    rows: list[dict[str, Any]] = []
    for name, scope, value, action, enabled in SETTINGS_ROWS:
        rows.append(
            {
                "row_key": f"{name}_{scope}",
                "setting": name,
                "scope": scope,
                "value": value,
                "action": action,
                "enabled": enabled,
                "owner": ["DeskOps", "Risk", "Coverage"][rng.integers(0, 3)],
            }
        )
    return pd.DataFrame(rows)


def _mark_touch_frame(touch: pd.DataFrame, hedges: pd.DataFrame) -> pd.DataFrame:
    hedge_lookup = hedges.set_index("symbol")
    marked = touch.copy()
    inventory_notional = marked["inventory_qty"] * marked["mid"]
    marked["inventory_notional"] = inventory_notional.round(2)
    marked["beta_exposure"] = (inventory_notional * marked["beta"]).round(2)
    marked["unrealized_pnl"] = ((marked["mid"] - marked["avg_cost"]) * marked["inventory_qty"]).round(2)
    marked["coverage_pct"] = 0.0
    marked["hedge_last"] = marked["hedge_symbol"].map(hedge_lookup["last_price"]).fillna(0.0)
    marked["suggested_hedge_qty"] = (
        marked["beta_exposure"].abs() / marked["hedge_last"].replace(0, np.nan)
    ).fillna(0.0).round().astype(int)

    for region, region_rows in marked.groupby("region"):
        hedge_symbol = region_rows["hedge_symbol"].iloc[0]
        hedge_row = hedge_lookup.loc[hedge_symbol]
        hedge_notional = abs(float(hedge_row["quantity"]) * float(hedge_row["last_price"]))
        cash_exposure = float(region_rows["beta_exposure"].abs().sum())
        coverage = hedge_notional / cash_exposure if cash_exposure else 0.0
        marked.loc[region_rows.index, "coverage_pct"] = round(min(1.6, coverage), 2)

    return marked


def _snapshot_history(touch: pd.DataFrame, cycle: int) -> pd.DataFrame:
    snapshot = touch.loc[
        :,
        [
            "isin",
            "symbol",
            "name",
            "region",
            "venue",
            "mid",
            "bid",
            "ask",
            "spread_bps",
            "quote_age_ms",
            "inventory_qty",
            "inventory_notional",
            "beta_exposure",
            "last_move_pct",
            "state",
            "hedge_symbol",
        ],
    ].copy()
    snapshot.insert(0, "time", _clock_str(cycle))
    snapshot.insert(0, "cycle", cycle)
    return snapshot


def _append_history(history: pd.DataFrame, snapshot: pd.DataFrame) -> pd.DataFrame:
    latest = snapshot if history.empty else pd.concat([history, snapshot], ignore_index=True)
    max_cycle = int(snapshot["cycle"].max()) if not snapshot.empty else 0
    min_cycle = max(0, max_cycle - MAX_HISTORY_CYCLES + 1)
    return latest.loc[latest["cycle"] >= min_cycle].reset_index(drop=True)


def _seed_touch(seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    for idx, (isin, symbol, name, product, venue, region, hedge_symbol, beta, quote_count, size_cap, inventory_limit) in enumerate(BASE_INSTRUMENTS):
        base_mid = {
            "ETF": 94.0,
            "ETC": 72.0,
            "Fund": 102.0,
            "Shares": 118.0,
        }[product]
        mid = round(float(max(8.0, base_mid + rng.normal(0, 14))), 2)
        spread_bps = round(float(rng.uniform(6.0, 22.0)), 1)
        bid = round(mid * (1 - spread_bps / 20000), 2)
        ask = round(mid * (1 + spread_bps / 20000), 2)
        inventory_qty = int(round(rng.normal(0, inventory_limit * 0.22)))
        inventory_qty = int(np.clip(inventory_qty, -inventory_limit, inventory_limit))
        avg_cost = round(mid + rng.normal(0, 1.8), 2)
        state = "TRAD" if idx % 5 else "SUSPMAN"
        enabled = idx % 8 != 0
        auto_trader = AUTO_TRADERS[idx % len(AUTO_TRADERS)].split(",")[0]
        rows.append(
            {
                "row_key": f"{isin}_{venue}",
                "isin": isin,
                "symbol": symbol,
                "name": name,
                "product": product,
                "bucket": "Funds" if product in {"ETF", "ETC", "Fund"} else "Shares",
                "venue": venue,
                "region": region,
                "hedge_symbol": hedge_symbol,
                "beta": beta,
                "quote_count": quote_count,
                "quoted_size": size_cap,
                "inventory_limit": inventory_limit,
                "mid": mid,
                "bid": bid,
                "ask": ask,
                "spread_bps": spread_bps,
                "last_move_pct": 0.0,
                "quote_age_ms": int(rng.uniform(120, 850)),
                "state": state,
                "enabled": enabled,
                "auto_trader": auto_trader,
                "inventory_qty": inventory_qty,
                "avg_cost": avg_cost,
                "realized_pnl": 0.0,
                "incoming_gap": int(rng.integers(0, 3)),
                "inactive_count": int(rng.integers(0, 2)),
                "error_count": 0,
                "warn_count": 0,
                "hit_ratio": round(float(rng.uniform(71, 97)), 1),
                "skew": round(float(rng.normal(0, 0.18)), 2),
                "hedge_mode": ["Auto", "Passive", "Manual"][idx % 3],
            }
        )
    return pd.DataFrame(rows)


def _seed_hedges(seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 44)
    rows: list[dict[str, Any]] = []
    for symbol, name, region, last_price in HEDGE_BASKETS:
        rows.append(
            {
                "row_key": symbol,
                "symbol": symbol,
                "name": name,
                "region": region,
                "last_price": round(last_price + rng.normal(0, 2), 2),
                "bid": 0.0,
                "ask": 0.0,
                "quantity": 0,
                "avg_cost": 0.0,
                "realized_pnl": 0.0,
            }
        )
    hedges = pd.DataFrame(rows)
    hedges["bid"] = (hedges["last_price"] * 0.9994).round(2)
    hedges["ask"] = (hedges["last_price"] * 1.0006).round(2)
    return hedges


def _blank_events() -> pd.DataFrame:
    return pd.DataFrame(columns=["time", "severity", "component", "message"])


def _blank_blotter() -> pd.DataFrame:
    return pd.DataFrame(columns=["time", "cycle", "region", "hedge_symbol", "side", "quantity", "fill_price", "reason"])


def _append_event(events: pd.DataFrame, cycle: int, severity: str, component: str, message: str) -> pd.DataFrame:
    new_row = pd.DataFrame(
        [{"time": _clock_str(cycle), "severity": severity, "component": component, "message": message}]
    )
    latest = new_row if events.empty else pd.concat([new_row, events], ignore_index=True)
    return latest.head(18)


def build_mm_system(seed: int = 19) -> MMSystemState:
    touch = _seed_touch(seed)
    hedges = _seed_hedges(seed)
    state = MMSystemState(
        seed=seed,
        cycle=0,
        touch=touch,
        hedges=hedges,
        history=pd.DataFrame(),
        groups=_build_groups(seed),
        settings=_build_settings(seed),
        events=_blank_events(),
        hedge_blotter=_blank_blotter(),
    )
    state.touch = _mark_touch_frame(state.touch, state.hedges)
    state.history = _append_history(state.history, _snapshot_history(state.touch, cycle=0))
    state.events = _append_event(state.events, 0, "INFO", "Monitor", "Synthetic quote engine started.")
    state.events = _append_event(state.events, 0, "INFO", "Risk", "Hedge baskets initialised for Europe, US, and Asia.")
    return state


def advance_mm_system(state: MMSystemState, shock_boost: float = 0.0) -> MMSystemState:
    rng = np.random.default_rng(state.seed + state.cycle * 97 + 7)
    state.cycle += 1
    touch = state.touch.copy()
    hedges = state.hedges.copy()
    incident_level = min(1.15, 0.18 + state.cycle * 0.025 + shock_boost)
    region_shocks = {
        "Europe": float(rng.normal(0.0008, 0.0045 + incident_level * 0.003)),
        "US": float(rng.normal(0.0010, 0.0050 + incident_level * 0.0035)),
        "Asia": float(rng.normal(0.0006, 0.0042 + incident_level * 0.0028)),
    }

    for idx in hedges.index:
        region = hedges.loc[idx, "region"]
        last_price = float(hedges.loc[idx, "last_price"])
        next_price = last_price * (1 + region_shocks[region] + rng.normal(0, 0.0025))
        hedges.loc[idx, "last_price"] = round(max(8.0, next_price), 2)
        hedges.loc[idx, "bid"] = round(float(hedges.loc[idx, "last_price"]) * 0.9994, 2)
        hedges.loc[idx, "ask"] = round(float(hedges.loc[idx, "last_price"]) * 1.0006, 2)

    for idx in touch.index:
        row = touch.loc[idx]
        region = str(row["region"])
        previous_mid = float(row["mid"])
        venue_noise = rng.normal(0, 0.0038)
        state_bias = 0.004 if row["state"] == "SUSPMAN" else 0.0
        move = region_shocks[region] + venue_noise + state_bias
        next_mid = previous_mid * (1 + move)
        next_mid = round(float(np.clip(next_mid, 5.0, 320.0)), 2)
        last_move_pct = round(((next_mid / max(previous_mid, 0.01)) - 1) * 100, 2)
        spread_bps = round(float(np.clip(float(row["spread_bps"]) * (1 + abs(move) * 18 + rng.normal(0, 0.05)), 5.0, 38.0)), 1)
        bid = round(next_mid * (1 - spread_bps / 20000), 2)
        ask = round(next_mid * (1 + spread_bps / 20000), 2)

        if bool(row["enabled"]):
            delta_qty = int(round(rng.normal(0, max(18, float(row["inventory_limit"]) * (0.03 + incident_level * 0.02)))))
        else:
            delta_qty = int(round(rng.normal(0, max(5, float(row["inventory_limit"]) * 0.01))))
        if str(row["state"]) in {"HALT", "HALTERR"}:
            delta_qty = int(round(delta_qty * 0.25))

        inventory_qty = int(row["inventory_qty"])
        avg_cost = float(row["avg_cost"])
        realized_pnl = float(row["realized_pnl"])
        if delta_qty != 0:
            fill_price = bid if delta_qty > 0 else ask
            inventory_qty, avg_cost, realized_pnl = _apply_fill(inventory_qty, avg_cost, realized_pnl, delta_qty, float(fill_price))

        inventory_limit = int(row["inventory_limit"])
        inventory_qty = int(np.clip(inventory_qty, -inventory_limit, inventory_limit))
        quote_age = int(np.clip(rng.normal(280 + incident_level * 220 + abs(delta_qty) * 0.9, 160), 30, 1800))
        incoming_gap = int(np.clip(rng.poisson(0.2 + incident_level * 1.5), 0, 40))
        inactive_count = int(np.clip(rng.poisson(0.1 + incident_level * 0.8), 0, max(1, row["quote_count"] // 12)))
        error_count = int(np.clip(rng.poisson(incident_level * 0.7 + (quote_age > 1200) * 2.5 + (abs(inventory_qty) > inventory_limit * 0.9) * 1.3), 0, 9))
        warn_count = int(np.clip(rng.poisson(incident_level * 0.5 + (quote_age > 950) * 1.2 + (abs(inventory_qty) > inventory_limit * 0.75) * 0.9), 0, 6))

        if not bool(row["enabled"]):
            state_value = "HALT"
        elif error_count >= 5 or quote_age > 1350:
            state_value = "HALTERR"
        elif abs(inventory_qty) > inventory_limit * 0.82:
            state_value = "SUSPMAN"
        elif warn_count >= 3 or quote_age > 1000:
            state_value = "HALT"
        else:
            state_value = "TRAD"

        touch.loc[idx, "mid"] = next_mid
        touch.loc[idx, "bid"] = bid
        touch.loc[idx, "ask"] = ask
        touch.loc[idx, "spread_bps"] = spread_bps
        touch.loc[idx, "last_move_pct"] = last_move_pct
        touch.loc[idx, "quote_age_ms"] = quote_age
        touch.loc[idx, "inventory_qty"] = inventory_qty
        touch.loc[idx, "avg_cost"] = round(avg_cost, 2)
        touch.loc[idx, "realized_pnl"] = round(realized_pnl, 2)
        touch.loc[idx, "incoming_gap"] = incoming_gap
        touch.loc[idx, "inactive_count"] = inactive_count
        touch.loc[idx, "error_count"] = error_count
        touch.loc[idx, "warn_count"] = warn_count
        touch.loc[idx, "state"] = state_value
        touch.loc[idx, "hit_ratio"] = round(float(np.clip(float(row["hit_ratio"]) + rng.normal(0, 0.9), 55, 98)), 1)
        touch.loc[idx, "skew"] = round(float(np.clip(float(row["skew"]) + rng.normal(0, 0.06), -0.75, 0.75)), 2)

    touch = _mark_touch_frame(touch, hedges)
    state.touch = touch
    state.hedges = hedges
    state.history = _append_history(state.history, _snapshot_history(touch, cycle=state.cycle))

    hot = touch.sort_values(["error_count", "quote_age_ms"], ascending=False).head(2)
    for row in hot.itertuples(index=False):
        if row.error_count > 0:
            state.events = _append_event(
                state.events,
                state.cycle,
                "ERROR",
                "QuoteMonitor",
                f"{row.symbol} on {row.venue}: {row.error_count} hard errors, quote age {int(row.quote_age_ms)} ms, inventory {int(row.inventory_qty)}.",
            )
        elif row.quote_age_ms > 900:
            state.events = _append_event(
                state.events,
                state.cycle,
                "WARN",
                "QuoteMonitor",
                f"{row.symbol} quote aging is elevated at {int(row.quote_age_ms)} ms.",
            )

    if state.cycle % 5 == 0:
        state.events = _append_event(
            state.events,
            state.cycle,
            "INFO",
            "Heartbeat",
            "Synthetic venue heartbeat completed for all active quote groups.",
        )

    return state


def _append_hedge_trade(
    blotter: pd.DataFrame,
    cycle: int,
    region: str,
    hedge_symbol: str,
    side: str,
    quantity: int,
    fill_price: float,
    reason: str,
) -> pd.DataFrame:
    new_row = pd.DataFrame(
        [
            {
                "time": _clock_str(cycle),
                "cycle": cycle,
                "region": region,
                "hedge_symbol": hedge_symbol,
                "side": side,
                "quantity": quantity,
                "fill_price": round(fill_price, 2),
                "reason": reason,
            }
        ]
    )
    latest = new_row if blotter.empty else pd.concat([new_row, blotter], ignore_index=True)
    return latest.head(24)


def hedge_symbol_inventory(state: MMSystemState, symbol: str) -> str:
    touch = state.touch.copy()
    hedges = state.hedges.copy()
    row = touch.loc[touch["symbol"] == symbol]
    if row.empty:
        return "Symbol not found."
    row = row.iloc[0]
    beta_exposure = float(row["beta_exposure"])
    if abs(beta_exposure) < 1:
        return "Selected symbol has no material exposure to hedge."

    hedge_row = hedges.loc[hedges["symbol"] == row["hedge_symbol"]].iloc[0]
    hedge_price = float(hedge_row["ask"] if beta_exposure < 0 else hedge_row["bid"])
    hedge_qty = max(int(round(abs(beta_exposure) / max(float(hedge_row["last_price"]), 1.0))), 1)
    signed_qty = -hedge_qty if beta_exposure > 0 else hedge_qty
    side = "SELL" if signed_qty < 0 else "BUY"

    qty, avg_cost, realized = _apply_fill(
        int(hedge_row["quantity"]),
        float(hedge_row["avg_cost"]),
        float(hedge_row["realized_pnl"]),
        signed_qty,
        hedge_price,
    )
    hedges.loc[hedges["symbol"] == row["hedge_symbol"], ["quantity", "avg_cost", "realized_pnl"]] = [qty, round(avg_cost, 2), round(realized, 2)]
    state.hedges = hedges
    state.touch = _mark_touch_frame(touch, hedges)
    state.hedge_blotter = _append_hedge_trade(
        state.hedge_blotter,
        state.cycle,
        str(row["region"]),
        str(row["hedge_symbol"]),
        side,
        hedge_qty,
        hedge_price,
        f"Hedge selected {symbol}",
    )
    state.events = _append_event(
        state.events,
        state.cycle,
        "ACTION",
        "Trader",
        f"Hedged {symbol} with {side} {hedge_qty} {row['hedge_symbol']} against beta exposure {beta_exposure:,.0f}.",
    )
    return f"Hedged {symbol} with {side} {hedge_qty} {row['hedge_symbol']}."


def hedge_region_inventory(state: MMSystemState, region: str, hedge_symbol: str | None = None) -> str:
    touch = state.touch.copy()
    hedges = state.hedges.copy()
    region_rows = touch.loc[touch["region"] == region]
    if region_rows.empty:
        return "Region not found."

    region_exposure = float(region_rows["beta_exposure"].sum())
    if hedge_symbol:
        hedge_row = hedges.loc[hedges["symbol"] == hedge_symbol]
    else:
        preferred_symbol = str(region_rows["hedge_symbol"].mode().iloc[0])
        hedge_row = hedges.loc[hedges["symbol"] == preferred_symbol]
    if hedge_row.empty:
        return "Hedge basket not found."
    hedge_row = hedge_row.iloc[0]
    current_hedge_exposure = float(hedge_row["quantity"]) * float(hedge_row["last_price"])
    target_delta = -(region_exposure + current_hedge_exposure)
    if abs(target_delta) < 1:
        return f"{region} region is already close to flat."

    hedge_qty = max(int(round(abs(target_delta) / max(float(hedge_row["last_price"]), 1.0))), 1)
    signed_qty = hedge_qty if target_delta > 0 else -hedge_qty
    side = "BUY" if signed_qty > 0 else "SELL"
    fill_price = float(hedge_row["ask"] if signed_qty > 0 else hedge_row["bid"])
    qty, avg_cost, realized = _apply_fill(
        int(hedge_row["quantity"]),
        float(hedge_row["avg_cost"]),
        float(hedge_row["realized_pnl"]),
        signed_qty,
        fill_price,
    )
    hedges.loc[hedges["symbol"] == hedge_row["symbol"], ["quantity", "avg_cost", "realized_pnl"]] = [qty, round(avg_cost, 2), round(realized, 2)]
    state.hedges = hedges
    state.touch = _mark_touch_frame(touch, hedges)
    state.hedge_blotter = _append_hedge_trade(
        state.hedge_blotter,
        state.cycle,
        region,
        str(hedge_row["symbol"]),
        side,
        hedge_qty,
        fill_price,
        f"Hedge region {region}",
    )
    state.events = _append_event(
        state.events,
        state.cycle,
        "ACTION",
        "Trader",
        f"Hedged {region} book with {side} {hedge_qty} {hedge_row['symbol']} to offset region exposure {region_exposure:,.0f}.",
    )
    return f"Hedged {region} with {side} {hedge_qty} {hedge_row['symbol']}."


def flatten_region_hedge(state: MMSystemState, region: str, hedge_symbol: str | None = None) -> str:
    hedges = state.hedges.copy()
    if hedge_symbol:
        hedge_row = hedges.loc[hedges["symbol"] == hedge_symbol]
    else:
        region_rows = state.touch.loc[state.touch["region"] == region]
        preferred_symbol = str(region_rows["hedge_symbol"].mode().iloc[0]) if not region_rows.empty else ""
        hedge_row = hedges.loc[hedges["symbol"] == preferred_symbol]
    if hedge_row.empty:
        return "Region not found."
    hedge_row = hedge_row.iloc[0]
    current_qty = int(hedge_row["quantity"])
    if current_qty == 0:
        return f"{region} hedge basket is already flat."

    signed_qty = -current_qty
    side = "BUY" if signed_qty > 0 else "SELL"
    fill_price = float(hedge_row["ask"] if signed_qty > 0 else hedge_row["bid"])
    qty, avg_cost, realized = _apply_fill(
        current_qty,
        float(hedge_row["avg_cost"]),
        float(hedge_row["realized_pnl"]),
        signed_qty,
        fill_price,
    )
    hedges.loc[hedges["symbol"] == hedge_row["symbol"], ["quantity", "avg_cost", "realized_pnl"]] = [qty, round(avg_cost, 2), round(realized, 2)]
    state.hedges = hedges
    state.touch = _mark_touch_frame(state.touch, hedges)
    state.hedge_blotter = _append_hedge_trade(
        state.hedge_blotter,
        state.cycle,
        region,
        str(hedge_row["symbol"]),
        side,
        abs(current_qty),
        fill_price,
        f"Flatten region {region}",
    )
    state.events = _append_event(
        state.events,
        state.cycle,
        "ACTION",
        "Trader",
        f"Flattened {region} hedge basket with {side} {abs(current_qty)} {hedge_row['symbol']}.",
    )
    return f"Flattened {region} hedge basket."


def manual_hedge_ticket(
    state: MMSystemState,
    *,
    hedge_symbol: str,
    side: str,
    quantity: int,
    reason: str,
    source_symbol: str | None = None,
    region: str | None = None,
) -> str:
    if quantity <= 0:
        return "Manual hedge quantity must be positive."

    hedges = state.hedges.copy()
    hedge_row = hedges.loc[hedges["symbol"] == hedge_symbol]
    if hedge_row.empty:
        return "Selected hedge basket is unavailable."
    hedge_row = hedge_row.iloc[0]

    signed_qty = int(quantity if side.upper() == "BUY" else -quantity)
    fill_price = float(hedge_row["ask"] if signed_qty > 0 else hedge_row["bid"])
    qty, avg_cost, realized = _apply_fill(
        int(hedge_row["quantity"]),
        float(hedge_row["avg_cost"]),
        float(hedge_row["realized_pnl"]),
        signed_qty,
        fill_price,
    )
    hedges.loc[hedges["symbol"] == hedge_symbol, ["quantity", "avg_cost", "realized_pnl"]] = [qty, round(avg_cost, 2), round(realized, 2)]
    state.hedges = hedges
    state.touch = _mark_touch_frame(state.touch, hedges)

    resolved_region = region or str(hedge_row["region"])
    suffix = f" for {source_symbol}" if source_symbol else ""
    state.hedge_blotter = _append_hedge_trade(
        state.hedge_blotter,
        state.cycle,
        resolved_region,
        hedge_symbol,
        side.upper(),
        quantity,
        fill_price,
        f"{reason}{suffix}",
    )
    state.events = _append_event(
        state.events,
        state.cycle,
        "ACTION",
        "Trader",
        f"Manual hedge ticket: {side.upper()} {quantity} {hedge_symbol} @ {fill_price:.2f} ({reason}{suffix}).",
    )
    return f"Manual hedge sent: {side.upper()} {quantity} {hedge_symbol} @ {fill_price:.2f}."


def set_symbol_hedge_override(state: MMSystemState, *, symbol: str, hedge_symbol: str) -> str:
    if hedge_symbol not in set(state.hedges["symbol"]):
        return "Selected hedge basket is unavailable."

    touch = state.touch.copy()
    row = touch.loc[touch["symbol"] == symbol]
    if row.empty:
        return "Selected symbol not found."
    current_region = str(row.iloc[0]["region"])
    hedge_region = str(state.hedges.loc[state.hedges["symbol"] == hedge_symbol, "region"].iloc[0])
    if hedge_region != current_region:
        return f"{hedge_symbol} belongs to {hedge_region}, but {symbol} is in {current_region}."

    touch.loc[touch["symbol"] == symbol, "hedge_symbol"] = hedge_symbol
    touch.loc[touch["symbol"] == symbol, "hedge_mode"] = "Manual"
    state.touch = _mark_touch_frame(touch, state.hedges)
    state.events = _append_event(
        state.events,
        state.cycle,
        "ACTION",
        "Trader",
        f"Basket override applied: {symbol} now maps to {hedge_symbol}.",
    )
    return f"Applied basket override for {symbol} -> {hedge_symbol}."


def set_region_hedge_override(state: MMSystemState, *, region: str, hedge_symbol: str) -> str:
    if hedge_symbol not in set(state.hedges["symbol"]):
        return "Selected hedge basket is unavailable."

    touch = state.touch.copy()
    hedge_region = str(state.hedges.loc[state.hedges["symbol"] == hedge_symbol, "region"].iloc[0])
    if hedge_region != region:
        return f"{hedge_symbol} belongs to {hedge_region}, but the selected region is {region}."

    mask = touch["region"] == region
    if not mask.any():
        return "Selected region not found."

    touch.loc[mask, "hedge_symbol"] = hedge_symbol
    touch.loc[mask, "hedge_mode"] = "Manual"
    state.touch = _mark_touch_frame(touch, state.hedges)
    state.events = _append_event(
        state.events,
        state.cycle,
        "ACTION",
        "Trader",
        f"Region basket override applied: {region} book now maps to {hedge_symbol}.",
    )
    return f"Applied basket override for {region} -> {hedge_symbol}."


def clear_symbol_hedge_override(state: MMSystemState, *, symbol: str) -> str:
    touch = state.touch.copy()
    row = touch.loc[touch["symbol"] == symbol]
    if row.empty:
        return "Selected symbol not found."
    region = str(row.iloc[0]["region"])
    default_hedge = str(state.hedges.loc[state.hedges["region"] == region, "symbol"].sort_values().iloc[0])
    touch.loc[touch["symbol"] == symbol, "hedge_symbol"] = default_hedge
    touch.loc[touch["symbol"] == symbol, "hedge_mode"] = "Auto"
    state.touch = _mark_touch_frame(touch, state.hedges)
    state.events = _append_event(
        state.events,
        state.cycle,
        "ACTION",
        "Trader",
        f"Cleared basket override for {symbol}; mapping reverted to {default_hedge}.",
    )
    return f"Cleared basket override for {symbol}."


def region_hedge_choices(state: MMSystemState, region: str) -> list[str]:
    return state.hedges.loc[state.hedges["region"] == region, "symbol"].sort_values().tolist()


def clear_region_hedge_override(state: MMSystemState, *, region: str) -> str:
    touch = state.touch.copy()
    mask = touch["region"] == region
    if not mask.any():
        return "Selected region not found."
    default_hedge = str(state.hedges.loc[state.hedges["region"] == region, "symbol"].sort_values().iloc[0])
    touch.loc[mask, "hedge_symbol"] = default_hedge
    touch.loc[mask, "hedge_mode"] = "Auto"
    state.touch = _mark_touch_frame(touch, state.hedges)
    state.events = _append_event(
        state.events,
        state.cycle,
        "ACTION",
        "Trader",
        f"Cleared region basket override for {region}; mapping reverted to {default_hedge}.",
    )
    return f"Cleared basket override for {region}."


def derive_summary(state: MMSystemState) -> pd.DataFrame:
    touch = state.touch.copy()
    rows: list[dict[str, Any]] = []
    row_id = 0

    def add_row(level: int, name: str, scope: pd.DataFrame) -> None:
        nonlocal row_id
        total = int(scope["quote_count"].sum())
        enabled_count = int(scope.loc[scope["enabled"], "quote_count"].sum())
        incoming = int(scope["incoming_gap"].sum())
        inactive = int(scope["inactive_count"].sum())
        quotes = max(enabled_count - incoming, 0)
        error_count = int(scope["error_count"].sum())
        warn_count = int(scope["warn_count"].sum())
        severity = "🔴 Error" if error_count > 0 else "🟠 Warn" if warn_count > 0 else "🟢 OK"
        auto = ", ".join(sorted(scope["auto_trader"].unique())[:2])
        prefix = {0: "▾ ", 1: "  ▾ ", 2: "    ▾ ", 3: "      • "}[level]
        rows.append(
            {
                "row_key": f"summary_{row_id}",
                "node": f"{prefix}{name}",
                "node_name": name,
                "level": level,
                "total": total,
                "enabled_count": enabled_count,
                "quotes": quotes,
                "inactive": inactive,
                "incoming": incoming,
                "error": severity,
                "error_count": error_count,
                "info_count": int((scope["state"] != "TRAD").sum()),
                "warn_count": warn_count,
                "auto_traders": auto,
                "send_q": bool(scope["enabled"].any()),
                "send_r": bool((scope["hedge_mode"] != "Paused").any()),
                "send_qr": bool(scope["enabled"].all()),
                "enabled_flag": bool(scope["enabled"].any()),
            }
        )
        row_id += 1

    for bucket in ["Funds", "Shares"]:
        bucket_scope = touch.loc[touch["bucket"] == bucket]
        if bucket_scope.empty:
            continue
        add_row(0, f"{bucket} - Quotes", bucket_scope)
        for venue in sorted(bucket_scope["venue"].unique()):
            venue_scope = bucket_scope.loc[bucket_scope["venue"] == venue]
            add_row(1, venue, venue_scope)
            for product in sorted(venue_scope["product"].unique()):
                product_scope = venue_scope.loc[venue_scope["product"] == product]
                add_row(2, product, product_scope)
                for state_name in sorted(product_scope["state"].unique()):
                    state_scope = product_scope.loc[product_scope["state"] == state_name]
                    add_row(3, state_name, state_scope)

    return pd.DataFrame(rows)


def system_metrics(state: MMSystemState) -> dict[str, float]:
    touch = state.touch
    hedges = state.hedges.copy()
    hedge_unrealized = ((hedges["last_price"] - hedges["avg_cost"]) * hedges["quantity"]).where(hedges["quantity"] != 0, 0.0)
    hedge_notional = (hedges["last_price"] * hedges["quantity"]).abs().sum()
    return {
        "total_quotes": float(touch["quote_count"].sum()),
        "enabled_quotes": float(touch.loc[touch["enabled"], "quote_count"].sum()),
        "hard_errors": float(touch["error_count"].sum()),
        "warnings": float(touch["warn_count"].sum()),
        "stale_quotes": float((touch["state"] != "TRAD").sum()),
        "disabled_symbols": float((~touch["enabled"]).sum()),
        "gross_inventory_usd": float(touch["inventory_notional"].abs().sum()),
        "net_inventory_usd": float(touch["beta_exposure"].sum()),
        "hedge_notional": float(hedge_notional),
        "hedge_unrealized": float(hedge_unrealized.sum()),
    }


def touch_monitor_frame(state: MMSystemState) -> pd.DataFrame:
    cols = [
        "row_key",
        "isin",
        "symbol",
        "product",
        "venue",
        "region",
        "bid",
        "ask",
        "last_move_pct",
        "spread_bps",
        "quote_age_ms",
        "state",
        "quoted_size",
        "inventory_qty",
        "inventory_limit",
        "inventory_notional",
        "beta_exposure",
        "coverage_pct",
        "auto_trader",
        "hedge_symbol",
        "hedge_mode",
        "enabled",
    ]
    return state.touch.loc[:, cols].sort_values(["region", "venue", "symbol"])


def risk_book_frame(state: MMSystemState) -> pd.DataFrame:
    frame = state.touch.loc[
        :,
        [
            "symbol",
            "name",
            "product",
            "region",
            "venue",
            "last_move_pct",
            "inventory_qty",
            "inventory_limit",
            "mid",
            "inventory_notional",
            "beta_exposure",
            "suggested_hedge_qty",
            "hedge_symbol",
            "coverage_pct",
            "unrealized_pnl",
            "realized_pnl",
            "state",
        ],
    ].copy()
    frame["utilization_pct"] = (frame["inventory_qty"].abs() / frame["inventory_limit"]).round(2)
    return frame.sort_values(["region", "beta_exposure"], ascending=[True, False])


def hedge_books_frame(state: MMSystemState) -> pd.DataFrame:
    hedges = state.hedges.copy()
    hedges["market_value"] = (hedges["quantity"] * hedges["last_price"]).round(2)
    hedges["unrealized_pnl"] = ((hedges["last_price"] - hedges["avg_cost"]) * hedges["quantity"]).where(hedges["quantity"] != 0, 0.0).round(2)
    return hedges.loc[:, ["symbol", "region", "last_price", "quantity", "avg_cost", "market_value", "unrealized_pnl", "realized_pnl"]]


def hedge_blotter_frame(state: MMSystemState) -> pd.DataFrame:
    return state.hedge_blotter.copy()


def region_risk_frame(state: MMSystemState) -> pd.DataFrame:
    touch = state.touch
    hedges = state.hedges
    rows: list[dict[str, Any]] = []
    for region, scope in touch.groupby("region"):
        gross_inventory = float(scope["inventory_notional"].abs().sum())
        beta_net = float(scope["beta_exposure"].sum())
        hedge_scope = hedges.loc[hedges["region"] == region]
        hedge_notional = float((hedge_scope["quantity"] * hedge_scope["last_price"]).sum())
        preferred_symbol = str(scope["hedge_symbol"].mode().iloc[0])
        rows.append(
            {
                "region": region,
                "gross_inventory": round(gross_inventory, 2),
                "beta_net": round(beta_net, 2),
                "primary_hedge": preferred_symbol,
                "hedge_qty": int(hedge_scope["quantity"].sum()),
                "hedge_notional": round(hedge_notional, 2),
                "post_hedge_net": round(beta_net + hedge_notional, 2),
                "coverage_pct": round(abs(hedge_notional) / gross_inventory, 2) if gross_inventory else 0.0,
            }
        )
    return pd.DataFrame(rows)


def market_overview_history_frame(state: MMSystemState) -> pd.DataFrame:
    history = state.history.copy()
    if history.empty:
        return history

    overview = (
        history.groupby(["cycle", "time", "region"], as_index=False)
        .agg(
            avg_mid=("mid", "mean"),
            avg_spread_bps=("spread_bps", "mean"),
            avg_move_pct=("last_move_pct", "mean"),
            stressed_symbols=("state", lambda values: int((pd.Series(values) != "TRAD").sum())),
        )
        .sort_values(["cycle", "region"])
    )
    overview["market_index"] = overview.groupby("region")["avg_mid"].transform(lambda series: ((series / series.iloc[0]) * 100).round(2))
    overview["avg_spread_bps"] = overview["avg_spread_bps"].round(2)
    overview["avg_move_pct"] = overview["avg_move_pct"].round(2)
    return overview


def market_movers_frame(state: MMSystemState) -> pd.DataFrame:
    movers = state.touch.loc[
        :,
        [
            "symbol",
            "isin",
            "name",
            "region",
            "venue",
            "mid",
            "bid",
            "ask",
            "last_move_pct",
            "spread_bps",
            "inventory_qty",
            "beta_exposure",
            "state",
            "hedge_symbol",
        ],
    ].copy()
    movers["abs_move_pct"] = movers["last_move_pct"].abs().round(2)
    return movers.sort_values(["abs_move_pct", "spread_bps"], ascending=[False, False]).reset_index(drop=True)


def isin_history_frame(state: MMSystemState, symbol: str) -> pd.DataFrame:
    history = state.history.loc[state.history["symbol"] == symbol].copy()
    if history.empty:
        return history
    return history.sort_values("cycle").reset_index(drop=True)
