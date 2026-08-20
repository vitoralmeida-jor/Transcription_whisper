"""Configuração central de logs."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path


def setup_logging(log_dir: Path) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"transcritor-{datetime.now():%Y-%m-%d}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.FileHandler(path, encoding="utf-8")],
        force=True,
    )
    return path

