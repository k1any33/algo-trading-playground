"""Run Fisher Transform mean-reversion backtest on saved USDJPY data.

Usage:
    uv run python scripts/run_backtest.py
    uv run python scripts/run_backtest.py --plot

Requires data/USDJPY_4hours.parquet — run scripts/fetch_history.py first.
"""

import argparse
import logging
import sys

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from src.config import HISTORY_PARQUET
from backtest.engine import run_backtest
from backtest.metrics import compute_metrics, print_metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plot", action="store_true", help="Show equity curve chart")
    args = parser.parse_args()

    if not HISTORY_PARQUET.exists():
        print(f"Data file not found: {HISTORY_PARQUET}")
        print("Run: uv run python scripts/fetch_history.py")
        sys.exit(1)

    df = pd.read_parquet(HISTORY_PARQUET)
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)
    df = df[~df.index.duplicated(keep="last")]

    print(f"Loaded {len(df):,} bars  [{df.index.min().date()} → {df.index.max().date()}]")

    trades = run_backtest(df)
    print(f"\nCompleted trades: {len(trades)}")

    if trades.empty:
        print("No trades generated — check data or strategy parameters.")
        sys.exit(0)

    metrics = compute_metrics(trades)
    print_metrics(metrics)

    if args.plot:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        eq = trades.set_index("exit_time")["pnl_pct"].cumsum()
        running_max = eq.cummax()
        drawdown = eq - running_max

        fig, axes = plt.subplots(2, 1, figsize=(14, 7), sharex=True,
                                  gridspec_kw={"height_ratios": [2, 1]})
        axes[0].plot(eq.index, eq, lw=1, color="steelblue")
        axes[0].fill_between(eq.index, eq, 0, alpha=0.1, color="steelblue")
        axes[0].axhline(0, color="black", lw=0.5)
        axes[0].set_ylabel("Cum. return (%)")
        axes[0].set_title("USD/JPY Fisher Mean-Reversion — Equity Curve")

        axes[1].fill_between(drawdown.index, drawdown, 0, color="red", alpha=0.4)
        axes[1].set_ylabel("Drawdown (%)")
        axes[1].set_title(f"Drawdown (max = {drawdown.min():.2f}%)")
        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    main()
