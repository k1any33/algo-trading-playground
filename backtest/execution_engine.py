"""Backtest execution engine — simulates fills for historical simulation.

submit() queues an order as PENDING.
on_bar() fills all PENDING orders at bar open, simulating a market order
on the bar following the signal bar.
"""

import logging

import pandas as pd

from src.execution_engine import ExecutionEngine
from src.order_manager import Order
from src.portfolio import Portfolio

logger = logging.getLogger(__name__)


class BacktestExecutionEngine(ExecutionEngine):
    def __init__(self, portfolio: Portfolio) -> None:
        self._portfolio = portfolio
        self._orders: list[Order] = []

    async def submit(self, order: Order) -> None:
        self._orders.append(order)
        logger.debug(
            "Queued [%s] %s %s", order.order_id[:8], order.direction, order.symbol
        )

    async def get_equity(self) -> float:
        return self._portfolio.equity

    def on_bar(self, bar: pd.Series) -> None:
        """Fill PENDING orders at bar open.

        Called by the backtest EventLoop at the start of each bar, before
        strategy evaluation, so orders generated on bar N fill at bar N+1 open.
        """
        open_px = float(bar["open"])
        for order in self._orders:
            if order.status == "PENDING":
                order.filled_price = open_px
                order.status = "OPEN"
                logger.debug(
                    "Filled [%s] at %.4f (bar open)", order.order_id[:8], open_px
                )
