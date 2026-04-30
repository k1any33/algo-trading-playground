import os
from dotenv import load_dotenv

load_dotenv()

# ── IBKR connection ───────────────────────────────────────────────────────────
IBKR_HOST      = os.getenv("IBKR_HOST", "127.0.0.1")
IBKR_PORT      = int(os.getenv("IBKR_PORT", "4002"))
IBKR_CLIENT_ID = int(os.getenv("IBKR_CLIENT_ID", "1"))
DRY_RUN        = os.getenv("DRY_RUN", "true").lower() == "true"

# ── Instrument ────────────────────────────────────────────────────────────────
SYMBOL       = "USDJPY"
CURRENCY     = "USD"
BAR_SIZE     = "4 hours"
HISTORY_BARS = 60   # bars loaded per cycle (enough for warmup + lookback)

# ── Strategy parameters ───────────────────────────────────────────────────────
FISHER_PERIOD = 10
FISHER_THRESH = 1.5
MA_PERIOD     = 20
RR_MULTIPLE   = 2.0
SPREAD_PIPS   = 1.0
PIP_SIZE      = 0.01   # 1 pip = 0.01 for JPY pairs

# ── Risk management ───────────────────────────────────────────────────────────
RISK_PER_TRADE = 0.01   # 1% of account equity per trade
MIN_STOP_PIPS  = 5      # ignore signals with stop < 5 pips

# ── Paths ─────────────────────────────────────────────────────────────────────
import pathlib
ROOT_DIR          = pathlib.Path(__file__).parent.parent
DATA_DIR          = ROOT_DIR / "data"
LOG_DIR           = ROOT_DIR / "logs"
POSITION_FILE     = ROOT_DIR / "position_state.json"
HISTORY_PARQUET   = DATA_DIR / "USDJPY_4hours.parquet"
