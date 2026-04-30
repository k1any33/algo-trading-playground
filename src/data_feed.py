"""Fetch historical 4H USD/JPY bars from IBKR and return as a DataFrame.

Used both for the initial history download (scripts/fetch_history.py)
and the live engine's per-cycle bar refresh.
"""

import asyncio
import logging
from datetime import datetime, timezone

import pandas as pd
from ib_async import IB, Forex, BarDataList

from src import config

logger = logging.getLogger(__name__)


def _make_contract() -> Forex:
    return Forex(config.SYMBOL)


async def _fetch_bars(ib: IB, n_bars: int, end_dt: str = "") -> pd.DataFrame:
    contract = _make_contract()
    await ib.qualifyContractsAsync(contract)

    # IBKR pacing: max 2000 bars per request for 4H
    # Each 4H bar = 4 hours, so n_bars * 4 hours of data
    # Express as days for the duration string
    duration_days = max(1, (n_bars * 4) // 24 + 2)
    duration_str  = f"{duration_days} D"

    bars: BarDataList = await ib.reqHistoricalDataAsync(
        contract,
        endDateTime=end_dt,
        durationStr=duration_str,
        barSizeSetting=config.BAR_SIZE,
        whatToShow="MIDPOINT",
        useRTH=False,
        formatDate=2,   # UTC timestamps
        keepUpToDate=False,
    )

    if not bars:
        raise RuntimeError("IBKR returned no bars — check connection and instrument")

    df = pd.DataFrame([
        {
            "timestamp": b.date,
            "open":  b.open,
            "high":  b.high,
            "low":   b.low,
            "close": b.close,
            "volume": b.volume,
        }
        for b in bars
    ])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df.set_index("timestamp", inplace=True)
    df.sort_index(inplace=True)
    df = df[~df.index.duplicated(keep="last")]
    return df.tail(n_bars)


def fetch_bars(n_bars: int = config.HISTORY_BARS) -> pd.DataFrame:
    """Synchronous wrapper — connects, fetches, disconnects."""
    ib = IB()
    ib.connect(config.IBKR_HOST, config.IBKR_PORT, clientId=config.IBKR_CLIENT_ID)
    try:
        loop = asyncio.get_event_loop()
        df = loop.run_until_complete(_fetch_bars(ib, n_bars))
        logger.info("Fetched %d bars (latest: %s)", len(df), df.index[-1])
        return df
    finally:
        ib.disconnect()


async def fetch_bars_async(ib: IB, n_bars: int = config.HISTORY_BARS) -> pd.DataFrame:
    """Async version for use inside an already-connected IB session."""
    return await _fetch_bars(ib, n_bars)


def fetch_and_save_history(output_path=config.HISTORY_PARQUET, n_bars: int = 2000) -> None:
    """Download full history and save to Parquet."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ib = IB()
    ib.connect(config.IBKR_HOST, config.IBKR_PORT, clientId=config.IBKR_CLIENT_ID + 1)
    try:
        loop = asyncio.get_event_loop()
        df = loop.run_until_complete(_fetch_bars(ib, n_bars))
        df.to_parquet(output_path)
        print(f"Saved {len(df)} bars → {output_path}")
        print(f"Date range: {df.index.min()} → {df.index.max()}")
    finally:
        ib.disconnect()
