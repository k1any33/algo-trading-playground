"""Portfolio — tracks trade history and equity across live and backtest runs."""

import logging
from dataclasses import dataclass
from typing import Literal, Optional

import pandas as pd

from src.order_manager import Order

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    order_id: str
    symbol: str
    direction: Literal["BUY", "SELL"]
    quantity: float
    filled_price: float
    exit_price: float
    exit_reason: Literal["stop", "take_profit"]
    pnl: float
    closed_at: pd.Timestamp


class Portfolio:
    def __init__(self, starting_capital: float) -> None:
        self._starting_capital = starting_capital
        self._trades: list[TradeRecord] = []
        self._equity_curve: list[tuple[pd.Timestamp, float]] = []

    # ── Public API ────────────────────────────────────────────────────────────

    def record_close(self, order: Order, timestamp: pd.Timestamp) -> None:
        """Record a completed trade and update the equity curve."""
        if order.filled_price is None or order.exit_price is None or order.exit_reason is None:
            logger.warning("record_close called on incomplete order [%s] — skipped", order.order_id[:8])
            return

        pnl = self._compute_pnl(order)
        record = TradeRecord(
            order_id=order.order_id,
            symbol=order.symbol,
            direction=order.direction,
            quantity=order.quantity,
            filled_price=order.filled_price,
            exit_price=order.exit_price,
            exit_reason=order.exit_reason,
            pnl=pnl,
            closed_at=timestamp,
        )
        self._trades.append(record)
        self._equity_curve.append((timestamp, self.equity))

        logger.info(
            "Trade closed [%s] %s %s pnl=%.2f equity=%.2f",
            order.order_id[:8], order.direction, order.symbol, pnl, self.equity,
        )

    @property
    def equity(self) -> float:
        return self._starting_capital + sum(t.pnl for t in self._trades)

    @property
    def trade_history(self) -> list[TradeRecord]:
        return list(self._trades)

    @property
    def equity_curve(self) -> list[tuple[pd.Timestamp, float]]:
        return list(self._equity_curve)

    def to_dataframe(self) -> pd.DataFrame:
        if not self._trades:
            return pd.DataFrame()
        return pd.DataFrame([vars(t) for t in self._trades])

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _compute_pnl(order: Order) -> float:
        if order.direction == "BUY":
            return (order.exit_price - order.filled_price) * order.quantity
        else:
            return (order.filled_price - order.exit_price) * order.quantity
