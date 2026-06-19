from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class ExecutionResult:
    message: str
    state: dict[str, Any]


def initial_state() -> dict[str, Any]:
    return {
        "cash": 1_000_000.0,
        "positions": {},
        "trade_blotter": [],
        "realized_pnl": 0.0,
        "equity_history": [{"tick": 0, "equity": 1_000_000.0}],
        "order_id": 1,
    }


def _ensure_position(state: dict[str, Any], symbol: str, isin: str, name: str, hedge_symbol: str) -> dict[str, Any]:
    if symbol not in state["positions"]:
        state["positions"][symbol] = {
            "symbol": symbol,
            "isin": isin,
            "name": name,
            "hedge_symbol": hedge_symbol,
            "quantity": 0,
            "avg_cost": 0.0,
            "realized_pnl": 0.0,
        }
    return state["positions"][symbol]


def execute_order(
    state: dict[str, Any],
    market: pd.DataFrame,
    *,
    symbol: str,
    side: str,
    quantity: int,
    reason: str = "Manual",
) -> ExecutionResult:
    if quantity <= 0:
        return ExecutionResult("Quantity must be positive.", state)

    row = market.loc[market["symbol"] == symbol]
    if row.empty:
        return ExecutionResult("Instrument not found in current market.", state)
    row = row.iloc[0]

    fill_price = float(row["ask"] if side == "BUY" else row["bid"])
    signed_qty = int(quantity if side == "BUY" else -quantity)

    position = _ensure_position(state, symbol, str(row["isin"]), str(row["name"]), str(row["hedge_symbol"]))
    old_qty = int(position["quantity"])
    old_cost = float(position["avg_cost"])

    realized_delta = 0.0
    if old_qty == 0 or old_qty * signed_qty > 0:
        new_qty = old_qty + signed_qty
        total_cost = old_cost * abs(old_qty) + fill_price * abs(signed_qty)
        position["avg_cost"] = total_cost / abs(new_qty) if new_qty != 0 else 0.0
        position["quantity"] = new_qty
    else:
        close_qty = min(abs(old_qty), abs(signed_qty))
        if old_qty > 0:
            realized_delta = close_qty * (fill_price - old_cost)
        else:
            realized_delta = close_qty * (old_cost - fill_price)
        remaining_qty = old_qty + signed_qty
        if remaining_qty == 0:
            position["quantity"] = 0
            position["avg_cost"] = 0.0
        elif old_qty * remaining_qty > 0:
            position["quantity"] = remaining_qty
        else:
            position["quantity"] = remaining_qty
            position["avg_cost"] = fill_price

    position["realized_pnl"] += realized_delta
    state["realized_pnl"] += realized_delta
    cash_delta = -fill_price * signed_qty
    state["cash"] += cash_delta
    state["trade_blotter"].append(
        {
            "order_id": state["order_id"],
            "tick": int(row["tick"]),
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "fill_price": round(fill_price, 2),
            "reason": reason,
            "cash_after": round(state["cash"], 2),
        }
    )
    state["order_id"] += 1
    return ExecutionResult(f"{side} {quantity} {symbol} @ {fill_price:.2f}", state)


def execute_hedge(state: dict[str, Any], market: pd.DataFrame, *, symbol: str) -> ExecutionResult:
    row = market.loc[market["symbol"] == symbol]
    if row.empty:
        return ExecutionResult("Selected symbol not found for hedge.", state)
    row = row.iloc[0]

    position = state["positions"].get(symbol)
    if not position or position["quantity"] == 0:
        return ExecutionResult("No open position to hedge.", state)

    hedge_symbol = str(row["hedge_symbol"])
    hedge_row = market.loc[market["symbol"] == hedge_symbol]
    if hedge_row.empty:
        return ExecutionResult("Hedge instrument unavailable.", state)
    hedge_row = hedge_row.iloc[0]

    gross_notional = abs(position["quantity"] * float(row["last_price"]) * float(row["beta"]))
    hedge_qty = max(int(round(gross_notional / max(float(hedge_row["last_price"]), 1.0))), 1)
    hedge_side = "SELL" if position["quantity"] > 0 else "BUY"
    result = execute_order(
        state,
        market,
        symbol=hedge_symbol,
        side=hedge_side,
        quantity=hedge_qty,
        reason=f"Hedge for {symbol}",
    )
    return ExecutionResult(
        f"Hedged {symbol} with {hedge_side} {hedge_qty} {hedge_symbol}.",
        result.state,
    )


def mark_to_market(state: dict[str, Any], market: pd.DataFrame) -> dict[str, float]:
    unrealized = 0.0
    gross_exposure = 0.0
    net_exposure = 0.0
    long_exposure = 0.0
    short_exposure = 0.0
    market_value = 0.0
    for symbol, position in state["positions"].items():
        qty = int(position["quantity"])
        if qty == 0:
            continue
        row = market.loc[market["symbol"] == symbol]
        if row.empty:
            continue
        last_price = float(row.iloc[0]["last_price"])
        unrealized += qty * (last_price - float(position["avg_cost"]))
        notional = qty * last_price
        market_value += notional
        gross_exposure += abs(notional)
        net_exposure += notional
        if notional >= 0:
            long_exposure += notional
        else:
            short_exposure += abs(notional)
    equity = state["cash"] + market_value
    return {
        "unrealized_pnl": round(unrealized, 2),
        "gross_exposure": round(gross_exposure, 2),
        "net_exposure": round(net_exposure, 2),
        "long_exposure": round(long_exposure, 2),
        "short_exposure": round(short_exposure, 2),
        "market_value": round(market_value, 2),
        "equity": round(equity, 2),
    }


def snapshot_equity(state: dict[str, Any], market: pd.DataFrame, tick: int) -> None:
    mtm = mark_to_market(state, market)
    snapshot = {"tick": tick, "equity": round(mtm["equity"], 2)}
    if state["equity_history"] and int(state["equity_history"][-1]["tick"]) == tick:
        state["equity_history"][-1] = snapshot
    else:
        state["equity_history"].append(snapshot)


def positions_frame(state: dict[str, Any], market: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for symbol, position in state["positions"].items():
        qty = int(position["quantity"])
        if qty == 0:
            continue
        row = market.loc[market["symbol"] == symbol].iloc[0]
        last_price = float(row["last_price"])
        unrealized = qty * (last_price - float(position["avg_cost"]))
        mapped_hedge_symbol = str(position["hedge_symbol"])
        hedge_position = state["positions"].get(mapped_hedge_symbol, {})
        hedge_qty = int(hedge_position.get("quantity", 0))
        hedge_row = market.loc[market["symbol"] == mapped_hedge_symbol]
        hedge_last = float(hedge_row.iloc[0]["last_price"]) if not hedge_row.empty else 0.0
        base_notional = abs(qty * last_price * float(row["beta"]))
        hedge_notional = abs(hedge_qty * hedge_last)
        hedge_ratio = hedge_notional / base_notional if base_notional else 0.0

        if row["is_hedge"]:
            hedge_status = "Basket"
        elif hedge_ratio >= 0.9:
            hedge_status = "Covered"
        elif hedge_ratio >= 0.35:
            hedge_status = "Partial"
        else:
            hedge_status = "Open"
        rows.append(
            {
                "symbol": symbol,
                "isin": position["isin"],
                "name": position["name"],
                "side": "Long" if qty > 0 else "Short",
                "quantity": qty,
                "avg_cost": round(float(position["avg_cost"]), 2),
                "last_price": round(last_price, 2),
                "market_value": round(qty * last_price, 2),
                "unrealized_pnl": round(unrealized, 2),
                "realized_pnl": round(float(position["realized_pnl"]), 2),
                "hedge_symbol": position["hedge_symbol"],
                "hedge_ratio": round(hedge_ratio, 2),
                "hedge_status": hedge_status,
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=[
                "symbol",
                "isin",
                "name",
                "side",
                "quantity",
                "avg_cost",
                "last_price",
                "market_value",
                "unrealized_pnl",
                "realized_pnl",
                "hedge_symbol",
                "hedge_ratio",
                "hedge_status",
            ]
        )
    return pd.DataFrame(rows).sort_values(["symbol"])


def blotter_frame(state: dict[str, Any]) -> pd.DataFrame:
    if not state["trade_blotter"]:
        return pd.DataFrame(columns=["order_id", "tick", "symbol", "side", "quantity", "fill_price", "reason", "cash_after"])
    return pd.DataFrame(state["trade_blotter"]).sort_values(["order_id"], ascending=False)


def equity_frame(state: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(state["equity_history"]).drop_duplicates(subset=["tick"], keep="last")


def risk_frame(state: dict[str, Any], market: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for region in sorted(market["region"].dropna().unique()):
        region_slice = market.loc[market["region"] == region, ["symbol", "last_price", "is_hedge"]]
        non_hedge_net = 0.0
        hedge_net = 0.0
        non_hedge_gross = 0.0
        hedge_gross = 0.0
        for item in region_slice.itertuples(index=False):
            position = state["positions"].get(item.symbol)
            qty = int(position["quantity"]) if position else 0
            if qty == 0:
                continue
            notional = qty * float(item.last_price)
            if item.is_hedge:
                hedge_net += notional
                hedge_gross += abs(notional)
            else:
                non_hedge_net += notional
                non_hedge_gross += abs(notional)

        hedge_ratio = hedge_gross / non_hedge_gross if non_hedge_gross else 0.0
        rows.append(
            {
                "region": region,
                "cash_balance": round(float(state["cash"]), 2),
                "gross_risk": round(non_hedge_gross, 2),
                "directional_net": round(non_hedge_net, 2),
                "hedge_notional": round(hedge_gross, 2),
                "post_hedge_net": round(non_hedge_net + hedge_net, 2),
                "hedge_ratio": round(hedge_ratio, 2),
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "region",
                "cash_balance",
                "gross_risk",
                "directional_net",
                "hedge_notional",
                "post_hedge_net",
                "hedge_ratio",
            ]
        )
    return pd.DataFrame(rows)
