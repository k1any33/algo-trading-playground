"""Download historical bars from IBKR and save to Parquet for backtesting."""

import asyncio
import logging
from datetime import datetime, timezone

from ib_async import IB

from backtest import config
from src import config as live_config
from src.data_feed import _fetch_bars_in_range

logger = logging.getLogger(__name__)


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
    ib.connect(live_config.IBKR_HOST, live_config.IBKR_PORT, clientId=live_config.IBKR_CLIENT_ID + 1)
    try:
        loop = asyncio.get_event_loop()
        df = loop.run_until_complete(_fetch_bars_in_range(ib, start_dt, end_dt))
        df.to_parquet(output_path)
        logger.info("Saved %d bars → %s", len(df), output_path)
        logger.info("Date range: %s → %s", df.index.min(), df.index.max())
    finally:
        ib.disconnect()
