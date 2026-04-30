"""IBKR order execution via ib-async.

Places bracket orders: market entry + stop loss + take-profit limit.
In DRY_RUN mode, logs what would happen without placing any orders.
"""

import logging
import math

from ib_async import IB, Forex, MarketOrder, StopOrder, LimitOrder, Trade

from src import config

logger = logging.getLogger(__name__)


def _make_contract() -> Forex:
    return Forex(config.SYMBOL)


def compute_quantity(account_equity: float, stop_dist: float) -> int:
    """Fixed-risk position sizing: risk 1% of equity per trade.

    For forex, quantity is in units of base currency.
    """
    risk_amount = account_equity * config.RISK_PER_TRADE
    qty = risk_amount / stop_dist
    return max(1, math.floor(qty))


async def get_account_equity(ib: IB) -> float:
    account_values = await ib.accountValuesAsync()
    for v in account_values:
        if v.tag == "NetLiquidation" and v.currency == "USD":
            return float(v.value)
    raise RuntimeError("Could not retrieve account equity from IBKR")


async def place_bracket_order(
    ib: IB,
    side: str,
    qty: int,
    stop_px: float,
    target_px: float,
) -> dict:
    """Place a bracket order: MKT entry + STP stop loss + LMT take profit.

    Returns dict with order IDs for tracking.
    """
    if config.DRY_RUN:
        logger.info(
            "[DRY RUN] Would place %s bracket: qty=%d stop=%.4f target=%.4f",
            side.upper(), qty, stop_px, target_px,
        )
        return {"dry_run": True, "side": side, "qty": qty, "stop_px": stop_px, "target_px": target_px}

    contract = _make_contract()
    await ib.qualifyContractsAsync(contract)

    action      = "BUY" if side == "long" else "SELL"
    close_action = "SELL" if side == "long" else "BUY"

    entry = MarketOrder(action, qty)
    entry.transmit = False

    stop = StopOrder(close_action, qty, stop_px)
    stop.parentId = entry.orderId
    stop.transmit = False

    take_profit = LimitOrder(close_action, qty, round(target_px, 5))
    take_profit.parentId = entry.orderId
    take_profit.ocaGroup = f"TP_SL_{entry.orderId}"
    take_profit.ocaType  = 1  # cancel remaining on fill
    stop.ocaGroup        = f"TP_SL_{entry.orderId}"
    stop.ocaType         = 1
    take_profit.transmit = True  # transmits all three

    entry_trade: Trade  = ib.placeOrder(contract, entry)
    stop_trade: Trade   = ib.placeOrder(contract, stop)
    tp_trade: Trade     = ib.placeOrder(contract, take_profit)

    logger.info(
        "Placed %s bracket: entry=%d stop=%.4f tp=%.4f",
        side.upper(), qty, stop_px, target_px,
    )

    return {
        "entry_order_id": entry_trade.order.orderId,
        "stop_order_id":  stop_trade.order.orderId,
        "tp_order_id":    tp_trade.order.orderId,
        "side": side,
        "qty": qty,
        "stop_px": stop_px,
        "target_px": target_px,
    }


async def cancel_all_orders(ib: IB) -> None:
    """Cancel all open orders — emergency use."""
    if config.DRY_RUN:
        logger.info("[DRY RUN] Would cancel all orders")
        return
    ib.reqGlobalCancel()
    logger.warning("Cancelled all open orders")
