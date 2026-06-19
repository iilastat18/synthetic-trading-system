from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Instrument:
    isin: str
    symbol: str
    name: str
    region: str
    sector: str
    beta: float
    hedge_symbol: str
    is_hedge: bool = False


def build_instruments() -> list[Instrument]:
    base = [
        ("XS0000001001", "ALP", "Alpha Systems", "Europe", "Technology", 1.08, "HXEU"),
        ("XS0000001002", "BRV", "Bravo Holdings", "Europe", "Financials", 0.92, "HXEU"),
        ("XS0000001003", "CRN", "Crown Energy", "Europe", "Energy", 1.17, "HXEU"),
        ("US0000002001", "DLT", "Delta Labs", "US", "Technology", 1.23, "HXUS"),
        ("US0000002002", "EVO", "Evo Retail", "US", "Consumer", 0.86, "HXUS"),
        ("US0000002003", "FRM", "Forum Health", "US", "Healthcare", 0.79, "HXUS"),
        ("JP0000003001", "GAI", "Gaia Robotics", "Asia", "Industrials", 1.11, "HXAS"),
        ("JP0000003002", "HZN", "Horizon Media", "Asia", "Consumer", 0.97, "HXAS"),
        ("JP0000003003", "ION", "Ion Materials", "Asia", "Industrials", 1.05, "HXAS"),
    ]
    hedges = [
        ("HXEU00000001", "HXEU", "Europe Hedge Basket", "Europe", "Hedge", 1.0, "HXEU", True),
        ("HXUS00000001", "HXUS", "US Hedge Basket", "US", "Hedge", 1.0, "HXUS", True),
        ("HXAS00000001", "HXAS", "Asia Hedge Basket", "Asia", "Hedge", 1.0, "HXAS", True),
    ]
    instruments = [Instrument(*row) for row in base]
    instruments.extend(Instrument(*row) for row in hedges)
    return instruments


def initialize_market(seed: int = 7) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    instruments = build_instruments()
    rows: list[dict[str, object]] = []
    history_rows: list[dict[str, object]] = []
    for instrument in instruments:
        base_price = {
            "Technology": 126.0,
            "Financials": 82.0,
            "Energy": 71.0,
            "Consumer": 94.0,
            "Healthcare": 118.0,
            "Industrials": 88.0,
            "Hedge": 100.0,
        }[instrument.sector]
        price = base_price + rng.normal(0, 7)
        spread_bps = 5.0 if instrument.is_hedge else float(9.5 + instrument.beta * 2.2 + rng.normal(0, 0.8))
        rows.append(
            {
                "isin": instrument.isin,
                "symbol": instrument.symbol,
                "name": instrument.name,
                "region": instrument.region,
                "sector": instrument.sector,
                "beta": instrument.beta,
                "hedge_symbol": instrument.hedge_symbol,
                "is_hedge": instrument.is_hedge,
                "last_price": round(float(max(price, 12)), 2),
                "spread_bps": round(float(max(spread_bps, 2.0)), 2),
                "bid": 0.0,
                "ask": 0.0,
                "day_change_pct": round(float(rng.normal(0, 0.9)), 2),
                "liquidity_score": round(float(62 + rng.normal(0, 11)), 1),
                "tick": 0,
            }
        )
        history_rows.append(
            {"tick": 0, "symbol": instrument.symbol, "last_price": round(float(max(price, 12)), 2)}
        )

    market = pd.DataFrame(rows)
    market["bid"] = (market["last_price"] * (1 - market["spread_bps"] / 20000)).round(2)
    market["ask"] = (market["last_price"] * (1 + market["spread_bps"] / 20000)).round(2)
    history = pd.DataFrame(history_rows)
    return market, history


def advance_market(
    market: pd.DataFrame,
    price_history: pd.DataFrame,
    tick_size: int = 1,
    rng: np.random.Generator | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = rng or np.random.default_rng()
    updated = market.copy()
    current_tick = int(updated["tick"].max()) + tick_size

    regime_shift = rng.normal(0.0, 0.55)
    for idx in updated.index:
        row = updated.loc[idx]
        shock = rng.normal(0.0, 0.85 if row["is_hedge"] else 1.6)
        beta_push = row["beta"] * regime_shift * 0.65
        next_change = row["day_change_pct"] * 0.38 + shock + beta_push
        next_change = float(np.clip(next_change, -8.0, 8.0))
        next_price = row["last_price"] * (1 + next_change / 100)
        next_spread = row["spread_bps"] * (1.0 + abs(next_change) / 18)
        updated.loc[idx, "last_price"] = round(float(max(next_price, 8)), 2)
        updated.loc[idx, "spread_bps"] = round(float(max(next_spread, 1.5)), 2)
        updated.loc[idx, "day_change_pct"] = round(next_change, 2)
        updated.loc[idx, "liquidity_score"] = round(float(np.clip(row["liquidity_score"] + rng.normal(0, 2.1), 28, 96)), 1)
        updated.loc[idx, "tick"] = current_tick

    updated["bid"] = (updated["last_price"] * (1 - updated["spread_bps"] / 20000)).round(2)
    updated["ask"] = (updated["last_price"] * (1 + updated["spread_bps"] / 20000)).round(2)

    next_history = pd.concat(
        [
            price_history,
            updated.loc[:, ["tick", "symbol", "last_price"]],
        ],
        ignore_index=True,
    )
    return updated, next_history
