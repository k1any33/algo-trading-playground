import numpy as np
import pandas as pd


def compute_metrics(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {}

    wins   = trades[trades["pnl_pct"] > 0]
    losses = trades[trades["pnl_pct"] <= 0]

    gross_win  = wins["pnl_pct"].sum()
    gross_loss = -losses["pnl_pct"].sum()

    eq          = trades["pnl_pct"].cumsum()
    running_max = eq.cummax()
    max_dd      = float((eq - running_max).min())

    span_years      = (trades["exit_time"].max() - trades["exit_time"].min()).days / 365.25
    trades_per_year = len(trades) / max(span_years, 0.01)
    sharpe = (
        (trades["pnl_pct"].mean() / trades["pnl_pct"].std()) * np.sqrt(trades_per_year)
        if trades["pnl_pct"].std() > 0 else 0.0
    )

    total_return = float(trades["pnl_pct"].sum())
    calmar = total_return / abs(max_dd) if max_dd < 0 else float("inf")

    exit_breakdown = (
        trades.groupby("exit_reason")
        .agg(n=("pnl_pct", "count"), avg_pnl=("pnl_pct", "mean"), total_pnl=("pnl_pct", "sum"))
        .round(3)
        .to_dict("index")
    )

    return {
        "total_trades"       : len(trades),
        "wins"               : len(wins),
        "losses"             : len(losses),
        "win_rate"           : f"{len(wins) / len(trades) * 100:.1f}%",
        "avg_win_pips"       : float(wins["pnl_pips"].mean()) if len(wins) else 0,
        "avg_loss_pips"      : float(losses["pnl_pips"].mean()) if len(losses) else 0,
        "avg_win_pct"        : float(wins["pnl_pct"].mean()) if len(wins) else 0,
        "avg_loss_pct"       : float(losses["pnl_pct"].mean()) if len(losses) else 0,
        "profit_factor"      : gross_win / gross_loss if gross_loss > 0 else float("inf"),
        "expectancy_pct"     : float(trades["pnl_pct"].mean()),
        "total_return_pct"   : total_return,
        "max_drawdown_pct"   : max_dd,
        "calmar"             : calmar,
        "sharpe"             : sharpe,
        "avg_bars_held"      : float(trades["bars_held"].mean()),
        "exit_breakdown"     : exit_breakdown,
    }


def print_metrics(metrics: dict) -> None:
    floats = {
        k: v for k, v in metrics.items()
        if isinstance(v, float) and k != "exit_breakdown"
    }
    others = {
        k: v for k, v in metrics.items()
        if not isinstance(v, float) and k != "exit_breakdown"
    }

    print("=" * 45)
    for k, v in others.items():
        print(f"  {k:<22s}: {v}")
    for k, v in floats.items():
        print(f"  {k:<22s}: {v:>9.3f}")
    print("-" * 45)
    if "exit_breakdown" in metrics:
        print("  Exit breakdown:")
        for reason, row in metrics["exit_breakdown"].items():
            print(f"    {reason:<8s}  n={row['n']}  avg={row['avg_pnl']:.3f}%  total={row['total_pnl']:.3f}%")
    print("=" * 45)
