"""Persist and retrieve the current open position to/from disk.

JSON format so the bot can resume correctly after a restart.
"""

import json
import logging
from pathlib import Path
from typing import Any

from src import config

logger = logging.getLogger(__name__)

_PATH: Path = config.POSITION_FILE


def load() -> dict | None:
    """Return the saved position dict, or None if no position is open."""
    if not _PATH.exists():
        return None
    with _PATH.open() as f:
        data = json.load(f)
    logger.info("Loaded position from disk: %s", data)
    return data


def save(position: dict) -> None:
    """Persist an open position to disk."""
    with _PATH.open("w") as f:
        json.dump(position, f, indent=2, default=str)
    logger.info("Saved position: %s", position)


def clear() -> None:
    """Remove position state after a trade is closed."""
    if _PATH.exists():
        _PATH.unlink()
    logger.info("Position state cleared")


def is_flat() -> bool:
    return not _PATH.exists()
