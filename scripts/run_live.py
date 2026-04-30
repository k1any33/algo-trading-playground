"""Start the live (paper) trading engine.

Usage:
    uv run python scripts/run_live.py

Set DRY_RUN=false in .env when ready to place real paper orders.
Default: DRY_RUN=true (signal generation only, no orders placed).
"""

import asyncio
import logging
import sys
from pathlib import Path

# Configure logging to both stdout and file
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_dir / "trading.log"),
    ],
)

from src import config
from src.engine import run_forever

if __name__ == "__main__":
    print(f"Starting Fisher Mean-Rev bot")
    print(f"  Instrument : {config.SYMBOL}  {config.BAR_SIZE}")
    print(f"  IBKR       : {config.IBKR_HOST}:{config.IBKR_PORT}")
    print(f"  DRY RUN    : {config.DRY_RUN}")
    print()

    asyncio.run(run_forever())
