"""IBD Weekly Digest — automated eIBD PDF → Claude → Gmail pipeline."""
import argparse
from html import escape
import keyring
import logging
import logging.handlers
import os
import re
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
LOGS_DIR = ROOT / "logs"
REPORTS_DIR = ROOT / "reports"
LOGS_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)


SERVICE_NAME = "ibd-digest"


def _get_credential(key: str) -> str:
    """Read credential from Windows Credential Manager. Raises RuntimeError if missing."""
    value = keyring.get_password(SERVICE_NAME, key)
    if not value:
        raise RuntimeError(
            f"Missing credential '{key}' in Windows Credential Manager. "
            "Run: python scripts/setup_credentials.py"
        )
    return value


def _build_secret_pattern() -> re.Pattern:
    """Build regex from current env vars + keyring secrets each call — no caching, safe for tests."""
    secret_keys = ["PASSWORD", "KEY", "TOKEN", "SECRET"]
    values = [
        v for k, v in os.environ.items()
        if any(sk in k.upper() for sk in secret_keys) and v.strip()
    ]
    # Also redact keyring-stored secrets so they don't appear in logs
    for cred_key in ("IBD_PASSWORD", "GMAIL_APP_PASSWORD"):
        try:
            v = keyring.get_password(SERVICE_NAME, cred_key)
            if v and v.strip():
                values.append(v)
        except Exception:
            pass
    if values:
        escaped = sorted([re.escape(v) for v in values], key=len, reverse=True)
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

import fitz  # PyMuPDF


def extract_text(pdf_path: str) -> str:
    """Extract full text from all pages of a PDF."""
    with fitz.open(pdf_path) as doc:
        pages = [page.get_text() for page in doc]
    return "\n".join(pages)


import anthropic as anthropic_sdk
import json

from scripts.ibd_schema import DigestSchema

SUMMARIZE_PROMPT = """\
You are extracting structured investment data from an Investor's Business Daily (IBD) weekly edition.

Return ONLY valid JSON matching this exact schema — no prose, no markdown fences, no extra keys:

{
  "date": "YYYY-MM-DD",
  "market_pulse": "<exactly one of: Confirmed Uptrend | Uptrend Under Pressure | Market in Correction>",
  "distribution_days": <integer >= 0>,
  "buy_candidates": [
    {
      "ticker": "<1-5 uppercase letters only, e.g. NVDA>",
      "company": "<company name>",
      "buy_point": "<single decimal number, no $ sign, no ranges, e.g. 153.20>",
      "rs_rating": <integer 1-99>,
      "composite_rating": <integer 1-99>,
      "rationale": "<exactly 2 sentences from IBD commentary>"
    }
  ],
  "stocks_to_watch": ["<TICKER — brief note>"],
  "avoid_extended": ["<TICKER — brief note>"]
}

Rules:
- buy_candidates: only stocks IBD explicitly recommends buying NOW (max 8)
- If a stock's RS or Composite rating is unavailable, omit it from buy_candidates entirely
- ticker: 1-5 uppercase letters only — no dots, slashes, or numbers
- buy_point: single decimal number only (e.g. "153.20") — no "$", no ranges like "153-155"
- market_pulse: must be exactly one of the three strings above, verbatim
- If IBD has no buy candidates this week, return an empty array for buy_candidates

IBD EDITION TEXT:
{text}
"""

CORRECTION_PROMPT = """\
Your previous response was not valid JSON or did not match the required schema.
Return ONLY the JSON object — no explanation, no markdown, no extra text.
Schema reminder: date, market_pulse (exact string), distribution_days, buy_candidates (list), stocks_to_watch (list), avoid_extended (list).
"""


class SummarizationError(Exception):
    pass


def _extract_json(text: str) -> str:
    """Strip markdown fences if present, return raw JSON string."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Skip opening fence line; find closing fence; take everything between
        close_idx = next(
            (i for i, ln in enumerate(lines[1:], 1) if ln.strip().startswith("```")),
            len(lines),
        )
        text = "\n".join(lines[1:close_idx]).strip()
    return text


def summarize(
    text: str,
    client: anthropic_sdk.Anthropic | None = None,
) -> DigestSchema:
    """Call Claude, parse JSON, validate with Pydantic. Retry once on failure."""
    if client is None:
        client = anthropic_sdk.Anthropic()

    # Use replace() not format() — prompt contains literal {} JSON braces that would crash format()
    messages = [{"role": "user", "content": SUMMARIZE_PROMPT.replace("{text}", text)}]

    for attempt in range(2):
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=messages,
        )
        raw = ""
        try:
            raw = response.content[0].text
            json_str = _extract_json(raw)
            data = json.loads(json_str)
            return DigestSchema(**data)
        except Exception as exc:
            log.warning("summarize attempt %d failed: %s", attempt + 1, exc)
            if attempt == 0:
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content": CORRECTION_PROMPT})

    raise SummarizationError("Claude returned invalid JSON after 2 attempts")


def render_subject(edition_date: str) -> str:
    return f"IBD Weekly Digest — Week of {edition_date}"


def render_html(digest: DigestSchema) -> str:
    if digest.buy_candidates:
        rows = ""
        for c in digest.buy_candidates:
            rows += f"""
            <div class="candidate">
              <div class="ticker-row"><strong>{c.ticker}</strong> — {escape(c.company)}</div>
              <div class="meta">Buy point: <strong>${c.buy_point}</strong> &nbsp;|&nbsp; RS Rating: <strong>{c.rs_rating}</strong> &nbsp;|&nbsp; Composite: <strong>{c.composite_rating}</strong></div>
              <div class="rationale">{escape(c.rationale)}</div>
            </div>"""
        candidates_html = f'<h2>Top Buy Candidates ({len(digest.buy_candidates)})</h2>{rows}'
    else:
        candidates_html = "<h2>Top Buy Candidates</h2><p>No buy candidates this week.</p>"

    watch_items = "".join(f"<li>{escape(w)}</li>" for w in digest.stocks_to_watch)
    avoid_items = "".join(f"<li>{escape(a)}</li>" for a in digest.avoid_extended)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px; color: #222; }}
  h1 {{ color: #c00; border-bottom: 2px solid #c00; }}
  h2 {{ color: #333; margin-top: 24px; }}
  .pulse-box {{ background: #f5f5f5; border-left: 4px solid #c00; padding: 12px; margin: 12px 0; }}
  .candidate {{ border: 1px solid #ddd; border-radius: 4px; padding: 12px; margin: 10px 0; }}
  .ticker-row {{ font-size: 1.1em; margin-bottom: 4px; }}
  .meta {{ color: #555; font-size: 0.9em; margin-bottom: 6px; }}
  .rationale {{ font-style: italic; }}
  ul {{ padding-left: 20px; }}
</style>
</head>
<body>
<h1>IBD Weekly Digest — Week of {digest.date}</h1>
<h2>Market Pulse</h2>
<div class="pulse-box">
  <strong>{digest.market_pulse}</strong><br>
  Distribution days: {digest.distribution_days}
</div>
{candidates_html}
<h2>Stocks to Watch</h2>
<ul>{watch_items if watch_items else "<li>None highlighted this week.</li>"}</ul>
<h2>Avoid / Extended</h2>
<ul>{avoid_items if avoid_items else "<li>None flagged this week.</li>"}</ul>
<hr>
<p style="color:#999;font-size:0.8em;">Generated from eIBD edition. Verify candidates against source before trading.</p>
</body>
</html>"""


import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email(html_body: str, subject: str) -> None:
    """Send HTML email via Gmail SMTP. Raises on failure."""
    gmail_address = _get_credential("GMAIL_ADDRESS")
    gmail_password = _get_credential("GMAIL_APP_PASSWORD")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = gmail_address
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(gmail_address, gmail_password)
        smtp.sendmail(gmail_address, gmail_address, msg.as_string())
    log.info("Email sent: %s", subject)


def send_alert(message: str) -> None:
    """Send plain-text alert email. Falls back to file if SMTP fails."""
    subject = "IBD Digest ERROR"
    html = f"<html><body><h2>IBD Digest Error</h2><pre>{message}</pre></body></html>"
    try:
        send_email(html, subject)
    except Exception as exc:
        log.error("Alert email also failed: %s", exc)
        fallback = REPORTS_DIR / f"ibd_alert_{date.today().isoformat()}.html"
        fallback.write_text(f"<html><body><pre>{escape(message)}</pre></body></html>", encoding="utf-8")
        log.info("Alert written to %s", fallback)


EIBD_URL = "https://research.investors.com/eIBD/#/"
LOGIN_URL = "https://investors.com"
DOWNLOAD_WAIT_SECONDS = 60
RETRY_INTERVAL_SECONDS = 600   # 10 minutes
MAX_RETRIES = 3                # 3 retries = 30 min total window


def _is_valid_pdf(path: str) -> bool:
    """Check magic bytes — real PDFs start with %PDF."""
    try:
        with open(path, "rb") as f:
            return f.read(4) == b"%PDF"
    except OSError:
        return False


def login_and_download_pdf(headless: bool = True) -> str:
    """
    Login to investors.com, navigate to eIBD SPA, download whole-edition PDF.
    Returns local path to downloaded PDF.
    Retries up to MAX_RETRIES times if PDF is not yet available.
    Raises RuntimeError on persistent failure.
    """
    from playwright.sync_api import sync_playwright
    from playwright_stealth import Stealth
    stealth = Stealth()

    username = _get_credential("IBD_USERNAME")
    password = _get_credential("IBD_PASSWORD")

    for attempt in range(MAX_RETRIES + 1):
        if attempt > 0:
            log.info("Retry %d/%d in %ds...", attempt, MAX_RETRIES, RETRY_INTERVAL_SECONDS)
            time.sleep(RETRY_INTERVAL_SECONDS)

        download_path = None
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=headless)
                context = browser.new_context(accept_downloads=True)
                page = context.new_page()
                stealth.apply_stealth_sync(page)

                # Step 1: Login on investors.com
                log.info("Navigating to investors.com for login...")
                page.goto(LOGIN_URL, wait_until="networkidle")

                # Fill login form — selectors may need adjustment if site changes
                page.fill('input[name="emailOrUsername"]', username)
                page.fill('input[name="password"], input[type="password"]', password)
                page.click('button[type="submit"], input[type="submit"]')
                page.wait_for_load_state("networkidle")

                if "login" in page.url.lower() or "signin" in page.url.lower():
                    raise RuntimeError("Login failed — still on login page after submit")

                log.info("Login succeeded. Navigating to eIBD...")

                # Step 2: Navigate to eIBD SPA
                page.goto(EIBD_URL, wait_until="networkidle")

                # Step 3: Wait for JS eReader to initialise
                page.wait_for_selector(
                    'button:has-text("Download"), a:has-text("Download PDF"), [aria-label*="download" i]',
                    timeout=30_000,
                )
                log.info("eReader loaded. Initiating download...")

                # Step 4: Click download and capture file
                with page.expect_download(timeout=DOWNLOAD_WAIT_SECONDS * 1000) as dl_info:
                    page.click(
                        'button:has-text("Download"), a:has-text("Download PDF"), [aria-label*="download" i]'
                    )
                download = dl_info.value

                # Save to temp file — mkstemp avoids TOCTOU race of deprecated mktemp()
                fd, tmp = tempfile.mkstemp(suffix=".pdf")
                os.close(fd)
                download_path = tmp  # set before save_as so cleanup finds it if save_as raises
                try:
                    download.save_as(tmp)
                finally:
                    context.close()
                    browser.close()

            # Step 5: Validate magic bytes
            if not _is_valid_pdf(download_path):
                log.warning("Downloaded file is not a valid PDF (magic bytes check failed)")
                if download_path:
                    Path(download_path).unlink(missing_ok=True)
                if attempt < MAX_RETRIES:
                    continue
                raise RuntimeError("Downloaded file is not a valid PDF after all retries")

            log.info("Valid PDF downloaded: %s", download_path)
            return download_path

        except Exception as exc:
            log.warning("Attempt %d failed: %s", attempt + 1, exc)
            if download_path:
                Path(download_path).unlink(missing_ok=True)
            if attempt >= MAX_RETRIES:
                raise RuntimeError(f"Failed to download eIBD PDF after {MAX_RETRIES + 1} attempts: {exc}") from exc


def cleanup(pdf_path: str) -> None:
    Path(pdf_path).unlink(missing_ok=True)
    log.info("Cleaned up temp PDF: %s", pdf_path)


def main(pdf_path: str | None = None) -> None:
    """
    Full pipeline. If pdf_path is given, skip browser download (manual mode).
    Exits with code 1 on any failure.
    """
    from dotenv import load_dotenv
    load_dotenv()

    downloaded = False
    path = pdf_path
    html: str | None = None  # initialized so backup-write is safe if pipeline short-circuits

    try:
        if path is None:
            path = login_and_download_pdf()
            downloaded = True

        text = extract_text(path)
        digest = summarize(text)
        html = render_html(digest)
        subject = render_subject(digest.date)
        send_email(html, subject)
        log.info("Digest sent successfully.")

    except Exception as exc:
        log.error("Pipeline failed: %s", exc)
        send_alert(str(exc))
        if downloaded and path:
            cleanup(path)
        sys.exit(1)

    if downloaded and path:
        cleanup(path)

    # Write HTML backup to reports/
    if html is not None:
        try:
            backup = REPORTS_DIR / f"ibd_{date.today().isoformat()}.html"
            backup.write_text(html, encoding="utf-8")
            log.info("Backup written to %s", backup)
        except Exception:
            pass  # backup failure is non-fatal


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IBD Weekly Digest")
    parser.add_argument("--pdf", metavar="PATH", help="Skip browser; use local PDF file")
    args = parser.parse_args()
    main(pdf_path=args.pdf)
