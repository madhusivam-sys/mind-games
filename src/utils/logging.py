from __future__ import annotations

import logging
from typing import Final

from utils.config import get_settings

_LOG_FORMAT: Final[str] = "%(asctime)s %(levelname)s %(name)s %(message)s"
_CONFIGURED: bool = False


def configure_logging() -> None:
    """Configure process logging once in an idempotent way."""

    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(level=getattr(logging, get_settings().log_level.upper(), logging.INFO), format=_LOG_FORMAT)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
