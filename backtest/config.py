"""Backtest-only configuration — not deployed to live trading."""

import pathlib

from src.config import ROOT_DIR

# ── Historical data ───────────────────────────────────────────────────────────
HISTORY_START_DATE = "2022-01-01"
HISTORY_END_DATE   = None           # None = fetch until today

DATA_DIR        = ROOT_DIR / "data"
HISTORY_PARQUET = DATA_DIR / "USDJPY_4hours.parquet"

# ── Strategy parameters ───────────────────────────────────────────────────────
FISHER_PERIOD = 10
FISHER_THRESH = 1.5
MA_PERIOD     = 20
RR_MULTIPLE   = 2.0
PIP_SIZE      = 0.01

# ── Risk management ───────────────────────────────────────────────────────────
RISK_PER_TRADE = 0.01
MIN_STOP_PIPS  = 5

# ── Simulation ────────────────────────────────────────────────────────────────
SPREAD_PIPS = 1.0
