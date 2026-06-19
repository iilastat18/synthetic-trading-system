<div align="center">
  <h1>Synthetic Market Maker System</h1>
  <p><strong>A single-screen synthetic market-maker terminal with live ISIN movement, inventory drift, and hedge workflows.</strong></p>
  <p>Designed to feel closer to a trader front-end than a simple dashboard or buy/sell demo.</p>
</div>

<p align="center">
  <code>market moving</code>
  <code>isin changes</code>
  <code>inventory drift</code>
  <code>hedge console</code>
  <code>system UI</code>
  <code>public-safe synthetic data</code>
</p>

## Portfolio Role

This is the most visually ambitious system in the portfolio. It is the repo that most clearly signals trader-workstation thinking: live state, changing numbers, hedge actions, and dense terminal-style layout.

## Preview

![Synthetic market maker terminal](assets/terminal-home.png)

## What This Project Is

This repo is a public-safe product demo inspired by internal market-making systems.

It focuses on:

1. a live `Market Moving` panel showing regional synthetic market motion
2. an `ISIN Changes` panel showing selected symbol drift over time
3. synthetic inventory drift from market-making flow
4. symbol-level and region-level hedge actions
5. a manual hedge ticket and basket override workflow
6. dense terminal-style tables and event feeds around the trader workflow

## Why This Version Is Stronger

This tells a more realistic story than a basic trading page because it shows:

- a monitored book, not just a trade form
- inventory building up over time
- hedge decisions made inside the same workstation
- system behavior that keeps moving while the trader reacts

## Main Surfaces

| Surface | Purpose |
| --- | --- |
| `Market Moving` | Top-left regional market motion driven by live synthetic history |
| `ISIN Changes` | Bottom-left selected symbol tape with price and inventory history |
| `Trader Console` | Hedge selected symbol or region, send a manual hedge ticket, and override basket mapping |
| `Regional Risk` | Hedge basket positions and region-level post-hedge exposure |
| `Live ISIN Board` | Dense table for the whole synthetic book, closer to a real front-end terminal |
| `cover.py` | Screenshot-friendly landing page for README and portfolio use |

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
# optional screenshot / README cover
streamlit run cover.py
```

## Project Structure

```text
synthetic-trading-system/
├── app.py
├── cover.py
├── README.md
├── requirements.txt
└── src/
    ├── mm_system.py
    ├── quote_monitor.py
    ├── ui.py
    ├── engine.py
    ├── market.py
    ├── showcase.py
    └── __init__.py
```

## Notes

- All quotes, instruments, ISINs, venues, inventory, baskets, and incidents are synthetic.
- The goal is to demonstrate internal-tool and trader-workstation product design, not reproduce proprietary company logic.
- The live feed uses timed page refresh so the system feels active and continuously monitored.
- The app is intentionally single-page so it feels like a terminal, not a multi-page dashboard site.

## Screenshot Strategy

- use `cover.py` for the README hero image
- use one full-screen shot of `app.py` showing `Market Moving`, `ISIN Changes`, and the trader console together
- crop screenshots tightly so the app reads like a terminal, not like a generic browser page
