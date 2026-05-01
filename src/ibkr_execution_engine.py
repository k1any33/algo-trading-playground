"""IBKR live execution engine.

Submits bracket orders (MKT entry + STP stop + LMT take-profit) via ib_async.
Order lifecycle is driven entirely by IBKR callbacks:
  - Entry fill  → PENDING → OPEN      (_on_order_status)
  - Stop/TP fill → OPEN   → CLOSED    (_on_order_status) → portfolio.record_close()
  - Other bracket leg is cancelled automatically by the OCA group.
"""

import logging
import math
from typing import Literal

import pandas as pd
from ib_async import IB, Forex, LimitOrder, MarketOrder, StopOrder, Trade

from src.execution_engine import ExecutionEngine
from src.order_manager import Order
from src.portfolio import Portfolio

logger = logging.getLogger(__name__)


class IBKRExecutionEngine(ExecutionEngine):
    def __init__(self, ib: IB, portfolio: Portfolio) -> None:
        self._ib = ib
        self._portfolio = portfolio
        # IBKR entry orderId → our Order (tracks fills for entry leg)
        self._pending_entries: dict[int, Order] = {}
        # IBKR bracket leg orderId → (our Order, exit reason)
        self._bracket_legs: dict[int, tuple[Order, Literal["stop", "take_profit"]]] = {}
        ib.orderStatusEvent += self._on_order_status

    async def submit(self, order: Order) -> None:
        contract = Forex(order.symbol)
        await self._ib.qualifyContractsAsync(contract)

        qty = max(1, math.floor(order.quantity))
        close_action = "SELL" if order.direction == "BUY" else "BUY"

        entry = MarketOrder(order.direction, qty)
        entry.transmit = False

        stop = StopOrder(close_action, qty, round(order.stop_price, 5))
        stop.parentId = entry.orderId
        stop.transmit = False

        take_profit = LimitOrder(close_action, qty, round(order.take_profit_price, 5))
        take_profit.parentId = entry.orderId
        oca_group = f"TP_SL_{entry.orderId}"
        stop.ocaGroup = oca_group
        stop.ocaType = 1
        take_profit.ocaGroup = oca_group
        take_profit.ocaType = 1
        take_profit.transmit = True  # transmits all three legs

        entry_trade: Trade = self._ib.placeOrder(contract, entry)
        stop_trade: Trade = self._ib.placeOrder(contract, stop)
        tp_trade: Trade = self._ib.placeOrder(contract, take_profit)

        self._pending_entries[entry_trade.order.orderId] = order
        self._bracket_legs[stop_trade.order.orderId] = (order, "stop")
        self._bracket_legs[tp_trade.order.orderId] = (order, "take_profit")

        logger.info(
            "Placed %s bracket on %s: qty=%d stop=%.4f tp=%.4f",
            order.direction, order.symbol, qty, order.stop_price, order.take_profit_price,
        )

    async def get_equity(self) -> float:
        account_values = await self._ib.accountValuesAsync()
        for v in account_values:
            if v.tag == "NetLiquidation" and v.currency == "USD":
                return float(v.value)
        raise RuntimeError("Could not retrieve NetLiquidation from IBKR")

    def _on_order_status(self, trade: Trade) -> None:
        if trade.orderStatus.status != "Filled":
            return

        ibkr_order_id = trade.order.orderId

        # Entry leg filled → PENDING → OPEN
        order = self._pending_entries.pop(ibkr_order_id, None)
        if order is not None:
            order.filled_price = trade.orderStatus.avgFillPrice
            order.status = "OPEN"
            logger.info("Entry filled [%s] at %.4f", order.order_id[:8], order.filled_price)
            return

        # Bracket leg (stop or TP) filled → OPEN → CLOSED
        bracket = self._bracket_legs.pop(ibkr_order_id, None)
        if bracket is not None:
            order, exit_reason = bracket
            order.exit_price = trade.orderStatus.avgFillPrice
            order.exit_reason = exit_reason
            order.status = "CLOSED"

            # Remove the sibling leg — it will be cancelled by the OCA group
            # but we clean up our dict to avoid a stale callback
            sibling_keys = [k for k, (o, _) in self._bracket_legs.items() if o is order]
            for k in sibling_keys:
                del self._bracket_legs[k]

            timestamp = self._fill_timestamp(trade)
            self._portfolio.record_close(order, timestamp)
            logger.info(
                "Bracket closed [%s] via %s at %.4f",
                order.order_id[:8], exit_reason, order.exit_price,
            )

    @staticmethod
    def _fill_timestamp(trade: Trade) -> pd.Timestamp:
        if trade.fills:
            return pd.Timestamp(trade.fills[-1].time, tz="UTC")
        return pd.Timestamp.now(tz="UTC")
