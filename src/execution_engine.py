"""Abstract execution engine interface."""

from abc import ABC, abstractmethod

import pandas as pd

from src.order_manager import Order


class ExecutionEngine(ABC):
    @abstractmethod
    async def submit(self, order: Order) -> None:
        """Submit an order to the broker or fill simulator."""
        ...

    @abstractmethod
    async def get_equity(self) -> float:
        """Return current account equity."""
        ...
