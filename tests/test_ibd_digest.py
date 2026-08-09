import json
import logging
import logging.handlers  # must import explicitly — `import logging` alone does not pull in submodule
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.ibd_schema import BuyCandidate

fitz = pytest.importorskip("fitz")  # PyMuPDF — skip fitz-dependent tests if not installed


def test_sanitizing_formatter_redacts_password(monkeypatch):
    monkeypatch.setenv("IBD_PASSWORD", "supersecret")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "apppass123")

    import io

    stream = io.StringIO()

    from scripts.ibd_digest import SanitizingFormatter, make_logger

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

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="ticker NVDA buy point 153.20",
        args=(),
        exc_info=None,
    )
    fmt = SanitizingFormatter()
    output = fmt.format(record)
    assert "NVDA" in output
    assert "153.20" in output


def _make_test_pdf(text: str) -> str:
    """Create a minimal PDF with given text, return path."""
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
        os.unlink(pdf_path)


def test_extract_text_multi_page():
    from scripts.ibd_digest import extract_text

    doc = fitz.open()
    for i in range(3):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i} content TICKER{i}")
    fd, path = tempfile.mkstemp(suffix=".pdf")
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


VALID_JSON = json.dumps(
    {
        "date": "2026-05-19",
        "market_pulse": "Confirmed Uptrend",
        "distribution_days": 2,
        "buy_candidates": [
            {
                "ticker": "NVDA",
                "company": "Nvidia",
                "buy_point": "153.20",
                "rs_rating": 97,
                "composite_rating": 98,
                "rationale": "Breaking out of flat base. Strong earnings growth.",
            }
        ],
        "stocks_to_watch": ["AAPL — forming handle"],
        "avoid_extended": ["META — extended 18%"],
    }
)


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
    from scripts.ibd_digest import SummarizationError, summarize

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

    no_buys = json.dumps(
        {
            "date": "2026-05-19",
            "market_pulse": "Market in Correction",
            "distribution_days": 5,
            "buy_candidates": [],
            "stocks_to_watch": [],
            "avoid_extended": [],
        }
    )
    mock_client = _mock_anthropic(no_buys)
    result = summarize("pdf text", client=mock_client)
    assert result.buy_candidates == []


def _make_digest(**overrides):
    defaults = {
        "date": "2026-05-19",
        "market_pulse": "Confirmed Uptrend",
        "distribution_days": 2,
        "buy_candidates": [
            BuyCandidate(
                ticker="NVDA",
                company="Nvidia Corp",
                buy_point="153.20",
                rs_rating=97,
                composite_rating=98,
                rationale="Breaking out. Strong earnings.",
            )
        ],
        "stocks_to_watch": ["AAPL — forming handle"],
        "avoid_extended": ["META — extended"],
    }
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


def test_send_email_uses_starttls():
    from scripts.ibd_digest import send_email

    def fake_get_password(service, key):
        return {"GMAIL_ADDRESS": "test@gmail.com", "GMAIL_APP_PASSWORD": "apppass"}.get(key)

    with (
        patch("keyring.get_password", side_effect=fake_get_password),
        patch("smtplib.SMTP") as mock_smtp_cls,
    ):
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = lambda s: mock_smtp
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        send_email("<html>test</html>", "Test Subject")

    mock_smtp.starttls.assert_called_once()
    mock_smtp.login.assert_called_once()
    mock_smtp.sendmail.assert_called_once()
    mock_smtp.set_debuglevel.assert_not_called()


def test_send_email_never_sets_debug_level():
    from scripts.ibd_digest import send_email

    def fake_get_password(service, key):
        return {"GMAIL_ADDRESS": "test@gmail.com", "GMAIL_APP_PASSWORD": "apppass"}.get(key)

    with (
        patch("keyring.get_password", side_effect=fake_get_password),
        patch("smtplib.SMTP") as mock_smtp_cls,
    ):
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = lambda s: mock_smtp
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        send_email("<html>body</html>", "Subject")

    for call in mock_smtp.method_calls:
        assert "set_debuglevel" not in str(call)


def test_login_raises_when_no_profile(tmp_path, monkeypatch):
    """login_and_download_pdf raises immediately when ibd-profile/ doesn't exist."""
    from scripts import ibd_digest

    monkeypatch.setattr(ibd_digest, "IBD_PROFILE_DIR", tmp_path / "nonexistent")
    with pytest.raises(RuntimeError, match="No saved profile"):
        ibd_digest.login_and_download_pdf()


@pytest.mark.asyncio
async def test_download_pdf_async_raises_when_no_profile(tmp_path, monkeypatch):
    """_download_pdf_async raises immediately when ibd-profile/ doesn't exist."""
    from scripts import ibd_digest

    monkeypatch.setattr(ibd_digest, "IBD_PROFILE_DIR", tmp_path / "nonexistent")
    with pytest.raises(RuntimeError, match="No saved profile"):
        await ibd_digest._download_pdf_async()


@pytest.mark.asyncio
async def test_download_pdf_async_success(tmp_path, monkeypatch):
    """_download_pdf_async returns a valid PDF path when nodriver succeeds."""
    from scripts import ibd_digest

    profile_dir = tmp_path / "ibd-profile"
    profile_dir.mkdir()
    monkeypatch.setattr(ibd_digest, "IBD_PROFILE_DIR", profile_dir)

    download_dir = tmp_path / "downloads"
    download_dir.mkdir()

    async def fake_click():
        pdf = download_dir / "ibd_edition.pdf"
        doc = fitz.open()
        doc.new_page()
        doc.save(str(pdf))
        doc.close()

    mock_btn = AsyncMock()
    mock_btn.click = fake_click

    mock_tab = AsyncMock()
    mock_tab.url = "https://research.investors.com/eIBD/#/"
    mock_tab.wait_for.return_value = mock_btn

    mock_browser = AsyncMock()
    mock_browser.get.return_value = mock_tab

    with (
        patch("nodriver.start", new=AsyncMock(return_value=mock_browser)),
        patch("tempfile.mkdtemp", return_value=str(download_dir)),
    ):
        result = await ibd_digest._download_pdf_async(headless=False)

    assert result.endswith(".pdf")
    assert ibd_digest._is_valid_pdf(result)


@pytest.mark.asyncio
async def test_download_pdf_async_session_expired(tmp_path, monkeypatch):
    """_download_pdf_async raises RuntimeError immediately when session is expired."""
    from scripts import ibd_digest

    profile_dir = tmp_path / "ibd-profile"
    profile_dir.mkdir()
    monkeypatch.setattr(ibd_digest, "IBD_PROFILE_DIR", profile_dir)
    monkeypatch.setattr(ibd_digest, "MAX_RETRIES", 0)

    mock_tab = AsyncMock()
    mock_tab.url = "https://sso.accounts.dowjones.com/authorize"
    mock_browser = AsyncMock()
    mock_browser.get.return_value = mock_tab

    with (
        patch("nodriver.start", new=AsyncMock(return_value=mock_browser)),
        pytest.raises(RuntimeError, match="Failed to download"),
    ):
        await ibd_digest._download_pdf_async(headless=False)


def test_pdf_flag_bypasses_browser(tmp_path, monkeypatch):
    """--pdf flag skips browser automation and reads local file."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Market Pulse: Confirmed Uptrend\nNVDA buy point 153")
    pdf_path = str(tmp_path / "test.pdf")
    doc.save(pdf_path)
    doc.close()

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
