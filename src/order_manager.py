"""Order dataclass and OrderManager.

Flow:
  Strategy → Signal → OrderManager.process_signals() → Order (PENDING)
  ExecutionEngine fills PENDING → OPEN (live: IBKR callbacks; backtest: fill simulator)
  OrderManager.on_bar() checks OPEN orders for stop/TP exits (backtest only —
    live trading uses IBKR bracket orders which handle exits broker-side)
"""

import uuid
import logging
from dataclasses import dataclass, field
from typing import Literal, Optional

import pandas as pd

from src.base_strategy import Signal
from src import config

logger = logging.getLogger(__name__)


@dataclass
class Order:
    order_id: str
    symbol: str
    direction: Literal["BUY", "SELL"]
    quantity: float
    entry_price: float
    stop_price: float
    take_profit_price: float
    status: Literal["PENDING", "OPEN", "CLOSED", "CANCELLED"] = "PENDING"
    group_id: Optional[str] = None
    filled_price: Optional[float] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[Literal["stop", "take_profit"]] = None
    metadata: dict = field(default_factory=dict)


class OrderManager:
    def __init__(
        self,
        risk_per_trade: float = config.RISK_PER_TRADE,
    ) -> None:
        self.risk_per_trade = risk_per_trade
        self._orders: list[Order] = []

    # ── Public API ────────────────────────────────────────────────────────────

    def process_signals(self, signals: list[Signal], equity: float) -> list[Order]:
        """Convert signals into Orders and register them as PENDING."""
        new_orders = []
        for signal in signals:
            order = self._build_order(signal, equity)
            if order is not None:
                self._orders.append(order)
                new_orders.append(order)
                logger.info(
                    "Order created [%s] %s %s qty=%.2f entry=%.4f stop=%.4f tp=%.4f",
                    order.order_id[:8], order.direction, order.symbol,
                    order.quantity, order.entry_price, order.stop_price, order.take_profit_price,
                )
        return new_orders

    def on_bar(self, bar: pd.Series) -> list[Order]:
        """Check OPEN orders for stop/TP exits.

        Used in backtesting only — live trading relies on IBKR bracket orders.
        bar must have: high, low.
        Returns orders whose status changed to CLOSED this bar.
        """
        return self._check_exits(bar)


    @property
    def open_orders(self) -> list[Order]:
        return [o for o in self._orders if o.status in ("PENDING", "OPEN")]

    @property
    def all_orders(self) -> list[Order]:
        return list(self._orders)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _build_order(self, signal: Signal, equity: float) -> Optional[Order]:
        if any(o.symbol == signal.symbol and o.status in ("PENDING", "OPEN")
               for o in self._orders):
            logger.debug("Signal skipped — position already open for %s", signal.symbol)
            return None

        entry_px: Optional[float] = signal.metadata.get("entry_px")
        stop_dist: Optional[float] = signal.metadata.get("stop_dist")

        if entry_px is None or stop_dist is None:
            logger.warning("Signal missing entry_px or stop_dist in metadata — skipped")
            return None

        if stop_dist == 0:
            logger.warning("Signal has zero stop_dist — skipped")
            return None

        direction: Literal["BUY", "SELL"] = "BUY" if signal.direction == "LONG" else "SELL"
        quantity = (equity * self.risk_per_trade) / stop_dist

        return Order(
            order_id=str(uuid.uuid4()),
            symbol=signal.symbol,
            direction=direction,
            quantity=quantity,
            entry_price=entry_px,
            stop_price=signal.stop_price,
            take_profit_price=signal.take_profit_price,
            group_id=signal.group_id,
            metadata={"signal_timestamp": str(signal.timestamp)},
        )

    def _check_exits(self, bar: pd.Series) -> list[Order]:
        """Stop takes priority if both stop and TP are hit in the same bar."""
        closed: list[Order] = []
        hi = float(bar["high"])
        lo = float(bar["low"])

        for order in self._orders:
            if order.status != "OPEN":
                continue

            exit_price: Optional[float] = None
            exit_reason: Optional[Literal["stop", "take_profit"]] = None

            if order.direction == "BUY":
                if lo <= order.stop_price:
                    exit_price, exit_reason = order.stop_price, "stop"
                elif hi >= order.take_profit_price:
                    exit_price, exit_reason = order.take_profit_price, "take_profit"
            else:
                if hi >= order.stop_price:
                    exit_price, exit_reason = order.stop_price, "stop"
                elif lo <= order.take_profit_price:
                    exit_price, exit_reason = order.take_profit_price, "take_profit"

            if exit_price is not None:
                order.exit_price = exit_price
                order.exit_reason = exit_reason
                order.status = "CLOSED"
                closed.append(order)
                logger.info(
                    "Order closed [%s] via %s at %.4f",
                    order.order_id[:8], exit_reason, exit_price,
                )

        return closed
