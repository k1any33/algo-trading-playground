"""Abstract base class for all trading strategies."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal, Optional

import pandas as pd


@dataclass
class Signal:
    symbol: str
    direction: Literal["LONG", "SHORT"]
    timestamp: pd.Timestamp
    stop_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    # Multi-leg coordination — set by strategy, consumed by engine/OrderManager
    group_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class Strategy(ABC):
    """Base class for all trading strategies.

    Subclasses must implement `generate_signals`, which receives a bar DataFrame
    and returns a list of Signals. Multiple signals support multi-leg strategies
    such as pair trades.
    """

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        """Evaluate the latest bar and return trading signals.

        Parameters
        ----------
        df : pd.DataFrame
            OHLCV bars with columns: open, high, low, close.
            Index must be datetime.

        Returns
        -------
        list[Signal]
            Empty list when no trade is warranted.
        """
        ...
