"""Logging management module."""

import sys
import os
import logging
import logging.handlers
from typing import List

from test_backtrader.utils.logging_handlers_ import UTF8DatagramHandler


def get_common_formatter() -> logging.Formatter:
    """Get logging common formatter."""
    return logging.Formatter(fmt="%(asctime)s - %(name)s - %(levelname)s: %(message)s")


def get_stdout_handler(
    formatter: logging.Formatter, log_level: int = logging.INFO
) -> logging.StreamHandler:
    """Get standard output formatted log handler."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt=formatter)
    handler.setLevel(level=log_level)

    return handler


def get_telegram_handler(
    host: str, port: int, formatter: logging.Formatter, log_level: int = logging.INFO
) -> logging.handlers.DatagramHandler:
    """Get the UDP log hanler to log to Telegram."""

    handler = UTF8DatagramHandler(host=host, port=port)
    handler.setFormatter(fmt=formatter)
    handler.setLevel(level=log_level)

    return handler


def setup_project_logger(
    handlers: List[logging.Handler], logger_level: int = logging.INFO
) -> None:
    """Setup project's logger."""

    # Get the new logger and reset the logging configuration by removing all handlers
    logger = logging.getLogger(os.path.basename(os.getcwd()))
    for handler in logger.handlers:
        logger.removeHandler(handler)

    # Set logger level
    logger.setLevel(logger_level)

    # Add null handler.
    # It has the purpose of set the default behaviour (completely silent)
    # when no other handler is added
    null_handler = logging.NullHandler()
    logger.addHandler(null_handler)

    # Add handlers
    for handler in handlers:
        logger.addHandler(handler)
