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
    import os
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
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
    fd, path = tempfile.mkstemp(suffix=".pdf")
    import os
    os.close(fd)
    doc.save(path)
    doc.close()
    try:
        text = extract_text(path)
        assert "TICKER0" in text
        assert "TICKER1" in text
        assert "TICKER2" in text
    finally:
        os.unlink(path)


import json
from unittest.mock import MagicMock, patch

VALID_JSON = json.dumps({
    "date": "2026-05-19",
    "market_pulse": "Confirmed Uptrend",
    "distribution_days": 2,
    "buy_candidates": [{"ticker": "NVDA", "company": "Nvidia", "buy_point": "153.20", "rs_rating": 97, "composite_rating": 98, "rationale": "Breaking out of flat base. Strong earnings growth."}],
    "stocks_to_watch": ["AAPL — forming handle"],
    "avoid_extended": ["META — extended 18%"],
})

def _mock_anthropic(response_text: str):
    mock_client = MagicMock()
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=response_text)]
    mock_client.messages.create.return_value = mock_msg
    return mock_client

def test_summarize_valid_json():
    from scripts.ibd_digest import summarize
    from scripts.ibd_schema import DigestSchema
    mock_client = _mock_anthropic(f"```json\n{VALID_JSON}\n```")
    result = summarize("some pdf text", client=mock_client)
    assert isinstance(result, DigestSchema)
    assert result.market_pulse == "Confirmed Uptrend"
    assert len(result.buy_candidates) == 1
    assert result.buy_candidates[0].ticker == "NVDA"

def test_summarize_retries_on_invalid_json():
    from scripts.ibd_digest import summarize
    mock_client = MagicMock()
    bad_response = MagicMock()
    bad_response.content = [MagicMock(text="not json at all")]
    good_response = MagicMock()
    good_response.content = [MagicMock(text=VALID_JSON)]
    mock_client.messages.create.side_effect = [bad_response, good_response]
    result = summarize("pdf text", client=mock_client)
    assert result.market_pulse == "Confirmed Uptrend"
    assert mock_client.messages.create.call_count == 2

def test_summarize_raises_after_two_bad_responses():
    from scripts.ibd_digest import summarize, SummarizationError
    mock_client = MagicMock()
    mock_client.messages.create.return_value.content = [MagicMock(text="bad")]
    with pytest.raises(SummarizationError):
        summarize("pdf text", client=mock_client)

def test_summarize_prompt_handles_curly_braces_in_text():
    """Regression: prompt must use .replace() not .format() to avoid crash on { } in PDF text."""
    from scripts.ibd_digest import summarize
    mock_client = _mock_anthropic(VALID_JSON)
    result = summarize("Stocks with {1} or {2} distribution days", client=mock_client)
    assert result.market_pulse == "Confirmed Uptrend"

def test_summarize_empty_buy_candidates_valid():
    from scripts.ibd_digest import summarize
    no_buys = json.dumps({"date": "2026-05-19", "market_pulse": "Market in Correction", "distribution_days": 5, "buy_candidates": [], "stocks_to_watch": [], "avoid_extended": []})
    mock_client = _mock_anthropic(no_buys)
    result = summarize("pdf text", client=mock_client)
    assert result.buy_candidates == []


from scripts.ibd_schema import BuyCandidate

def _make_digest(**overrides):
    defaults = dict(
        date="2026-05-19", market_pulse="Confirmed Uptrend", distribution_days=2,
        buy_candidates=[BuyCandidate(ticker="NVDA", company="Nvidia Corp", buy_point="153.20", rs_rating=97, composite_rating=98, rationale="Breaking out. Strong earnings.")],
        stocks_to_watch=["AAPL — forming handle"],
        avoid_extended=["META — extended"],
    )
    defaults.update(overrides)
    from scripts.ibd_schema import DigestSchema
    return DigestSchema(**defaults)

def test_render_html_contains_ticker():
    from scripts.ibd_digest import render_html
    html = render_html(_make_digest())
    assert "NVDA" in html
    assert "Nvidia Corp" in html

def test_render_html_contains_market_pulse():
    from scripts.ibd_digest import render_html
    html = render_html(_make_digest())
    assert "Confirmed Uptrend" in html
    assert "2" in html

def test_render_html_contains_buy_point():
    from scripts.ibd_digest import render_html
    html = render_html(_make_digest())
    assert "153.20" in html

def test_render_html_no_candidates_section():
    from scripts.ibd_digest import render_html
    html = render_html(_make_digest(buy_candidates=[]))
    assert "No buy candidates" in html

def test_render_html_subject_line():
    from scripts.ibd_digest import render_subject
    subject = render_subject("2026-05-19")
    assert subject == "IBD Weekly Digest — Week of 2026-05-19"


from unittest.mock import patch, MagicMock

def test_send_email_uses_starttls(monkeypatch):
    monkeypatch.setenv("GMAIL_ADDRESS", "test@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "apppass")
    from scripts.ibd_digest import send_email
    with patch("smtplib.SMTP") as mock_smtp_cls:
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = lambda s: mock_smtp
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        send_email("<html>test</html>", "Test Subject")
    mock_smtp.starttls.assert_called_once()
    mock_smtp.login.assert_called_once()
    mock_smtp.sendmail.assert_called_once()
    mock_smtp.set_debuglevel.assert_not_called()

def test_send_email_never_sets_debug_level(monkeypatch):
    monkeypatch.setenv("GMAIL_ADDRESS", "test@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "apppass")
    from scripts.ibd_digest import send_email
    with patch("smtplib.SMTP") as mock_smtp_cls:
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = lambda s: mock_smtp
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        send_email("<html>body</html>", "Subject")
    for call in mock_smtp.method_calls:
        assert "set_debuglevel" not in str(call)


def test_pdf_flag_bypasses_browser(tmp_path, monkeypatch):
    """--pdf flag skips browser automation and reads local file."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("GMAIL_ADDRESS", "test@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "apppass")

    # Create a minimal test PDF
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Market Pulse: Confirmed Uptrend\nNVDA buy point 153")
    pdf_path = str(tmp_path / "test.pdf")
    doc.save(pdf_path)
    doc.close()

    # Patch summarize and send_email so we don't hit real APIs
    from scripts import ibd_digest
    calls = []

    def fake_summarize(text, client=None):
        from scripts.ibd_schema import DigestSchema
        calls.append("summarize")
        return DigestSchema(
            date="2026-05-19",
            market_pulse="Confirmed Uptrend",
            distribution_days=0,
            buy_candidates=[],
            stocks_to_watch=[],
            avoid_extended=[],
        )

    def fake_send_email(html, subject):
        calls.append("send_email")

    monkeypatch.setattr(ibd_digest, "summarize", fake_summarize)
    monkeypatch.setattr(ibd_digest, "send_email", fake_send_email)

    ibd_digest.main(pdf_path=pdf_path)
    assert "summarize" in calls
    assert "send_email" in calls
