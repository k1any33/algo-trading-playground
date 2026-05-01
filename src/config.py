import os
import pathlib
from dotenv import load_dotenv

load_dotenv()

# ── IBKR connection ───────────────────────────────────────────────────────────
IBKR_HOST      = os.getenv("IBKR_HOST", "127.0.0.1")
IBKR_PORT      = int(os.getenv("IBKR_PORT", "7496"))
IBKR_CLIENT_ID = int(os.getenv("IBKR_CLIENT_ID", "1"))
DRY_RUN        = os.getenv("DRY_RUN", "true").lower() == "true"

# ── Instrument ────────────────────────────────────────────────────────────────
SYMBOL       = "USDJPY"
CURRENCY     = "USD"
BAR_SIZE     = "4 hours"
HISTORY_BARS = 60   # bars fetched per live cycle (warmup + lookback)

# ── Strategy parameters ───────────────────────────────────────────────────────
FISHER_PERIOD = 10
FISHER_THRESH = 1.5
MA_PERIOD     = 20
RR_MULTIPLE   = 2.0
PIP_SIZE      = 0.01   # 1 pip = 0.01 for JPY pairs

# ── Risk management ───────────────────────────────────────────────────────────
RISK_PER_TRADE = 0.01   # 1% of account equity per trade
MIN_STOP_PIPS  = 5

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT_DIR = pathlib.Path(__file__).parent.parent
LOG_DIR  = ROOT_DIR / "logs"
