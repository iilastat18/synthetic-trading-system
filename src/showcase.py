from __future__ import annotations

import numpy as np
import pandas as pd

from src.engine import (
    blotter_frame,
    equity_frame,
    execute_hedge,
    execute_order,
    initial_state,
    mark_to_market,
    positions_frame,
    risk_frame,
    snapshot_equity,
)
from src.market import advance_market, initialize_market


def build_showcase_snapshot(seed: int = 23) -> dict[str, pd.DataFrame | dict]:
    market, history = initialize_market(seed=seed)
    state = initial_state()
    rng = np.random.default_rng(seed + 101)

    snapshot_equity(state, market, tick=0)
    for _ in range(2):
        market, history = advance_market(market, history, rng=rng)
        snapshot_equity(state, market, tick=int(market["tick"].max()))

    execute_order(state, market, symbol="ALP", side="BUY", quantity=450, reason="Opening theme position")
    snapshot_equity(state, market, tick=int(market["tick"].max()))

    execute_order(state, market, symbol="DLT", side="SELL", quantity=320, reason="Macro short")
    snapshot_equity(state, market, tick=int(market["tick"].max()))

    execute_order(state, market, symbol="GAI", side="BUY", quantity=260, reason="Asia add")
    snapshot_equity(state, market, tick=int(market["tick"].max()))

    execute_hedge(state, market, symbol="ALP")
    execute_hedge(state, market, symbol="DLT")
    snapshot_equity(state, market, tick=int(market["tick"].max()))

    for _ in range(4):
        market, history = advance_market(market, history, rng=rng)
        snapshot_equity(state, market, tick=int(market["tick"].max()))

    return {
        "market": market,
        "history": history,
        "state": state,
        "mtm": mark_to_market(state, market),
        "positions": positions_frame(state, market),
        "blotter": blotter_frame(state),
        "equity": equity_frame(state),
        "risk": risk_frame(state, market),
    }
