"""Download USDJPY 4H historical data from IBKR and save to Parquet.

Usage:
    uv run python scripts/fetch_history.py
"""

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from src.data_feed import fetch_and_save_history
from src.config import HISTORY_PARQUET

if __name__ == "__main__":
    print(f"Downloading USDJPY 4H history → {HISTORY_PARQUET}")
    print("Make sure IBKR TWS/Gateway is running on paper account.")
    fetch_and_save_history()
