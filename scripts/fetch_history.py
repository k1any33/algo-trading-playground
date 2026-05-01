"""Download USDJPY 4H historical data from IBKR and save to Parquet.

Usage:
    uv run python -m scripts.fetch_history
"""

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from backtest.data import fetch_and_save_history
from backtest.config import HISTORY_PARQUET

if __name__ == "__main__":
    print(f"Downloading USDJPY 4H history → {HISTORY_PARQUET}")
    print("Make sure IBKR TWS/Gateway is running on paper account.")
    fetch_and_save_history()
