"""Vectorized backtest engine — ported from usdjpy_fisher_meanrev.ipynb."""

import numpy as np
import pandas as pd

from src.indicators import fisher_transform, sma
from src import config


def run_backtest(
    df: pd.DataFrame,
    fisher_period: int = config.FISHER_PERIOD,
    fisher_thresh: float = config.FISHER_THRESH,
    ma_period: int = config.MA_PERIOD,
    rr: float = config.RR_MULTIPLE,
    spread_pips: float = config.SPREAD_PIPS,
) -> pd.DataFrame:
    """Run event-driven backtest on a bar DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV with columns open, high, low, close. Index must be datetime.

    Returns
    -------
    pd.DataFrame
        One row per completed trade with columns:
        side, entry_time, entry_px, exit_time, exit_px, exit_reason,
        stop, stop_dist, pnl_pips, pnl_pct, bars_held.
    """
    df = df[["open", "high", "low", "close"]].copy()
    df["fisher"] = fisher_transform(df["high"], df["low"], fisher_period)
    df["ma"]     = sma(df["close"], ma_period)
    df.dropna(inplace=True)

    opens  = df["open"].to_numpy()
    highs  = df["high"].to_numpy()
    lows   = df["low"].to_numpy()
    closes = df["close"].to_numpy()
    mas    = df["ma"].to_numpy()
    idx    = df.index
    fisher = df["fisher"].to_numpy()

    spread_cost = spread_pips * config.PIP_SIZE
    trades: list[dict] = []
    pos = None

    for i in range(1, len(df)):
        if pos is None:
            f, f_prev = fisher[i], fisher[i - 1]
            short_sig = (f_prev >= fisher_thresh) and (f < f_prev)
            long_sig  = (f_prev <= -fisher_thresh) and (f > f_prev)

            if (short_sig or long_sig) and i + 1 < len(df):
                side     = "short" if short_sig else "long"
                entry_px = opens[i + 1]
                stop_px  = _stop_anchor(fisher, highs, lows, i + 1, side, fisher_thresh)
                if stop_px is None:
                    continue
                stop_dist = abs(entry_px - stop_px)
                if stop_dist < config.MIN_STOP_PIPS * config.PIP_SIZE:
                    continue
                target_rr = (entry_px - rr * stop_dist
                             if side == "short"
                             else entry_px + rr * stop_dist)
                pos = dict(
                    side=side, entry_idx=i + 1, entry_px=entry_px,
                    stop=stop_px, target_rr=target_rr, stop_dist=stop_dist,
                )
        else:
            if i <= pos["entry_idx"]:
                continue

            hi, lo, ma = highs[i], lows[i], mas[i]
            side = pos["side"]
            exit_px, exit_reason = None, None

            if side == "short":
                hit_stop = hi >= pos["stop"]
                hit_ma   = lo <= ma
                hit_rr   = lo <= pos["target_rr"]
                if hit_stop:
                    exit_px, exit_reason = pos["stop"], "stop"
                elif hit_ma and hit_rr:
                    best = max(ma, pos["target_rr"])
                    exit_px = best
                    exit_reason = "ma" if best == ma else "rr"
                elif hit_ma:
                    exit_px, exit_reason = ma, "ma"
                elif hit_rr:
                    exit_px, exit_reason = pos["target_rr"], "rr"
            else:
                hit_stop = lo <= pos["stop"]
                hit_ma   = hi >= ma
                hit_rr   = hi >= pos["target_rr"]
                if hit_stop:
                    exit_px, exit_reason = pos["stop"], "stop"
                elif hit_ma and hit_rr:
                    best = min(ma, pos["target_rr"])
                    exit_px = best
                    exit_reason = "ma" if best == ma else "rr"
                elif hit_ma:
                    exit_px, exit_reason = ma, "ma"
                elif hit_rr:
                    exit_px, exit_reason = pos["target_rr"], "rr"

            if exit_px is not None:
                pnl_raw = (
                    pos["entry_px"] - exit_px
                    if side == "short"
                    else exit_px - pos["entry_px"]
                )
                pnl_net = pnl_raw - spread_cost
                trades.append(dict(
                    side=side,
                    entry_time=idx[pos["entry_idx"]], entry_px=pos["entry_px"],
                    exit_time=idx[i], exit_px=exit_px, exit_reason=exit_reason,
                    stop=pos["stop"], stop_dist=pos["stop_dist"],
                    pnl_pips=pnl_net / config.PIP_SIZE,
                    pnl_pct=pnl_net / pos["entry_px"] * 100,
                    bars_held=i - pos["entry_idx"],
                ))
                pos = None

    return pd.DataFrame(trades)


def _stop_anchor(
    fisher: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    entry_idx: int,
    side: str,
    thresh: float,
) -> float | None:
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
