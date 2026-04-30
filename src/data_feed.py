"""Fetch historical 4H USD/JPY bars from IBKR and return as a DataFrame.

Used both for the initial history download (scripts/fetch_history.py)
and the live engine's per-cycle bar refresh.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import pandas as pd
from ib_async import IB, Forex, BarDataList

from src import config

logger = logging.getLogger(__name__)


def _make_contract() -> Forex:
    return Forex(config.SYMBOL)


async def fetch_latest_bars(ib: IB, n_bars: int = config.HISTORY_BARS) -> pd.DataFrame:
    """Async version for use inside an already-connected IB session."""
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(hours=n_bars * 4)
    return await _fetch_bars_in_range(ib, start_dt, end_dt)


async def _fetch_bars_in_range(ib: IB, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    """Fetch all bars between start_dt and end_dt, paginating backwards as needed."""
    contract = _make_contract()
    await ib.qualifyContractsAsync(contract)

    all_frames: list[pd.DataFrame] = []
    current_end = end_dt

    while True:
        end_str = current_end.strftime("%Y%m%d %H:%M:%S") + " UTC"

        duration_days = min(365, (current_end - start_dt).days + 2)
        bars: BarDataList = await ib.reqHistoricalDataAsync(
            contract,
            endDateTime=end_str,
            durationStr=f"{duration_days} D",
            barSizeSetting=config.BAR_SIZE,
            whatToShow="MIDPOINT",
            useRTH=False,
            formatDate=2,
            keepUpToDate=False,
        )

        if not bars:
            break

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

        all_frames.append(df)
        logger.info("Fetched page: %d bars (%s → %s)", len(df), df.index.min(), df.index.max())

        if df.index.min() <= start_dt:
            break

        current_end = df.index.min().to_pydatetime()
        await asyncio.sleep(10)

    if not all_frames:
        raise RuntimeError("IBKR returned no bars — check connection and instrument")

    combined = pd.concat(all_frames)
    combined = combined[~combined.index.duplicated(keep="last")]
    combined.sort_index(inplace=True)
    return combined[combined.index >= start_dt]


def fetch_and_save_history(
    start_date: str = config.HISTORY_START_DATE,
    end_date: str | None = config.HISTORY_END_DATE,
    output_path=config.HISTORY_PARQUET,
) -> None:
    """Download history between start_date and end_date and save to Parquet."""
    start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end_dt = (
        datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if end_date
        else datetime.now(timezone.utc)
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    ib = IB()
    ib.connect(config.IBKR_HOST, config.IBKR_PORT, clientId=config.IBKR_CLIENT_ID + 1)
    try:
        loop = asyncio.get_event_loop()
        df = loop.run_until_complete(_fetch_bars_in_range(ib, start_dt, end_dt))
        df.to_parquet(output_path)
        print(f"Saved {len(df)} bars → {output_path}")
        print(f"Date range: {df.index.min()} → {df.index.max()}")
    finally:
        ib.disconnect()
