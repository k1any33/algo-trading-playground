"""Fisher Transform mean-reversion strategy.

Entry conditions:
  SHORT: fisher[t-1] >= +fisher_threshold AND fisher[t] < fisher[t-1]
  LONG:  fisher[t-1] <= -fisher_threshold AND fisher[t] > fisher[t-1]

Entry price: open of the bar AFTER the signal bar.
Stop: swing high/low over the Fisher-extreme run (+ 1-pip buffer).
Take-profit: first hit of SMA.
Filtered: trades where reward/risk (SMA distance / stop distance) < min_rr are skipped.
"""

import pandas as pd

from src.base_strategy import Signal, Strategy
from src.indicators import fisher_transform, sma
from src import config


class FisherMeanReversion(Strategy):
    def __init__(
        self,
        symbol: str = config.SYMBOL,
        fisher_period: int = config.FISHER_PERIOD,
        fisher_threshold: float = config.FISHER_THRESH,
        ma_period: int = config.MA_PERIOD,
        pip_size: float = config.PIP_SIZE,
        min_rr: float = config.RR_MULTIPLE,
    ) -> None:
        self.symbol = symbol
        self.fisher_period = fisher_period
        self.fisher_threshold = fisher_threshold
        self.ma_period = ma_period
        self.pip_size = pip_size
        self.min_rr = min_rr

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        df = df[["open", "high", "low", "close"]].copy()
        df["fisher"] = fisher_transform(df["high"], df["low"], self.fisher_period)
        df["ma"] = sma(df["close"], self.ma_period)
        df.dropna(inplace=True)

        if len(df) < 3:
            return []

        f = df["fisher"].iloc[-1]
        f_prev = df["fisher"].iloc[-2]

        short_signal = (f_prev >= self.fisher_threshold) and (f < f_prev)
        long_signal = (f_prev <= -self.fisher_threshold) and (f > f_prev)

        if not short_signal and not long_signal:
            return []

        direction = "SHORT" if short_signal else "LONG"
        entry_px = float(df["close"].iloc[-1])
        entry_idx = len(df) - 1

        stop_price = self._compute_stop_price(df, entry_idx, direction)
        stop_dist = abs(entry_px - stop_price)
        ma_val = float(df["ma"].iloc[-1])

        reward = abs(ma_val - entry_px)
        if stop_dist == 0 or reward / stop_dist < self.min_rr:
            return []

        return [Signal(
            symbol=self.symbol,
            direction=direction,
            timestamp=df.index[-1],
            stop_price=stop_price,
            take_profit_price=ma_val,
            metadata={
                "entry_px":  entry_px,
                "stop_dist": stop_dist,
            },
        )]

    def _compute_stop_price(self, df: pd.DataFrame, entry_idx: int, direction: str) -> float:
        fisher = df["fisher"].to_numpy()
        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()

        run_end = entry_idx
        i = entry_idx - 2
        while i > 0 and (
            (direction == "SHORT" and fisher[i] >= self.fisher_threshold) or
            (direction == "LONG" and fisher[i] <= -self.fisher_threshold)
        ):
            i -= 1
        run_start = i + 1

        if run_start >= run_end:
            run_start = run_end - 1

        if direction == "SHORT":
            return float(highs[run_start:run_end].max()) + self.pip_size
        else:
            return float(lows[run_start:run_end].min()) - self.pip_size
