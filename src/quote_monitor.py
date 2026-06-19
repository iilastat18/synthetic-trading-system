from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd


TREE_SPEC = [
    (0, "Funds - Quotes", "Funds", "ALL", "SYSTEM", 1595),
    (1, "XHAN", "Funds", "XHAN", "VENUE", 1595),
    (2, "ETC", "Funds", "XHAN", "PRODUCT", 4),
    (3, "<None>", "Funds", "XHAN", "STRATEGY", 4),
    (3, "TRAD", "Funds", "XHAN", "STRATEGY", 4),
    (2, "ETF", "Funds", "XHAN", "PRODUCT", 1583),
    (3, "<None>", "Funds", "XHAN", "STRATEGY", 1583),
    (3, "TRAD", "Funds", "XHAN", "STRATEGY", 1580),
    (3, "unknown", "Funds", "XHAN", "STRATEGY", 3),
    (2, "Fund", "Funds", "XHAN", "PRODUCT", 8),
    (3, "<None>", "Funds", "XHAN", "STRATEGY", 8),
    (3, "TRAD", "Funds", "XHAN", "STRATEGY", 8),
    (0, "Shares - Quotes", "Shares", "ALL", "SYSTEM", 3931),
    (1, "XHAN", "Shares", "XHAN", "VENUE", 3931),
    (2, "<None>", "Shares", "XHAN", "PRODUCT", 3931),
    (3, "HALT", "Shares", "XHAN", "STATE", 14),
    (3, "HALTERR", "Shares", "XHAN", "STATE", 9),
    (3, "SUSPMAN", "Shares", "XHAN", "STATE", 15),
    (3, "TRAD", "Shares", "XHAN", "STATE", 3891),
    (3, "unknown", "Shares", "XHAN", "STATE", 2),
]

AUTO_TRADERS = [
    "SCLB0017, SCLB0020",
    "SCLB0017",
    "SCLB0020",
    "MMEU1001, MMEU1003",
    "QDRV014, QDRV019",
]

REQUEST_GROUPS = [
    ("EU_ETF_TOUCH", "ETF", "XHAN", "Touch", "Streaming", 120, 250_000, "Active"),
    ("EU_ETF_FALLBACK", "ETF", "XHAN", "Fallback", "On Demand", 250, 150_000, "Active"),
    ("EU_FUND_PRIMARY", "Fund", "XHAN", "Primary", "Streaming", 150, 100_000, "Active"),
    ("EU_ETC_FAST", "ETC", "XHAN", "Fast", "Streaming", 100, 80_000, "Review"),
    ("US_LARGE_CAP", "Shares", "XNAS", "Touch", "Streaming", 120, 350_000, "Active"),
    ("US_HEALTHCARE", "Shares", "BATS", "Touch", "Streaming", 140, 200_000, "Active"),
    ("JP_MOMENTUM", "Shares", "XTKS", "Adaptive", "Burst", 175, 175_000, "Review"),
    ("APAC_ETF", "ETF", "XHKG", "Touch", "Streaming", 160, 220_000, "Active"),
]

SETTINGS_ROWS = [
    ("Venue throttle", "XHAN", "120 ms", "Auto", True),
    ("Error escalation", "Global", "3 hard errors", "Pager + email", True),
    ("Inventory skew", "EU Shares", "0.35 beta", "Symmetric", True),
    ("Touch size cap", "ETF", "250000", "Static", True),
    ("Quote aging", "Global", "1250 ms", "Reject stale", True),
    ("Heartbeat monitor", "AutoTraders", "3 sec", "Drop + alert", True),
]


@dataclass
class SystemSnapshot:
    seed: int
    cycle: int
    summary: pd.DataFrame
    touch: pd.DataFrame
    groups: pd.DataFrame
    settings: pd.DataFrame
    events: pd.DataFrame


def _node_label(level: int, name: str) -> str:
    prefix = {0: "▾ ", 1: "  ▾ ", 2: "    ▾ ", 3: "      • "}[level]
    return f"{prefix}{name}"


def _severity(error_count: int, warn_count: int) -> str:
    if error_count >= 8:
        return "Critical"
    if error_count > 0:
        return "Error"
    if warn_count > 0:
        return "Warn"
    return "OK"


def _severity_icon(severity: str) -> str:
    mapping = {
        "Critical": "🔴 Critical",
        "Error": "🔴 Error",
        "Warn": "🟠 Warn",
        "OK": "🟢 OK",
    }
    return mapping[severity]


def _build_summary(seed: int, cycle: int, incident_level: float) -> pd.DataFrame:
    rng = np.random.default_rng(seed + cycle * 17)
    rows: list[dict[str, object]] = []
    for idx, (level, name, asset_class, venue, node_type, total) in enumerate(TREE_SPEC):
        row_seed = seed * 31 + cycle * 19 + idx * 7
        local_rng = np.random.default_rng(row_seed)
        inactive = int(max(0, round(local_rng.normal(0.8 if total > 30 else 0.2, 0.7))))
        incoming = int(max(0, round(local_rng.normal(0.4 if total > 80 else 0.1, 0.6))))
        enabled = max(total - inactive, 0)
        quotes = max(enabled - incoming, 0)

        structural_risk = 0.0
        if "HALTERR" in name:
            structural_risk = 0.95
        elif name in {"HALT", "SUSPMAN", "unknown"}:
            structural_risk = 0.6
        elif asset_class == "Shares" and level >= 2:
            structural_risk = 0.32
        elif asset_class == "Funds" and level >= 2:
            structural_risk = 0.18
        elif level == 0:
            structural_risk = 0.12

        raw_error = local_rng.poisson(max(total / 800, 0.15) * (0.35 + incident_level + structural_risk))
        raw_warn = local_rng.poisson(max(total / 950, 0.08) * (0.25 + structural_risk))
        raw_info = local_rng.poisson(max(total / 1000, 0.05) * 0.35)

        if name == "HALTERR":
            raw_error = max(raw_error, 6 + int(incident_level * 8))
        if name == "TRAD" and asset_class == "Shares":
            incoming = max(incoming, int(incident_level * 40))
            raw_warn = max(raw_warn, 3)
        if level == 0 and asset_class == "Shares":
            incoming = max(incoming, int(incident_level * 40))
            raw_error = max(raw_error, int(incident_level * 5))

        severity = _severity(raw_error, raw_warn)
        rows.append(
            {
                "row_key": f"{asset_class}_{venue}_{level}_{name}_{idx}",
                "node": _node_label(level, name),
                "node_name": name,
                "level": level,
                "asset_class": asset_class,
                "venue": venue,
                "node_type": node_type,
                "total": total,
                "enabled_count": enabled,
                "quotes": quotes,
                "inactive": inactive,
                "incoming": incoming,
                "error": _severity_icon(severity),
                "error_count": int(raw_error),
                "info_count": int(raw_info),
                "warn_count": int(raw_warn),
                "auto_traders": AUTO_TRADERS[idx % len(AUTO_TRADERS)],
                "send_q": bool(local_rng.integers(0, 10) > 1),
                "send_r": bool(local_rng.integers(0, 10) > 2),
                "send_qr": bool(local_rng.integers(0, 10) > 3),
                "enabled_flag": enabled > 0,
                "owner": ["Quoting", "Risk", "Coverage", "Ops"][idx % 4],
            }
        )

    return pd.DataFrame(rows)


def _build_touch(seed: int, cycle: int, incident_level: float) -> pd.DataFrame:
    rng = np.random.default_rng(seed + cycle * 29)
    products = [
        ("XS0000001001", "ALPHA_ETF", "ETF", "XHAN"),
        ("XS0000001002", "BRAVO_ETC", "ETC", "XHAN"),
        ("XS0000001003", "CROWN_FUND", "Fund", "XHAN"),
        ("DE000A1EWWW0", "DELTA_DE", "Shares", "XHAN"),
        ("US0000002002", "EVO_US", "Shares", "XNAS"),
        ("US0000002003", "FORUM_US", "Shares", "BATS"),
        ("JP0000003001", "GAIA_JP", "Shares", "XTKS"),
        ("JP0000003002", "HZN_JP", "ETF", "XHKG"),
        ("FR0000004001", "ION_FR", "Shares", "XPAR"),
        ("NL0000005001", "NOVA_NL", "ETF", "XAMS"),
        ("GB0000006001", "ORBIT_UK", "Shares", "XLON"),
        ("IT0000007001", "PULSE_IT", "ETP", "XMIL"),
    ]
    rows: list[dict[str, object]] = []
    for idx, (isin, symbol, product, venue) in enumerate(products):
        mid = round(float(rng.uniform(14, 235)), 2)
        spread_bps = round(float(rng.uniform(4.5, 24.0) * (1 + incident_level * 0.35)), 1)
        bid = round(mid * (1 - spread_bps / 20000), 2)
        ask = round(mid * (1 + spread_bps / 20000), 2)
        skew = round(float(rng.normal(0, 0.28)), 2)
        quote_age = int(max(35, rng.normal(480 + cycle * 25, 180)))
        stale = quote_age > 1100 or (idx % 7 == 0 and incident_level > 0.4)
        state = "HALTERR" if stale and idx % 5 == 0 else "TRAD" if not stale else "HALT"
        rows.append(
            {
                "row_key": f"{isin}_{venue}",
                "isin": isin,
                "symbol": symbol,
                "product": product,
                "venue": venue,
                "bid": bid,
                "ask": ask,
                "spread_bps": spread_bps,
                "quote_age_ms": quote_age,
                "state": state,
                "inventory_skew": skew,
                "auto_trader": AUTO_TRADERS[idx % len(AUTO_TRADERS)].split(",")[0],
                "hedge_mode": ["Auto", "Passive", "Paused"][idx % 3],
                "stale": stale,
                "enabled": idx % 9 != 0,
            }
        )
    return pd.DataFrame(rows)


def _build_groups(seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 503)
    rows: list[dict[str, object]] = []
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
    rows: list[dict[str, object]] = []
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


def _build_events(seed: int, cycle: int, summary: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(seed + cycle * 41)
    now = datetime(2026, 6, 18, 9, 30) + timedelta(minutes=cycle * 3)
    hot_rows = summary.sort_values(["error_count", "warn_count"], ascending=False).head(6)
    events: list[dict[str, object]] = []
    for idx, row in enumerate(hot_rows.itertuples(index=False)):
        severity = "ERROR" if row.error_count > 0 else "WARN" if row.warn_count > 0 else "INFO"
        message = (
            f"{row.node_name} on {row.venue}: "
            f"{row.error_count} hard errors, {row.warn_count} warnings, {row.incoming} incoming quote gaps."
        )
        events.append(
            {
                "time": (now - timedelta(seconds=idx * 37)).strftime("%H:%M:%S"),
                "severity": severity,
                "component": row.owner,
                "message": message,
            }
        )

    for extra_idx in range(4):
        events.append(
            {
                "time": (now - timedelta(seconds=(len(events) + extra_idx) * 23)).strftime("%H:%M:%S"),
                "severity": "INFO",
                "component": ["Heartbeat", "AutoTrader", "Scheduler"][extra_idx % 3],
                "message": [
                    "Heartbeat check completed for all venues.",
                    "Auto trader rotation refreshed for EU touch books.",
                    "Configuration checksum matches active release.",
                    "Quote request backlog remains within threshold.",
                ][extra_idx],
            }
        )

    return pd.DataFrame(events).sort_values("time", ascending=False).reset_index(drop=True)


def build_system_snapshot(seed: int = 11, cycle: int = 0, incident_level: float = 0.35) -> SystemSnapshot:
    summary = _build_summary(seed, cycle, incident_level)
    touch = _build_touch(seed, cycle, incident_level)
    groups = _build_groups(seed)
    settings = _build_settings(seed)
    events = _build_events(seed, cycle, summary)
    return SystemSnapshot(
        seed=seed,
        cycle=cycle,
        summary=summary,
        touch=touch,
        groups=groups,
        settings=settings,
        events=events,
    )


def advance_snapshot(snapshot: SystemSnapshot, incident_boost: float = 0.0) -> SystemSnapshot:
    next_cycle = snapshot.cycle + 1
    incident_level = min(1.2, 0.28 + next_cycle * 0.04 + incident_boost)
    return build_system_snapshot(seed=snapshot.seed, cycle=next_cycle, incident_level=incident_level)


def clear_alerts(snapshot: SystemSnapshot) -> SystemSnapshot:
    return build_system_snapshot(seed=snapshot.seed, cycle=snapshot.cycle, incident_level=0.08)


def system_metrics(summary: pd.DataFrame, touch: pd.DataFrame) -> dict[str, float]:
    return {
        "total_quotes": float(summary.loc[summary["level"] == 0, "total"].sum()),
        "enabled_quotes": float(summary.loc[summary["level"] == 0, "enabled_count"].sum()),
        "hard_errors": float(summary["error_count"].sum()),
        "warnings": float(summary["warn_count"].sum()),
        "stale_quotes": float(touch["stale"].sum()),
        "disabled_symbols": float((~touch["enabled"]).sum()),
    }
