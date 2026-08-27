"""Utility helpers for logging and file I/O."""

import json
import logging
from pathlib import Path
from typing import Any, Optional


def setup_logging(level: str = "INFO", log_file: Optional[str] = None):
    """Configure logging for the application."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]

    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def save_results(data: Any, filepath: str):
    """Save results to JSON file."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)


def load_results(filepath: str) -> Any:
    """Load results from JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)
