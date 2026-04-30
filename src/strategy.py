"""Fisher Transform mean-reversion signal logic.

Entry conditions (from usdjpy_fisher_meanrev.ipynb):
  SHORT: fisher[t-1] >= +1.5 AND fisher[t] < fisher[t-1]  (turning down from extreme)
  LONG:  fisher[t-1] <= -1.5 AND fisher[t] > fisher[t-1]  (turning up from extreme)

Entry price: open of the bar AFTER the signal bar.
Stop: swing high/low over the run where Fisher was extreme (+ 1-pip buffer).
Target: first hit of SMA-20 or RR * stop_distance.
"""

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from src.indicators import fisher_transform, sma
from src import config


@dataclass
class SignalEvent:
    side: Literal["long", "short"]
    entry_px: float
    stop_px: float
    target_rr: float
    target_ma: float
    stop_dist: float


def _stop_anchor(df: pd.DataFrame, entry_idx: int, side: str) -> float | None:
    """Walk back from entry bar to find the swing extreme over the Fisher-extreme run."""
    fisher = df["fisher"].to_numpy()
    highs  = df["high"].to_numpy()
    lows   = df["low"].to_numpy()
    thresh = config.FISHER_THRESH

    run_end = entry_idx
    i = entry_idx - 2
    while i > 0 and (
        (side == "short" and fisher[i] >= thresh) or
        (side == "long"  and fisher[i] <= -thresh)
    ):
        i -= 1
    run_start = i + 1

    if run_start >= run_end:
        run_start = run_end - 1

    if side == "short":
        return float(highs[run_start:run_end].max()) + config.PIP_SIZE
    else:
        return float(lows[run_start:run_end].min()) - config.PIP_SIZE


def generate_signal(df: pd.DataFrame) -> SignalEvent | None:
    """Evaluate the most recent completed bar for a trade signal.

    df must have columns: open, high, low, close
    and enough rows for FISHER_PERIOD + MA_PERIOD warmup.
    Returns a SignalEvent if an entry is triggered on the next bar open,
    otherwise None.
    """
    df = df.copy()
    df["fisher"] = fisher_transform(df["high"], df["low"], config.FISHER_PERIOD)
    df["ma"]     = sma(df["close"], config.MA_PERIOD)
    df.dropna(inplace=True)

    if len(df) < 3:
        return None

    f      = df["fisher"].iloc[-1]
    f_prev = df["fisher"].iloc[-2]

    short_signal = (f_prev >= config.FISHER_THRESH) and (f < f_prev)
    long_signal  = (f_prev <= -config.FISHER_THRESH) and (f > f_prev)

    if not short_signal and not long_signal:
        return None

    side = "short" if short_signal else "long"

    # Entry at open of next bar — use last close as proxy at signal time
    entry_px = float(df["close"].iloc[-1])

    entry_idx = len(df) - 1
    stop_px = _stop_anchor(df, entry_idx, side)
    if stop_px is None:
        return None

    stop_dist = abs(entry_px - stop_px)
    if stop_dist < config.MIN_STOP_PIPS * config.PIP_SIZE:
        return None

    ma_val = float(df["ma"].iloc[-1])

    if side == "short":
        target_rr = entry_px - config.RR_MULTIPLE * stop_dist
        target_ma = ma_val
    else:
        target_rr = entry_px + config.RR_MULTIPLE * stop_dist
        target_ma = ma_val

    return SignalEvent(
        side=side,
        entry_px=entry_px,
        stop_px=stop_px,
        target_rr=target_rr,
        target_ma=target_ma,
        stop_dist=stop_dist,
    )


def check_exit(df: pd.DataFrame, position: dict) -> tuple[str | None, float | None]:
    """Check if the current bar triggers a stop or take-profit exit.

    Returns (reason, exit_price) or (None, None).
    """
    if not df.empty:
        bar = df.iloc[-1]
        hi, lo = bar["high"], bar["low"]
        ma_val = float(sma(df["close"], config.MA_PERIOD).iloc[-1])
    else:
        return None, None

    side   = position["side"]
    stop   = position["stop_px"]
    tgt_rr = position["target_rr"]

    if side == "short":
        if hi >= stop:
            return "stop", stop
        hit_ma = lo <= ma_val
        hit_rr = lo <= tgt_rr
        if hit_ma and hit_rr:
            best = max(ma_val, tgt_rr)
            return ("ma" if best == ma_val else "rr"), best
        if hit_ma:
            return "ma", ma_val
        if hit_rr:
            return "rr", tgt_rr
    else:
        if lo <= stop:
            return "stop", stop
        hit_ma = hi >= ma_val
        hit_rr = hi >= tgt_rr
        if hit_ma and hit_rr:
            best = min(ma_val, tgt_rr)
            return ("ma" if best == ma_val else "rr"), best
        if hit_ma:
            return "ma", ma_val
        if hit_rr:
            return "rr", tgt_rr

    return None, None
