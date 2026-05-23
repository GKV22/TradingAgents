"""IBD Weekly Digest — automated eIBD PDF → Claude → Gmail pipeline."""
import logging
import logging.handlers
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
LOGS_DIR = ROOT / "logs"
REPORTS_DIR = ROOT / "reports"
LOGS_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)


def _build_secret_pattern() -> re.Pattern:
    """Build regex from current env vars each call — no caching, safe for tests."""
    secret_keys = ["PASSWORD", "KEY", "TOKEN", "SECRET"]
    values = [
        v for k, v in os.environ.items()
        if any(sk in k.upper() for sk in secret_keys) and v.strip()
    ]
    if values:
        escaped = [re.escape(v) for v in values]
        return re.compile("|".join(escaped))
    return re.compile(r"(?!)")  # never matches


class SanitizingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        return _build_secret_pattern().sub("***REDACTED***", msg)


def make_logger(name: str = "ibd_digest") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = SanitizingFormatter("%(asctime)s %(levelname)s %(message)s")
    fh = logging.FileHandler(LOGS_DIR / "ibd_digest.log", encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    return logger


log = make_logger()
