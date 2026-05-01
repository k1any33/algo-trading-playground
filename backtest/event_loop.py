"""Backtest event loop — iterates over historical bars and orchestrates all components.

Bar processing order per iteration:
  1. Fill PENDING orders at bar open (execution_engine.on_bar)
  2. Check OPEN orders for stop/TP exits (order_manager.on_bar) → record closed trades
  3. Generate signals on bars up to this bar (strategy.generate_signals)
  4. Convert signals → orders (order_manager.process_signals)
  5. Submit new orders — fills at next bar's open
"""

import asyncio
import logging

import pandas as pd

from backtest.execution_engine import BacktestExecutionEngine
from src.base_strategy import Strategy
from src.order_manager import OrderManager
from src.portfolio import Portfolio

logger = logging.getLogger(__name__)


async def run(
    df: pd.DataFrame,
    strategy: Strategy,
    order_manager: OrderManager,
    execution_engine: BacktestExecutionEngine,
    portfolio: Portfolio,
) -> Portfolio:
    """Run a full backtest over df and return the completed Portfolio.

    df must have columns: open, high, low, close with a datetime index.
    """
    logger.info("Backtest starting — %d bars from %s to %s", len(df), df.index[0], df.index[-1])

    for i in range(1, len(df)):
        bar = df.iloc[i]
        timestamp = df.index[i]

        # 1. Fill any orders queued on the previous bar
        execution_engine.on_bar(bar)

        # 2. Check open positions for exits
        closed_orders = order_manager.on_bar(bar)
        for order in closed_orders:
            portfolio.record_close(order, timestamp)

        # 3. Generate signals on all bars up to and including this one
        df_slice = df.iloc[: i + 1]
        signals = strategy.generate_signals(df_slice)

        if not signals:
            continue

        # 4 & 5. Size orders and queue them — fills at next bar's open
        equity = await execution_engine.get_equity()
        new_orders = order_manager.process_signals(signals, equity)
        for order in new_orders:
            await execution_engine.submit(order)

    logger.info(
        "Backtest complete — %d trades | final equity: %.2f",
        len(portfolio.trade_history), portfolio.equity,
    )
    return portfolio
