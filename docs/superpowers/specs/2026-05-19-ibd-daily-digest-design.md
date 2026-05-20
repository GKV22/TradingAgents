# IBD Daily Digest — Design Spec

**Date:** 2026-05-19
**Status:** Draft

## Overview

Automated daily script that logs into investors.com, downloads the IBD daily paper PDF, extracts buy candidates and market signals using Claude, and emails a structured 2-page HTML digest to geoff.cavey@gmail.com at 6 AM via Windows Task Scheduler.

## Goals

- Surface IBD's explicit stock buy recommendations each morning before market open
- Highlight Market Pulse, buy points, CAN SLIM signals, and IBD ratings
- Require zero manual effort once configured

## Non-Goals

- Integration with TradingAgents graph or agent layers
- Storing historical digests in a database
- Tracking portfolio positions

## Risks & Assumptions

### Anti-bot / Browser Detection

investors.com is a Dow Jones property serving paid subscription content. The site may deploy bot-detection (Cloudflare, Akamai, PerimeterX) that blocks headless Playwright sessions. Mitigation:

- Use `playwright-stealth` to reduce fingerprint detectability
- Validate downloaded file is a real PDF via magic bytes (`%PDF` header) — not file extension
- If headless mode is blocked, fall back to visible-browser mode (`headless=False`) which is acceptable for a personal unattended task on a home machine with a logged-in Windows session
- If automation is permanently blocked, document fallback: manual download + manual trigger of `scripts/ibd_digest.py --pdf <path>`

### Terms of Service

Automated login and programmatic download of IBD content may conflict with investors.com ToS. **This is personal-use automation for a paying subscriber's own content on their own machine.** User has reviewed this risk and accepts it as a deliberate decision. The script does not redistribute content.

### IBD Publication Schedule

IBD's digital edition PDF is published overnight. Exact availability time varies. A fixed 6 AM trigger may arrive before the PDF is posted.

**Mitigation:** Script retries PDF download every 10 minutes for up to 90 minutes. If not found by 7:30 AM, sends alert email and exits with non-zero code.

## Architecture

```
Windows Task Scheduler (6:00 AM daily)
    │
    ▼
scripts/ibd_digest.py
    │
    ├─ 1. Playwright (+stealth): login investors.com → navigate → download PDF
    │       Validate: magic bytes confirm real PDF
    │       Retry: every 10 min up to 90 min if PDF not yet posted
    │       Re-auth: on each retry attempt, re-login if session may have expired (>15 min since last login)
    │
    ├─ 2. PyMuPDF (fitz): extract full text from all pages
    │
    ├─ 3. Claude API (claude-sonnet-4-6): extract structured JSON digest
    │       → validate schema (candidate count, required fields)
    │       → render JSON to HTML
    │
    └─ 4. smtplib: send HTML email → geoff.cavey@gmail.com
         on failure: write to reports/ibd_YYYYMMDD.html
                     exit with code 1 (triggers Task Scheduler failure alert)
```

## Components

### `scripts/ibd_digest.py`

| Function | Purpose |
|---|---|
| `login_and_download_pdf()` | Playwright+stealth: login, navigate, download PDF; validate magic bytes; retry loop |
| `extract_text(pdf_path)` | PyMuPDF: extract raw text from all pages |
| `summarize(text) -> DigestSchema` | Claude API: extract structured JSON matching DigestSchema |
| `render_html(digest: DigestSchema) -> str` | Python: render DigestSchema to HTML email body |
| `send_email(html_body)` | smtplib + Gmail SMTP: send HTML email |
| `cleanup(pdf_path)` | Delete temp PDF after successful send |

### Claude Output Schema (JSON-first, Pydantic-validated)

`summarize()` instructs Claude to return JSON. Python validates with Pydantic before rendering — TypedDict alone does not enforce value-level constraints at runtime.

```python
from pydantic import BaseModel, Field, field_validator
from typing import Literal

VALID_MARKET_PULSE = {
    "Confirmed Uptrend",
    "Uptrend Under Pressure",
    "Market in Correction",
}

class BuyCandidate(BaseModel):
    ticker: str           # validated ^[A-Z]{1,5}$ — satisfies project ticker allowlist invariant
    company: str
    buy_point: str        # validated as single numeric value e.g. "153.20" (no "$", no ranges)
    rs_rating: int = Field(ge=1, le=99)
    composite_rating: int = Field(ge=1, le=99)
    rationale: str        # 2 sentences max

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v):
        import re
        if not re.fullmatch(r"[A-Z]{1,5}", v):
            raise ValueError(f"Invalid ticker: {v!r}")
        return v

    @field_validator("buy_point")
    @classmethod
    def validate_buy_point(cls, v):
        import re
        # accept "153.20" or "153" — no "$", no ranges, no text
        if not re.fullmatch(r"\d+(\.\d{1,2})?", v):
            raise ValueError(f"buy_point must be a single decimal number, got: {v!r}")
        return v

class DigestSchema(BaseModel):
    date: str
    market_pulse: str
    distribution_days: int = Field(ge=0)
    buy_candidates: list[BuyCandidate] = Field(max_length=8)
    stocks_to_watch: list[str]   # display-only; never used as file path, query param, or API arg
    avoid_extended: list[str]    # display-only; never used as file path, query param, or API arg

    @field_validator("market_pulse")
    @classmethod
    def validate_pulse(cls, v):
        if v not in VALID_MARKET_PULSE:
            raise ValueError(f"Unknown market_pulse: {v!r}")
        return v
```

If Claude returns invalid JSON or Pydantic validation fails, retry once with a corrective prompt. If still invalid, send alert email. An empty `buy_candidates` list is valid (IBD may have no buys on a given day); the email will render a "No buy candidates today" section rather than an error.

### Email Format

```
Subject: IBD Daily Digest — YYYY-MM-DD

MARKET PULSE
Current outlook: Confirmed Uptrend
Distribution days: 2

TOP BUY CANDIDATES (5)
┌─────────────────────────────────────────────────────┐
│ NVDA — Nvidia Corp                                  │
│ Buy point: $153.20  |  RS Rating: 97  |  Comp: 98  │
│ Why: Breaking out of 8-week flat base on volume.    │
│      Earnings accelerating three straight quarters. │
└─────────────────────────────────────────────────────┘
...

STOCKS TO WATCH
• AAPL — Forming handle on cup base, buy point $198.50

AVOID / EXTENDED
• META — Extended 18% past buy point
```

HTML-styled. ~2 printed pages.

## Credentials

Stored in `.env` (already gitignored), loaded via `python-dotenv`:

```
IBD_USERNAME=
IBD_PASSWORD=
GMAIL_ADDRESS=geoff.cavey@gmail.com
GMAIL_APP_PASSWORD=
ANTHROPIC_API_KEY=   # already present in project
```

### Log Credential Safety

- Logger uses a `SanitizingFormatter` that redacts values of any env var whose name contains `PASSWORD`, `KEY`, `TOKEN`, or `SECRET`
- `smtplib` debug level is never enabled (`SMTP.set_debuglevel(0)` enforced)
- Exception tracebacks are caught and logged without re-raising raw SMTP auth strings

## Error Handling

| Failure | Behaviour |
|---|---|
| Login fails | Send alert email; exit code 1 |
| PDF not found after 90 min retry | Send alert email; exit code 1 |
| Downloaded file is not valid PDF | Send alert email; exit code 1 |
| Claude returns invalid JSON (after 1 retry) | Send alert email; exit code 1 |
| Gmail send fails (primary digest) | Write digest to `reports/ibd_YYYYMMDD.html`; exit code 1 |
| Gmail send fails (alert email) | Write alert to `reports/ibd_alert_YYYYMMDD.html`; exit code 1 |

All events appended to `logs/ibd_digest.log` with credential sanitization.

## Scheduling

Windows Task Scheduler:
- Trigger: Daily at 06:00 AM
- Action: `python scripts/ibd_digest.py`
- Working directory: repo root
- **Run only when user is logged on** — required because the anti-bot fallback (`headless=False`) needs a desktop session. "Run whether user is logged on or not" is incompatible with visible-browser mode (no desktop in non-interactive Windows sessions). A home machine left running overnight satisfies this.
- On failure (exit code 1): Task Scheduler sends system notification

`scripts/install_task.ps1` registers the scheduled task automatically.

## Dependencies (new)

| Package | PyPI name | Purpose |
|---|---|---|
| `playwright` | `playwright` | Browser automation / login |
| `playwright-stealth` | `playwright-stealth` | Reduce bot-detection fingerprint |
| `pymupdf` | `pymupdf` | PDF text extraction |
| `pydantic>=2.0` | `pydantic` | Runtime validation of Claude JSON output (v2 required for `max_length` list fields and `@field_validator` syntax) |
| `python-dotenv` | `python-dotenv` | Load `.env` credentials |

`anthropic` already present. `smtplib` is stdlib.

**Setup note:** After `pip install playwright`, run `playwright install chromium` (~130 MB). The `install_task.ps1` script runs this step automatically.

## File Layout

```
scripts/
  ibd_digest.py          # main script
  install_task.ps1       # installs chromium + registers Task Scheduler entry
logs/
  ibd_digest.log         # appended per run, credentials sanitized
reports/
  ibd_YYYYMMDD.html      # fallback if email send fails
docs/superpowers/specs/
  2026-05-19-ibd-daily-digest-design.md
```

## Claude Prompt Constraints

The prompt instructs Claude explicitly:
- Return valid JSON only, no prose outside the JSON block
- `ticker`: 1–5 uppercase letters only (e.g. `"NVDA"`)
- `buy_point`: single decimal number, no dollar sign, no ranges (e.g. `"153.20"`)
- `market_pulse`: must be exactly one of `"Confirmed Uptrend"`, `"Uptrend Under Pressure"`, `"Market in Correction"`
- If a rating is unavailable, omit the stock from `buy_candidates` rather than using 0 or "N/A"

## Success Criteria

- Script runs at 6 AM with no terminal interaction
- Email arrives with Market Pulse + buy candidates (count depends on IBD content that day)
- PDF magic-byte validation rejects non-PDF downloads before Claude is called
- Claude output validated against DigestSchema (Pydantic) before email is sent
- `ticker` field validated `^[A-Z]{1,5}$` — satisfies project ticker allowlist security invariant
- `buy_point` validated as single decimal number — prevents silent rendering corruption
- Failure always produces alert email or Task Scheduler exit-code notification — never silent
- No credentials appear in source code or log files
- `playwright install chromium` included in setup script
- **First-week spot-check:** user verifies buy candidates against the source PDF for 3–5 days to confirm Claude extraction accuracy before relying on the digest for trading decisions
