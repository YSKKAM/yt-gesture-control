"""
app/logging_setup/logger.py

Configures the application-wide rotating file logger.
All other modules import 'get_logger' from here.
"""
import logging
import logging.handlers
import os
import sys
from pathlib import Path


def setup_logging(log_file: str = "logs/ytgc.log",
                  max_bytes: int = 5_242_880,
                  backup_count: int = 3,
                  level: str = "INFO") -> None:
    """
    Call once at application startup.
    Creates the log directory if it does not exist.
    """
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Rotating file handler — never grows unbounded
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Console handler for development visibility
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Call after setup_logging() has been called."""
    return logging.getLogger(name)
