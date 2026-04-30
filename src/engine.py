"""Main trading engine — runs one cycle per 4-hour bar close.

Cycle logic:
  1. Fetch latest N bars from IBKR
  2. If position open → check for exit
  3. If flat → check for entry signal → place bracket order
  4. Persist position state to disk
"""

import asyncio
import logging
from datetime import datetime, timezone

from ib_async import IB

from src import config, position_manager
from src.data_feed import fetch_latest_bars
from src.strategy import generate_signal, check_exit
from src.execution import place_bracket_order, cancel_all_orders, get_account_equity, compute_quantity

logger = logging.getLogger(__name__)


async def run_cycle(ib: IB) -> None:
    now = datetime.now(timezone.utc)
    logger.info("── Cycle start %s ──", now.strftime("%Y-%m-%d %H:%M UTC"))

    # 1. Fetch bars
    try:
        df = await fetch_latest_bars(ib, n_bars=config.HISTORY_BARS)
    except Exception as e:
        logger.error("Bar fetch failed: %s", e)
        return

    # 2. Check open position exit
    position = position_manager.load()

    if position is not None:
        reason, exit_px = check_exit(df, position)
        if reason is not None:
            logger.info(
                "EXIT %s @ %.4f (%s) | entry was %.4f | stop_dist %.4f",
                position["side"].upper(), exit_px, reason,
                position["entry_px"], position["stop_dist"],
            )
            position_manager.clear()
            # In dry-run the bracket order already managed exit; in live, IBKR handles it.
            return
        else:
            logger.info(
                "Position OPEN: %s entry=%.4f stop=%.4f tgt_rr=%.4f",
                position["side"].upper(),
                position["entry_px"], position["stop_px"], position["target_rr"],
            )
            return

    # 3. Check for entry signal
    signal = generate_signal(df)

    if signal is None:
        logger.info("No signal this bar.")
        return

    logger.info(
        "SIGNAL %s | entry~%.4f stop=%.4f tgt_rr=%.4f tgt_ma=%.4f",
        signal.side.upper(), signal.entry_px,
        signal.stop_px, signal.target_rr, signal.target_ma,
    )

    # Use the tighter of the two targets
    if signal.side == "short":
        target_px = max(signal.target_rr, signal.target_ma)
    else:
        target_px = min(signal.target_rr, signal.target_ma)

    # 4. Size and place order
    try:
        equity = await get_account_equity(ib)
    except Exception as e:
        logger.error("Could not fetch account equity: %s — using $10,000 fallback", e)
        equity = 10_000.0

    qty = compute_quantity(equity, signal.stop_dist)

    order_ids = await place_bracket_order(
        ib,
        side=signal.side,
        qty=qty,
        stop_px=signal.stop_px,
        target_px=target_px,
    )

    # 5. Persist position state
    position_manager.save({
        "side":      signal.side,
        "entry_px":  signal.entry_px,
        "stop_px":   signal.stop_px,
        "target_rr": signal.target_rr,
        "target_ma": signal.target_ma,
        "stop_dist": signal.stop_dist,
        "qty":       qty,
        **order_ids,
    })


async def run_forever() -> None:
    """Connect to IBKR once and run cycles on the 4-hour bar schedule."""
    ib = IB()
    ib.connect(config.IBKR_HOST, config.IBKR_PORT, clientId=config.IBKR_CLIENT_ID)
    logger.info(
        "Connected to IBKR %s:%d (paper=%s, dry_run=%s)",
        config.IBKR_HOST, config.IBKR_PORT,
        config.IBKR_PORT in (7497, 4002),
        config.DRY_RUN,
    )

    try:
        while True:
            await run_cycle(ib)
            # Sleep until the next 4H bar boundary (align to 00, 04, 08, 12, 16, 20 UTC)
            now = datetime.now(timezone.utc)
            minutes_into_4h = (now.hour % 4) * 60 + now.minute
            seconds_to_next = (4 * 60 - minutes_into_4h) * 60 - now.second + 30  # +30s buffer
            logger.info("Sleeping %.0f minutes until next bar …", seconds_to_next / 60)
            await asyncio.sleep(seconds_to_next)
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    finally:
        ib.disconnect()
        logger.info("Disconnected from IBKR")
