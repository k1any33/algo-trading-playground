"""Live trading event loop — connects to IBKR and runs on the 4H bar schedule.

Cycle per bar close:
  1. Fetch latest bars from IBKR
  2. Generate signals
  3. Convert signals → orders
  4. Submit orders to IBKR (bracket orders handle stop/TP broker-side)

Portfolio.record_close() for live trades is a TODO — requires wiring up IBKR
bracket fill callbacks in IBKRExecutionEngine to notify the event loop.
"""

import asyncio
import logging
from datetime import datetime, timezone

from ib_async import IB

from src import config
from src.base_strategy import Strategy
from src.data_feed import fetch_latest_bars
from src.ibkr_execution_engine import IBKRExecutionEngine
from src.order_manager import OrderManager
from src.portfolio import Portfolio

logger = logging.getLogger(__name__)


async def run(
    strategy: Strategy,
    order_manager: OrderManager,
    execution_engine: IBKRExecutionEngine,
    portfolio: Portfolio,
    ib: IB,
) -> None:
    """Run the live event loop indefinitely until interrupted."""
    logger.info(
        "Connected to IBKR %s:%d", config.IBKR_HOST, config.IBKR_PORT
    )

    try:
        while True:
            await _run_cycle(strategy, order_manager, execution_engine, portfolio, ib)
            await _sleep_until_next_bar()
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    finally:
        ib.disconnect()
        logger.info("Disconnected from IBKR")


async def _run_cycle(
    strategy: Strategy,
    order_manager: OrderManager,
    execution_engine: IBKRExecutionEngine,
    portfolio: Portfolio,
    ib: IB,
) -> None:
    now = datetime.now(timezone.utc)
    logger.info("── Cycle start %s ──", now.strftime("%Y-%m-%d %H:%M UTC"))

    try:
        df = await fetch_latest_bars(ib, n_bars=config.HISTORY_BARS)
    except Exception as e:
        logger.error("Bar fetch failed: %s — skipping cycle", e)
        return

    signals = strategy.generate_signals(df)
    if not signals:
        logger.info("No signal this bar.")
        return

    equity = await execution_engine.get_equity()
    new_orders = order_manager.process_signals(signals, equity)

    for order in new_orders:
        await execution_engine.submit(order)


async def _sleep_until_next_bar() -> None:
    """Sleep until the next 4H bar boundary (00, 04, 08, 12, 16, 20 UTC) + 30s buffer."""
    now = datetime.now(timezone.utc)
    minutes_into_4h = (now.hour % 4) * 60 + now.minute
    seconds_to_next = (4 * 60 - minutes_into_4h) * 60 - now.second + 30
    logger.info("Sleeping %.0f minutes until next bar …", seconds_to_next / 60)
    await asyncio.sleep(seconds_to_next)
