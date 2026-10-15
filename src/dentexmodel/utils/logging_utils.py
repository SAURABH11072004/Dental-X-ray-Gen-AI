"""Central logging setup (console + rotating file)."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_FMT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_configured = False


def setup_logging(log_dir: Path | None = None, level: str = "INFO") -> None:
    """Idempotently configure the root ``dentexmodel`` logger."""
    global _configured
    logger = logging.getLogger("dentexmodel")
    logger.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    if _configured:
        return
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(_FMT))
    logger.addHandler(console)
    if log_dir is not None:
        try:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
            fh = RotatingFileHandler(Path(log_dir) / "dentamind.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
            fh.setFormatter(logging.Formatter(_FMT))
            logger.addHandler(fh)
        except OSError as exc:  # read-only volume etc. - never crash because of logging
            logger.warning("File logging disabled (%s)", exc)
    logger.propagate = False
    _configured = True
