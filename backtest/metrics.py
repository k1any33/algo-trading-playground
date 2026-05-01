import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.portfolio import Portfolio


# ── New Portfolio-based metrics ───────────────────────────────────────────────

@dataclass
class BacktestMetrics:
    # Trade counts
    total_trades:   int
    winning_trades: int
    losing_trades:  int
    stop_hits:      int
    tp_hits:        int

    # Trade-level
    win_rate:           float   # %
    profit_factor:      float   # gross_profit / gross_loss
    avg_win:            float
    avg_loss:           float   # negative
    avg_pnl_per_trade:  float
    largest_win:        float
    largest_loss:       float

    # Portfolio-level
    starting_capital:  float
    final_equity:      float
    total_return_pct:  float
    max_drawdown_pct:  float   # peak-to-trough as % of peak

    # Risk-adjusted (trade-based approximation)
    sharpe_ratio:   float
    sortino_ratio:  float


def compute(portfolio: Portfolio) -> BacktestMetrics:
    trades = portfolio.trade_history
    if not trades:
        raise ValueError("Portfolio has no closed trades — run backtest first.")

    pnls   = [t.pnl for t in trades]
    wins   = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    gross_profit = sum(wins)
    gross_loss   = abs(sum(losses))

    stop_hits = sum(1 for t in trades if t.exit_reason == "stop")
    tp_hits   = sum(1 for t in trades if t.exit_reason == "take_profit")

    equity_series  = _equity_series(portfolio)
    trade_returns  = equity_series.pct_change().dropna()
    peak           = equity_series.cummax()
    max_dd_pct     = float(((equity_series - peak) / peak).min()) * 100

    starting = portfolio._starting_capital
    final    = portfolio.equity

    return BacktestMetrics(
        total_trades=len(trades),
        winning_trades=len(wins),
        losing_trades=len(losses),
        stop_hits=stop_hits,
        tp_hits=tp_hits,

        win_rate=len(wins) / len(trades) * 100,
        profit_factor=gross_profit / gross_loss if gross_loss else float("inf"),
        avg_win=float(np.mean(wins)) if wins else 0.0,
        avg_loss=float(np.mean(losses)) if losses else 0.0,
        avg_pnl_per_trade=float(np.mean(pnls)),
        largest_win=max(pnls),
        largest_loss=min(pnls),

        starting_capital=starting,
        final_equity=final,
        total_return_pct=(final - starting) / starting * 100,
        max_drawdown_pct=max_dd_pct,

        sharpe_ratio=_sharpe(trade_returns),
        sortino_ratio=_sortino(trade_returns),
    )


def summary_df(metrics: BacktestMetrics) -> pd.DataFrame:
    """Return metrics as a two-column DataFrame for display in a notebook."""
    rows = [
        ("Total trades",     metrics.total_trades),
        ("Winning trades",   metrics.winning_trades),
        ("Losing trades",    metrics.losing_trades),
        ("Win rate",         f"{metrics.win_rate:.1f}%"),
        ("Profit factor",    f"{metrics.profit_factor:.2f}"),
        ("Avg win",          f"{metrics.avg_win:.2f}"),
        ("Avg loss",         f"{metrics.avg_loss:.2f}"),
        ("Largest win",      f"{metrics.largest_win:.2f}"),
        ("Largest loss",     f"{metrics.largest_loss:.2f}"),
        ("Avg P&L / trade",  f"{metrics.avg_pnl_per_trade:.2f}"),
        ("Stop hits",        metrics.stop_hits),
        ("TP hits",          metrics.tp_hits),
        ("Starting capital", f"{metrics.starting_capital:,.2f}"),
        ("Final equity",     f"{metrics.final_equity:,.2f}"),
        ("Total return",     f"{metrics.total_return_pct:.2f}%"),
        ("Max drawdown",     f"{metrics.max_drawdown_pct:.2f}%"),
        ("Sharpe ratio",     f"{metrics.sharpe_ratio:.2f}"),
        ("Sortino ratio",    f"{metrics.sortino_ratio:.2f}"),
    ]
    return pd.DataFrame(rows, columns=["Metric", "Value"]).set_index("Metric")


def _equity_series(portfolio: Portfolio) -> pd.Series:
    timestamps, equities = zip(*portfolio.equity_curve)
    return pd.Series(list(equities), index=pd.DatetimeIndex(list(timestamps)))


def _sharpe(returns: pd.Series, periods_per_year: int = 252) -> float:
    if returns.std() == 0:
        return 0.0
    return float(returns.mean() / returns.std() * math.sqrt(periods_per_year))


def _sortino(returns: pd.Series, periods_per_year: int = 252) -> float:
    downside = returns[returns < 0]
    if downside.empty or downside.std() == 0:
        return 0.0
    return float(returns.mean() / downside.std() * math.sqrt(periods_per_year))