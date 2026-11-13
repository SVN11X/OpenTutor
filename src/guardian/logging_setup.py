"""Local rotating log file. Never records question text, answers or window titles."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_NAME = "guardian.log"


def setup_logging(app_data: Path) -> Path:
    """Attach a small rotating file handler to the 'guardian' logger. Safe to call twice."""
    app_data.mkdir(parents=True, exist_ok=True)
    path = app_data / LOG_NAME
    logger = logging.getLogger("guardian")
    logger.setLevel(logging.INFO)
    if not any(
        isinstance(h, RotatingFileHandler) and h.baseFilename == str(path.resolve()) for h in logger.handlers
    ):
        handler = RotatingFileHandler(path, maxBytes=256 * 1024, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
    return path
