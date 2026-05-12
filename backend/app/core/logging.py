"""
Logging setup for ANTS.
Provides standardized logging configuration.
"""
import logging
import os
import sys
from typing import Optional


def setup_logging(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    Set up a logger with standardized configuration.

    Args:
        name: Logger name (typically __name__)
        level: Optional log level override

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    log_level = level or os.getenv("LOG_LEVEL", "INFO")

    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
