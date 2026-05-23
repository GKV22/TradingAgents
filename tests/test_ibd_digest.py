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


import fitz  # PyMuPDF
import tempfile


def _make_test_pdf(text: str) -> str:
    """Create a minimal PDF with given text, return path."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    path = tempfile.mktemp(suffix=".pdf")
    doc.save(path)
    doc.close()
    return path


def test_extract_text_returns_content():
    from scripts.ibd_digest import extract_text
    pdf_path = _make_test_pdf("IBD Market Pulse: Confirmed Uptrend\nNVDA buy point 153.20")
    try:
        text = extract_text(pdf_path)
        assert "Confirmed Uptrend" in text
        assert "NVDA" in text
    finally:
        import os
        os.unlink(pdf_path)


def test_extract_text_multi_page():
    from scripts.ibd_digest import extract_text
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i} content TICKER{i}")
    path = tempfile.mktemp(suffix=".pdf")
    doc.save(path)
    doc.close()
    try:
        text = extract_text(path)
        assert "TICKER0" in text
        assert "TICKER1" in text
        assert "TICKER2" in text
    finally:
        import os
        os.unlink(path)
