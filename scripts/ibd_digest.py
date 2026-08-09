"""IBD Weekly Digest — automated eIBD PDF → Claude → Gmail pipeline."""

# Inject Windows certificate store so corporate/custom CAs are trusted
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass  # truststore optional; falls back to certifi bundle

import argparse
import asyncio
import json
import logging
import logging.handlers
import os
import re
import shutil
import smtplib
import sys
import tempfile
import time
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from pathlib import Path

import anthropic as anthropic_sdk
import keyring

from scripts.ibd_schema import DigestSchema

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
        v for k, v in os.environ.items() if any(sk in k.upper() for sk in secret_keys) and v.strip()
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


def extract_text(pdf_path: str) -> str:
    """Extract full text from all pages of a PDF."""
    import fitz  # PyMuPDF — optional dep; import here to avoid E402 / missing-dep CI failure

    with fitz.open(pdf_path) as doc:
        pages = [page.get_text() for page in doc]
    return "\n".join(pages)


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


MAX_PDF_CHARS = 80_000  # ~20K tokens — well under free-tier 30K/min rate limit


def summarize(
    text: str,
    client: anthropic_sdk.Anthropic | None = None,
) -> DigestSchema:
    """Call Claude, parse JSON, validate with Pydantic. Retry once on failure."""
    if client is None:
        client = anthropic_sdk.Anthropic()

    # Truncate to stay under per-minute token rate limits
    if len(text) > MAX_PDF_CHARS:
        log.info("PDF text truncated from %d to %d chars", len(text), MAX_PDF_CHARS)
        text = text[:MAX_PDF_CHARS]

    # Use replace() not format() — prompt contains literal {} JSON braces that would crash format()
    first_msg = {"role": "user", "content": SUMMARIZE_PROMPT.replace("{text}", text)}
    messages = [first_msg]

    RATE_LIMIT_WAIT = 65  # seconds — token bucket refills each minute
    for attempt in range(4):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                messages=messages,
            )
        except anthropic_sdk.RateLimitError as exc:
            if attempt >= 3:
                raise SummarizationError(f"Rate limit persisted after 4 attempts: {exc}") from exc
            log.warning("Rate limit hit (attempt %d), waiting %ds...", attempt + 1, RATE_LIMIT_WAIT)
            time.sleep(RATE_LIMIT_WAIT)
            continue

        raw = ""
        try:
            raw = response.content[0].text
            json_str = _extract_json(raw)
            data = json.loads(json_str)
            return DigestSchema(**data)
        except Exception as exc:
            log.warning("summarize attempt %d failed: %s", attempt + 1, exc)
            if attempt == 0:
                # Retry: send only assistant reply + correction (not the full PDF again)
                messages = [
                    first_msg,
                    {"role": "assistant", "content": raw},
                    {"role": "user", "content": CORRECTION_PROMPT},
                ]
                time.sleep(5)  # brief pause before retry
            elif attempt >= 2:
                break

    raise SummarizationError("Claude returned invalid JSON after retries")


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
        candidates_html = f"<h2>Top Buy Candidates ({len(digest.buy_candidates)})</h2>{rows}"
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
        fallback.write_text(
            f"<html><body><pre>{escape(message)}</pre></body></html>", encoding="utf-8"
        )
        log.info("Alert written to %s", fallback)


EIBD_URL = "https://research.investors.com/eIBD/#/"
IBD_PROFILE_DIR = ROOT / "ibd-profile"
DOWNLOAD_WAIT_SECONDS = 60
RETRY_INTERVAL_SECONDS = 600  # 10 minutes
MAX_RETRIES = 3  # 3 retries = 30 min total window


def _is_valid_pdf(path: str) -> bool:
    """Check magic bytes — real PDFs start with %PDF."""
    try:
        with open(path, "rb") as f:
            return f.read(4) == b"%PDF"
    except OSError:
        return False


def _force_chrome_pdf_download() -> None:
    """Patch Chrome profile Preferences so PDFs are downloaded, not opened in viewer."""
    import json as _json

    prefs_path = IBD_PROFILE_DIR / "Default" / "Preferences"
    if not prefs_path.exists():
        return
    try:
        prefs = _json.loads(prefs_path.read_text(encoding="utf-8"))
        prefs.setdefault("plugins", {})["always_open_pdf_externally"] = True
        prefs_path.write_text(_json.dumps(prefs), encoding="utf-8")
        log.info("Chrome preference set: PDFs will download instead of opening in viewer")
    except Exception as exc:
        log.warning("Could not patch Chrome PDF preference: %s", exc)


async def _download_pdf_async(headless: bool = False) -> str:
    """Async implementation: launch real Chrome via nodriver, download eIBD PDF."""
    import nodriver as uc

    if not IBD_PROFILE_DIR.exists():
        raise RuntimeError(
            "No saved profile found. Run once manually: python scripts/ibd_save_session.py"
        )

    _force_chrome_pdf_download()

    download_dir = Path(tempfile.mkdtemp(prefix="ibd_dl_"))
    fd, final_path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)

    for attempt in range(MAX_RETRIES + 1):
        if attempt > 0:
            log.info("Retry %d/%d in %ds...", attempt, MAX_RETRIES, RETRY_INTERVAL_SECONDS)
            await asyncio.sleep(RETRY_INTERVAL_SECONDS)

        browser = None
        try:
            browser = await uc.start(
                user_data_dir=str(IBD_PROFILE_DIR),
                headless=headless,
                expert=True,  # forces shadow-roots open so JS can traverse them
            )
            tab = await browser.get(EIBD_URL)

            if "research.investors.com" not in tab.url:
                raise RuntimeError("Session expired — run: python scripts/ibd_save_session.py")

            await tab.set_download_path(download_dir)

            # Wait for SPA to render
            log.info("Waiting for SPA to render...")
            await asyncio.sleep(8)

            # Screenshot for debugging page layout / button positions
            try:
                dbg_shot = ROOT / "reports" / f"debug_eibd_{attempt}.png"
                await tab.save_screenshot(str(dbg_shot))
                log.info("Debug screenshot: %s", dbg_shot)
            except Exception as _se:
                log.warning("Screenshot failed: %s", _se)

            # Monitor network for PDF response — catches download regardless of Chrome save path
            import nodriver.cdp.network as _cdp_net

            captured_pdf_url: list[str] = []

            async def _on_response(
                event: _cdp_net.ResponseReceived,
                _cpdf: list = captured_pdf_url,
            ) -> None:
                url = event.response.url
                mime = (event.response.mime_type or "").lower()
                if "pdf" in mime or url.lower().endswith(".pdf"):
                    log.info("PDF response captured: %s", url)
                    _cpdf.append(url)

            tab.add_handler(_cdp_net.ResponseReceived, _on_response)

            # Click the Newest Issue Download button specifically.
            # eIBD uses Stencil.js (open shadow DOM) so JS can traverse shadow roots.
            # Strategy 1: JS shadow-DOM walk — find Newest Issue card, click its Download btn.
            # Strategy 2: nodriver find "Newest Issue!" → click the element's apply() click.
            # Strategy 3: raw coordinate click derived from page layout.
            log.info("Looking for newest issue Download button...")
            before = set(download_dir.glob("*.pdf"))

            _JS_CLICK_NEWEST = """
            () => {
                function walkAll(root) {
                    const out = [];
                    function recurse(el) {
                        out.push(el);
                        if (el.shadowRoot) recurse(el.shadowRoot);
                        for (const c of (el.children || [])) recurse(c);
                    }
                    recurse(root);
                    return out;
                }

                const all = walkAll(document);

                // Find smallest element whose text is exactly "Newest Issue!"
                let label = null;
                for (const el of all) {
                    if (el.nodeType !== 1) continue;
                    const t = (el.textContent || '').trim();
                    if (t === 'Newest Issue!' && el.children.length === 0) {
                        label = el;
                        break;
                    }
                }
                if (!label) return 'no_label';

                // Walk ancestors (crossing shadow root boundaries) looking for Download btn
                function getParent(el) {
                    if (el.parentElement) return el.parentElement;
                    const root = el.getRootNode();
                    return root && root.host ? root.host : null;
                }

                let node = label;
                for (let depth = 0; depth < 15; depth++) {
                    node = getParent(node);
                    if (!node || node === document) break;
                    // Search downward from this ancestor for a Download button/link
                    for (const el of walkAll(node)) {
                        if (el.nodeType !== 1) continue;
                        const tag = (el.tagName || '').toUpperCase();
                        const txt = (el.textContent || '').trim();
                        const cls = (el.className || '').toLowerCase();
                        const isClickable = tag === 'BUTTON' || tag === 'A' ||
                            el.onclick || cls.includes('download') || cls.includes('btn');
                        if (isClickable && txt.includes('Download') && txt.length < 30) {
                            el.click();
                            return 'clicked_' + tag;
                        }
                    }
                }
                return 'label_found_no_button';
            }
            """

            clicked_directly = False
            try:
                js_result = await tab.evaluate(_JS_CLICK_NEWEST)
                log.info("JS newest-issue click result: %s", js_result)
                if js_result and js_result.startswith("clicked_"):
                    clicked_directly = True
            except Exception as exc:
                log.warning("JS newest issue approach failed: %s", exc)

            if not clicked_directly:
                # Fallback: nodriver find nearest "Newest Issue!" element and use its position
                btn = None
                try:
                    newest_label = await tab.find("Newest Issue!", best_match=True, timeout=10)
                    if newest_label:
                        pos = await newest_label.get_position()
                        log.info(
                            "'Newest Issue!' at (%.0f, %.0f); coordinate clicking Download",
                            pos.x,
                            pos.y,
                        )
                        # Try multiple y-offsets to find the Download button in the card
                        for y_offset in (250, 300, 200):
                            await tab.mouse_click(pos.x, pos.y + y_offset)
                            await asyncio.sleep(2)
                            new_pdfs = set(download_dir.glob("*.pdf")) - before
                            if new_pdfs:
                                clicked_directly = True
                                break
                except Exception as exc:
                    log.warning("Coordinate fallback failed: %s", exc)

            if not clicked_directly:
                # Last resort: find any element with "Download" text
                try:
                    btn = await tab.find("Download", best_match=True, timeout=15)
                    if btn and btn.tag_name == "#comment":
                        btn = None
                except Exception:
                    btn = None
                if btn:
                    log.info("nodriver found element tag=%s text=%r", btn.tag_name, btn.text)
                    try:
                        btn_html = await btn.apply(
                            "function() { return this.outerHTML + ' | parent: ' + (this.parentElement ? this.parentElement.outerHTML.slice(0,300) : 'none'); }"
                        )
                        log.info("Download element HTML: %s", str(btn_html)[:600])
                    except Exception:
                        pass
                    await btn.click()
                else:
                    log.info("Falling back to coordinate click at (480, 581)...")
                    await tab.mouse_click(480, 581)

            await asyncio.sleep(3)
            log.info("URL after click: %s", tab.url)

            # Poll for file in download_dir OR capture via network handler
            log.info("Waiting for download to complete...")
            pdf_path: Path | None = None
            for _ in range(DOWNLOAD_WAIT_SECONDS):
                await asyncio.sleep(1)
                new_pdfs = set(download_dir.glob("*.pdf")) - before
                in_progress = set(download_dir.glob("*.crdownload"))
                if new_pdfs and not in_progress:
                    pdf_path = next(iter(new_pdfs))
                    log.info("PDF found in download dir: %s", pdf_path)
                    break

            # Fallback: use network-captured PDF URL + browser cookies
            if pdf_path is None and captured_pdf_url:
                log.info(
                    "File poll timed out; downloading via captured URL: %s", captured_pdf_url[0]
                )
                cookies_list = await browser.cookies.get_all()
                cookie_header = "; ".join(f"{c.name}={c.value}" for c in cookies_list)
                import urllib.request as _urlreq

                req = _urlreq.Request(
                    captured_pdf_url[0],
                    headers={
                        "Cookie": cookie_header,
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    },
                )
                with _urlreq.urlopen(req, timeout=60) as resp:
                    Path(final_path).write_bytes(resp.read())
                log.info("PDF downloaded via URL fallback")
                return final_path  # skip shutil.move below

            if pdf_path is None:
                raise RuntimeError("Download timed out — no PDF received and no URL captured")

            _stop = browser.stop()
            if asyncio.iscoroutine(_stop):
                await _stop
            browser = None

            if not _is_valid_pdf(str(pdf_path)):
                raise RuntimeError("Downloaded file is not a valid PDF (magic bytes check failed)")

            shutil.move(str(pdf_path), final_path)
            log.info("Valid PDF downloaded: %s", final_path)
            shutil.rmtree(str(download_dir), ignore_errors=True)
            return final_path

        except Exception as exc:
            import traceback as _tb

            log.warning("Attempt %d failed: %s\n%s", attempt + 1, exc, _tb.format_exc())
            if browser:
                try:
                    result = browser.stop()
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:
                    pass
            if attempt >= MAX_RETRIES:
                Path(final_path).unlink(missing_ok=True)
                shutil.rmtree(str(download_dir), ignore_errors=True)
                raise RuntimeError(
                    f"Failed to download eIBD PDF after {MAX_RETRIES + 1} attempts: {exc}"
                ) from exc

    raise RuntimeError("Unexpected exit from retry loop")


def login_and_download_pdf(headless: bool = False) -> str:
    """
    Navigate to eIBD using persistent nodriver profile, download whole-edition PDF.
    Returns local path to downloaded PDF.
    Requires ibd-profile/ created by scripts/ibd_save_session.py.
    Retries up to MAX_RETRIES times if PDF is not yet available.
    Raises RuntimeError on persistent failure.
    """
    return asyncio.run(_download_pdf_async(headless=headless))


def cleanup(pdf_path: str) -> None:
    Path(pdf_path).unlink(missing_ok=True)
    log.info("Cleaned up temp PDF: %s", pdf_path)


def main(pdf_path: str | None = None) -> None:
    """
    Full pipeline. If pdf_path is given, skip browser download (manual mode).
    Exits with code 1 on any failure.
    """
    from dotenv import load_dotenv

    load_dotenv(override=True)

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
