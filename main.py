"""Entry point shortcuts.

    uv run python main.py backtest [--plot]
    uv run python main.py live
    uv run python main.py fetch
"""

import sys

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "help"
    sys.argv = [sys.argv[0]] + sys.argv[2:]

    if mode == "backtest":
        from scripts.run_backtest import main
        main()
    elif mode == "live":
        import asyncio
        from src.engine import run_forever
        asyncio.run(run_forever())
    elif mode == "fetch":
        from src.data_feed import fetch_and_save_history
        fetch_and_save_history()
    else:
        print("Usage: uv run python main.py [backtest|live|fetch]")
        sys.exit(1)
