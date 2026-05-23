import logging
import logging.handlers  # must import explicitly — `import logging` alone does not pull in submodule
import os
import pytest


def test_sanitizing_formatter_redacts_password(monkeypatch):
    monkeypatch.setenv("IBD_PASSWORD", "supersecret")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "apppass123")

    import io
    stream = io.StringIO()
    from scripts.ibd_digest import make_logger, SanitizingFormatter
    import logging
    sh = logging.StreamHandler(stream)
    sh.setFormatter(SanitizingFormatter())
    handler2 = logging.handlers.MemoryHandler(capacity=100, target=sh)
    logger2 = make_logger("test_sanitize2")
    logger2.addHandler(handler2)
    logger2.error("Failed with password=supersecret and apppass123")
    handler2.flush()
    output = stream.getvalue()

    assert "supersecret" not in output
    assert "apppass123" not in output
    assert "***REDACTED***" in output


def test_sanitizing_formatter_preserves_non_secret_text(monkeypatch):
    monkeypatch.setenv("IBD_PASSWORD", "mysecret")
    from scripts.ibd_digest import SanitizingFormatter
    import logging
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="ticker NVDA buy point 153.20", args=(), exc_info=None
    )
    fmt = SanitizingFormatter()
    output = fmt.format(record)
    assert "NVDA" in output
    assert "153.20" in output
