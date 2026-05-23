# IBD Weekly Digest Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically download the weekly eIBD PDF, extract stock buy candidates via Claude, and email an HTML digest every Monday at 6 AM.

**Architecture:** Playwright logs into investors.com, navigates to the eIBD SPA, and downloads the full edition PDF. PyMuPDF extracts text. Claude returns structured JSON (Pydantic-validated DigestSchema). smtplib sends an HTML email. Windows Task Scheduler triggers weekly on Monday.

**Tech Stack:** Python 3.10+, Playwright + playwright-stealth, PyMuPDF (fitz), Pydantic v2, anthropic SDK, smtplib, python-dotenv, Windows Task Scheduler.

**Spec:** `docs/superpowers/specs/2026-05-19-ibd-daily-digest-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `scripts/ibd_schema.py` | Create | Pydantic models: BuyCandidate, DigestSchema, validators |
| `scripts/ibd_digest.py` | Create | All functions + main() + CLI entry point |
| `scripts/install_task.ps1` | Create | Install chromium + register Windows Task Scheduler |
| `tests/test_ibd_schema.py` | Create | Unit tests for schema validation |
| `tests/test_ibd_digest.py` | Create | Unit tests for extract, summarize, render, email, logging |
| `pyproject.toml` | Modify | Add new dependencies |
| `.env.example` | Modify | Add IBD_USERNAME, IBD_PASSWORD, GMAIL_* vars |
| `logs/.gitkeep` | Create | Ensure logs/ directory tracked in git |
| `reports/.gitkeep` | Create | Ensure reports/ directory tracked in git |

---

## Chunk 1: Setup

### Task 1: Add dependencies and environment template

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Create: `logs/.gitkeep`
- Create: `reports/.gitkeep`

- [ ] **Step 1.1: Add dependencies to pyproject.toml**

In `pyproject.toml`, add to the `dependencies` list:

```toml
    "playwright>=1.44.0",
    "playwright-stealth>=1.0.6",
    "pymupdf>=1.24.0",
    "pydantic>=2.0",
    "python-dotenv>=1.0.0",
```

Note: `pydantic>=2.0` is already installed (v2.13.3) but not declared — add it explicitly.

- [ ] **Step 1.2: Update .env.example**

Append to `.env.example`:

```
# IBD Weekly Digest
IBD_USERNAME=
IBD_PASSWORD=
GMAIL_ADDRESS=
GMAIL_APP_PASSWORD=
```

- [ ] **Step 1.3: Create directory placeholders**

```bash
echo "" > logs/.gitkeep
```

Note: `reports/` already exists on this machine with unrelated `.md` files from prior runs. Do NOT add `reports/.gitkeep` — it already exists. Instead, add `reports/*.html` to `.gitignore` so generated digests are excluded. The existing `.md` files in `reports/` can stay untracked or be committed separately — they are out of scope for this plan.

Note: `logs/*.log` does NOT need to be added to `.gitignore` — the existing pattern `*.log` on line 59 already covers all subdirectories.

In `.gitignore`, add only:
```
reports/*.html
```

- [ ] **Step 1.4: Install packages and Playwright browser**

```bash
pip install playwright playwright-stealth pymupdf python-dotenv
playwright install chromium
```

Expected: `chromium` downloads ~130 MB to user data dir. Final line: `chromium ... 1 installation(s) finished.`

- [ ] **Step 1.5: Verify installs**

```bash
python -c "import playwright; import fitz; import playwright_stealth; import dotenv; print('all ok')"
```

Expected output: `all ok`

- [ ] **Step 1.6: Commit**

```bash
git add pyproject.toml .env.example logs/.gitkeep .gitignore
git commit -m "chore(ibd-digest): add dependencies and directory structure"
```

---

## Chunk 2: Schema

### Task 2: Pydantic models for Claude output

**Files:**
- Create: `scripts/ibd_schema.py`
- Create: `tests/test_ibd_schema.py`

- [ ] **Step 2.1: Write failing tests**

Create `tests/test_ibd_schema.py`:

```python
import pytest
from scripts.ibd_schema import BuyCandidate, DigestSchema

# --- BuyCandidate ---

def test_buy_candidate_valid():
    c = BuyCandidate(
        ticker="NVDA",
        company="Nvidia",
        buy_point="153.20",
        rs_rating=97,
        composite_rating=98,
        rationale="Breaking out. Strong earnings.",
    )
    assert c.ticker == "NVDA"
    assert c.buy_point == "153.20"

def test_ticker_rejects_lowercase():
    with pytest.raises(Exception, match="Invalid ticker"):
        BuyCandidate(ticker="nvda", company="x", buy_point="100", rs_rating=90, composite_rating=90, rationale="x")

def test_ticker_rejects_too_long():
    with pytest.raises(Exception, match="Invalid ticker"):
        BuyCandidate(ticker="TOOLONG", company="x", buy_point="100", rs_rating=90, composite_rating=90, rationale="x")

def test_ticker_rejects_numbers():
    with pytest.raises(Exception, match="Invalid ticker"):
        BuyCandidate(ticker="NV1A", company="x", buy_point="100", rs_rating=90, composite_rating=90, rationale="x")

def test_buy_point_rejects_dollar_sign():
    with pytest.raises(Exception, match="buy_point"):
        BuyCandidate(ticker="NVDA", company="x", buy_point="$153.20", rs_rating=90, composite_rating=90, rationale="x")

def test_buy_point_rejects_range():
    with pytest.raises(Exception, match="buy_point"):
        BuyCandidate(ticker="NVDA", company="x", buy_point="153.20-155.00", rs_rating=90, composite_rating=90, rationale="x")

def test_buy_point_rejects_text():
    with pytest.raises(Exception, match="buy_point"):
        BuyCandidate(ticker="NVDA", company="x", buy_point="near 153", rs_rating=90, composite_rating=90, rationale="x")

def test_rs_rating_out_of_range():
    with pytest.raises(Exception):
        BuyCandidate(ticker="NVDA", company="x", buy_point="100", rs_rating=100, composite_rating=90, rationale="x")

def test_rs_rating_zero():
    with pytest.raises(Exception):
        BuyCandidate(ticker="NVDA", company="x", buy_point="100", rs_rating=0, composite_rating=90, rationale="x")

# --- DigestSchema ---

def make_valid_digest(**overrides):
    defaults = dict(
        date="2026-05-19",
        market_pulse="Confirmed Uptrend",
        distribution_days=2,
        buy_candidates=[],
        stocks_to_watch=[],
        avoid_extended=[],
    )
    defaults.update(overrides)
    return DigestSchema(**defaults)

def test_digest_valid():
    d = make_valid_digest()
    assert d.market_pulse == "Confirmed Uptrend"
    assert d.distribution_days == 2

def test_digest_invalid_market_pulse():
    with pytest.raises(Exception, match="market_pulse"):
        make_valid_digest(market_pulse="Uptrend")

def test_digest_distribution_days_negative():
    with pytest.raises(Exception):
        make_valid_digest(distribution_days=-1)

def test_digest_buy_candidates_max_8():
    candidate = dict(
        ticker="NVDA", company="x", buy_point="100",
        rs_rating=90, composite_rating=90, rationale="x"
    )
    with pytest.raises(Exception):
        make_valid_digest(buy_candidates=[candidate] * 9)

def test_digest_empty_buy_candidates_is_valid():
    d = make_valid_digest(buy_candidates=[])
    assert d.buy_candidates == []

def test_all_three_market_pulse_values():
    for pulse in ["Confirmed Uptrend", "Uptrend Under Pressure", "Market in Correction"]:
        d = make_valid_digest(market_pulse=pulse)
        assert d.market_pulse == pulse

def test_ticker_boundary_one_char():
    c = BuyCandidate(ticker="A", company="x", buy_point="100", rs_rating=90, composite_rating=90, rationale="x")
    assert c.ticker == "A"

def test_ticker_boundary_five_chars():
    c = BuyCandidate(ticker="BRKBX", company="x", buy_point="100", rs_rating=90, composite_rating=90, rationale="x")
    assert c.ticker == "BRKBX"

def test_buy_candidates_exactly_eight_valid():
    candidate = dict(ticker="NVDA", company="x", buy_point="100", rs_rating=90, composite_rating=90, rationale="x")
    d = make_valid_digest(buy_candidates=[candidate] * 8)
    assert len(d.buy_candidates) == 8
```

- [ ] **Step 2.2: Run tests — expect all FAIL (module not found)**

```bash
python -m pytest tests/test_ibd_schema.py -v
```

Expected: `ModuleNotFoundError: No module named 'scripts.ibd_schema'`

- [ ] **Step 2.3: Implement ibd_schema.py**

Create `scripts/__init__.py` (empty) so `scripts` is importable as a package.

Create `scripts/ibd_schema.py`:

```python
import re
from pydantic import BaseModel, Field, field_validator

VALID_MARKET_PULSE = {
    "Confirmed Uptrend",
    "Uptrend Under Pressure",
    "Market in Correction",
}


class BuyCandidate(BaseModel):
    ticker: str
    company: str
    buy_point: str
    rs_rating: int = Field(ge=1, le=99)
    composite_rating: int = Field(ge=1, le=99)
    rationale: str

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        if not re.fullmatch(r"[A-Z]{1,5}", v):
            raise ValueError(f"Invalid ticker: {v!r} — must be 1–5 uppercase letters")
        return v

    @field_validator("buy_point")
    @classmethod
    def validate_buy_point(cls, v: str) -> str:
        if not re.fullmatch(r"\d+(\.\d{1,2})?", v):
            raise ValueError(
                f"buy_point must be a single decimal number (e.g. '153.20'), got: {v!r}"
            )
        return v


class DigestSchema(BaseModel):
    date: str
    market_pulse: str
    distribution_days: int = Field(ge=0)
    buy_candidates: list[BuyCandidate] = Field(max_length=8)
    stocks_to_watch: list[str]
    avoid_extended: list[str]

    @field_validator("market_pulse")
    @classmethod
    def validate_pulse(cls, v: str) -> str:
        if v not in VALID_MARKET_PULSE:
            raise ValueError(
                f"Unknown market_pulse: {v!r}. "
                f"Must be one of: {sorted(VALID_MARKET_PULSE)}"
            )
        return v
```

- [ ] **Step 2.4: Run tests — expect all PASS**

```bash
python -m pytest tests/test_ibd_schema.py -v
```

Expected: all green, 0 failures.

- [ ] **Step 2.5: Commit**

```bash
git add scripts/__init__.py scripts/ibd_schema.py tests/test_ibd_schema.py
git commit -m "feat(ibd-digest): add DigestSchema + BuyCandidate Pydantic models"
```

---

## Chunk 3: Core pipeline functions

### Task 3: Sanitizing logger

**Files:**
- Create: `scripts/ibd_digest.py` (partial — logger only)
- Create: `tests/test_ibd_digest.py` (partial)

- [ ] **Step 3.1: Write failing tests for SanitizingFormatter**

Create `tests/test_ibd_digest.py`:

```python
import logging
import logging.handlers  # must import explicitly — `import logging` alone does not pull in submodule
import os
import pytest


def test_sanitizing_formatter_redacts_password(monkeypatch):
    monkeypatch.setenv("IBD_PASSWORD", "supersecret")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "apppass123")

    from scripts.ibd_digest import make_logger
    logger = make_logger("test_sanitize")
    handler = logging.handlers.MemoryHandler(capacity=100)
    logger.addHandler(handler)
    logger.error("Failed with password=supersecret and apppass123")
    handler.flush()

    # Grab formatted output
    import io
    stream = io.StringIO()
    sh = logging.StreamHandler(stream)
    from scripts.ibd_digest import SanitizingFormatter
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
```

- [ ] **Step 3.2: Run — expect FAIL**

```bash
python -m pytest tests/test_ibd_digest.py::test_sanitizing_formatter_redacts_password -v
```

Expected: `ModuleNotFoundError` or `ImportError`.

- [ ] **Step 3.3: Implement logger in ibd_digest.py**

Create `scripts/ibd_digest.py`:

```python
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
    # File handler
    fh = logging.FileHandler(LOGS_DIR / "ibd_digest.log", encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    return logger


log = make_logger()
```

- [ ] **Step 3.4: Run tests — expect PASS**

```bash
python -m pytest tests/test_ibd_digest.py -v
```

- [ ] **Step 3.5: Commit**

```bash
git add scripts/ibd_digest.py tests/test_ibd_digest.py
git commit -m "feat(ibd-digest): add sanitizing logger"
```

---

### Task 4: PDF text extraction

**Files:**
- Modify: `scripts/ibd_digest.py` (add `extract_text`)
- Modify: `tests/test_ibd_digest.py` (add tests)

- [ ] **Step 4.1: Write failing test**

Add to `tests/test_ibd_digest.py`:

```python
import fitz  # PyMuPDF
import tempfile
import os


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
        os.unlink(path)
```

- [ ] **Step 4.2: Run — expect FAIL**

```bash
python -m pytest tests/test_ibd_digest.py::test_extract_text_returns_content -v
```

Expected: `ImportError: cannot import name 'extract_text'`

- [ ] **Step 4.3: Implement extract_text**

Add to `scripts/ibd_digest.py`:

```python
import fitz  # PyMuPDF


def extract_text(pdf_path: str) -> str:
    """Extract full text from all pages of a PDF."""
    doc = fitz.open(pdf_path)
    pages = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(pages)
```

- [ ] **Step 4.4: Run tests — expect PASS**

```bash
python -m pytest tests/test_ibd_digest.py -v
```

- [ ] **Step 4.5: Commit**

```bash
git add scripts/ibd_digest.py tests/test_ibd_digest.py
git commit -m "feat(ibd-digest): add PDF text extraction"
```

---

### Task 5: Claude summarization

**Files:**
- Modify: `scripts/ibd_digest.py` (add `summarize`)
- Modify: `tests/test_ibd_digest.py`

- [ ] **Step 5.1: Write failing tests**

Add to `tests/test_ibd_digest.py`:

```python
import json
from unittest.mock import MagicMock, patch


VALID_JSON = json.dumps({
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
})


def _mock_anthropic(response_text: str):
    """Return a mock anthropic client that returns response_text."""
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
    mock_client = _mock_anthropic("still not json")
    mock_client.messages.create.return_value.content = [MagicMock(text="bad")]
    with pytest.raises(SummarizationError):
        summarize("pdf text", client=mock_client)


def test_summarize_prompt_handles_curly_braces_in_text():
    """Regression: SUMMARIZE_PROMPT.format() crashed on { } in PDF text. Use replace() instead."""
    from scripts.ibd_digest import summarize
    mock_client = _mock_anthropic(VALID_JSON)
    # PDF text with curly braces must not crash prompt construction
    result = summarize("Stocks with {1} or {2} distribution days", client=mock_client)
    assert result.market_pulse == "Confirmed Uptrend"


def test_summarize_empty_buy_candidates_valid():
    from scripts.ibd_digest import summarize
    no_buys = json.dumps({
        "date": "2026-05-19",
        "market_pulse": "Market in Correction",
        "distribution_days": 5,
        "buy_candidates": [],
        "stocks_to_watch": [],
        "avoid_extended": [],
    })
    mock_client = _mock_anthropic(no_buys)
    result = summarize("pdf text", client=mock_client)
    assert result.buy_candidates == []
```

- [ ] **Step 5.2: Run — expect FAIL**

```bash
python -m pytest tests/test_ibd_digest.py::test_summarize_valid_json -v
```

Expected: `ImportError: cannot import name 'summarize'`

- [ ] **Step 5.3: Implement summarize**

Add to `scripts/ibd_digest.py`:

```python
import anthropic as anthropic_sdk

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
      "rationale": "<exactly 2 sentences from IBD's commentary>"
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
        # drop first and last fence lines
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner).strip()
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
        raw = response.content[0].text
        try:
            json_str = _extract_json(raw)
            data = json.loads(json_str)
            return DigestSchema(**data)
        except Exception as exc:
            log.warning("summarize attempt %d failed: %s", attempt + 1, exc)
            if attempt == 0:
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content": CORRECTION_PROMPT})

    raise SummarizationError("Claude returned invalid JSON after 2 attempts")
```

- [ ] **Step 5.4: Run tests — expect PASS**

```bash
python -m pytest tests/test_ibd_digest.py -v
```

- [ ] **Step 5.5: Commit**

```bash
git add scripts/ibd_digest.py tests/test_ibd_digest.py
git commit -m "feat(ibd-digest): add Claude summarization with Pydantic validation"
```

---

### Task 6: HTML rendering

**Files:**
- Modify: `scripts/ibd_digest.py` (add `render_html`)
- Modify: `tests/test_ibd_digest.py`

- [ ] **Step 6.1: Write failing tests**

Add to `tests/test_ibd_digest.py`:

```python
from scripts.ibd_schema import DigestSchema, BuyCandidate


def _make_digest(**overrides) -> DigestSchema:
    defaults = dict(
        date="2026-05-19",
        market_pulse="Confirmed Uptrend",
        distribution_days=2,
        buy_candidates=[
            BuyCandidate(
                ticker="NVDA",
                company="Nvidia Corp",
                buy_point="153.20",
                rs_rating=97,
                composite_rating=98,
                rationale="Breaking out. Strong earnings.",
            )
        ],
        stocks_to_watch=["AAPL — forming handle"],
        avoid_extended=["META — extended"],
    )
    defaults.update(overrides)
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
    assert "2" in html  # distribution days


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
```

- [ ] **Step 6.2: Run — expect FAIL**

```bash
python -m pytest tests/test_ibd_digest.py::test_render_html_contains_ticker -v
```

- [ ] **Step 6.3: Implement render_html and render_subject**

Add to `scripts/ibd_digest.py`:

```python
from scripts.ibd_schema import DigestSchema


def render_subject(edition_date: str) -> str:
    return f"IBD Weekly Digest — Week of {edition_date}"


def render_html(digest: DigestSchema) -> str:
    candidates_html = ""
    if digest.buy_candidates:
        rows = ""
        for c in digest.buy_candidates:
            rows += f"""
            <div class="candidate">
              <div class="ticker-row">
                <strong>{c.ticker}</strong> — {c.company}
              </div>
              <div class="meta">
                Buy point: <strong>${c.buy_point}</strong> &nbsp;|&nbsp;
                RS Rating: <strong>{c.rs_rating}</strong> &nbsp;|&nbsp;
                Composite: <strong>{c.composite_rating}</strong>
              </div>
              <div class="rationale">{c.rationale}</div>
            </div>"""
        candidates_html = f'<h2>Top Buy Candidates ({len(digest.buy_candidates)})</h2>{rows}'
    else:
        candidates_html = "<h2>Top Buy Candidates</h2><p>No buy candidates this week.</p>"

    watch_items = "".join(f"<li>{w}</li>" for w in digest.stocks_to_watch)
    avoid_items = "".join(f"<li>{a}</li>" for a in digest.avoid_extended)

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
```

- [ ] **Step 6.4: Run tests — expect PASS**

```bash
python -m pytest tests/test_ibd_digest.py -v
```

- [ ] **Step 6.5: Commit**

```bash
git add scripts/ibd_digest.py tests/test_ibd_digest.py
git commit -m "feat(ibd-digest): add HTML rendering"
```

---

### Task 7: Email sending

**Files:**
- Modify: `scripts/ibd_digest.py` (add `send_email`, `send_alert`)
- Modify: `tests/test_ibd_digest.py`

- [ ] **Step 7.1: Write failing tests**

Add to `tests/test_ibd_digest.py`:

```python
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
    # Verify smtplib debug level never set
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
```

- [ ] **Step 7.2: Run — expect FAIL**

```bash
python -m pytest tests/test_ibd_digest.py::test_send_email_uses_starttls -v
```

- [ ] **Step 7.3: Implement send_email and send_alert**

Add to `scripts/ibd_digest.py`:

```python
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email(html_body: str, subject: str) -> None:
    """Send HTML email via Gmail SMTP. Raises on failure."""
    gmail_address = os.environ["GMAIL_ADDRESS"]
    gmail_password = os.environ["GMAIL_APP_PASSWORD"]

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
    """Send a plain-text alert email. Falls back to file if SMTP fails."""
    subject = "IBD Digest ERROR"
    html = f"<html><body><h2>IBD Digest Error</h2><pre>{message}</pre></body></html>"
    try:
        send_email(html, subject)
    except Exception as exc:
        log.error("Alert email also failed: %s", exc)
        fallback = REPORTS_DIR / f"ibd_alert_{date.today().isoformat()}.html"
        fallback.write_text(f"<html><body><pre>{message}</pre></body></html>")
        log.info("Alert written to %s", fallback)
```

- [ ] **Step 7.4: Run tests — expect PASS**

```bash
python -m pytest tests/test_ibd_digest.py -v
```

- [ ] **Step 7.5: Commit**

```bash
git add scripts/ibd_digest.py tests/test_ibd_digest.py
git commit -m "feat(ibd-digest): add Gmail SMTP email + alert sender"
```

---

## Chunk 4: Browser automation + orchestrator

### Task 8: Playwright browser automation

**Files:**
- Modify: `scripts/ibd_digest.py` (add `login_and_download_pdf`)

Note: Full unit testing of Playwright is impractical — browser interaction requires a live site. This task provides implementation + a manual integration test procedure.

- [ ] **Step 8.1: Implement login_and_download_pdf**

Add to `scripts/ibd_digest.py`:

```python
import time


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
    from playwright_stealth import stealth_sync

    username = os.environ["IBD_USERNAME"]
    password = os.environ["IBD_PASSWORD"]

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
                stealth_sync(page)

                # Step 1: Login on investors.com
                log.info("Navigating to investors.com for login...")
                page.goto(LOGIN_URL, wait_until="networkidle")

                # Fill login form — selectors may need adjustment if site changes
                page.fill('input[name="email"], input[type="email"]', username)
                page.fill('input[name="password"], input[type="password"]', password)
                page.click('button[type="submit"], input[type="submit"]')
                page.wait_for_load_state("networkidle")

                if "login" in page.url.lower() or "signin" in page.url.lower():
                    raise RuntimeError("Login failed — still on login page after submit")

                log.info("Login succeeded. Navigating to eIBD...")

                # Step 2: Navigate to eIBD SPA
                page.goto(EIBD_URL, wait_until="networkidle")

                # Step 3: Wait for JS eReader to initialise
                # Wait for a download button to appear (adjust selector after inspecting the page)
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

                # Save to temp file
                tmp = tempfile.mktemp(suffix=".pdf")
                download.save_as(tmp)
                download_path = tmp
                context.close()
                browser.close()

            # Step 5: Validate
            if not _is_valid_pdf(download_path):
                log.warning("Downloaded file is not a valid PDF (magic bytes check failed)")
                if download_path:
                    Path(download_path).unlink(missing_ok=True)
                if attempt < MAX_RETRIES:
                    continue
                raise RuntimeError("Downloaded file is not a valid PDF after all retries")

            log.info("Valid PDF downloaded: %s", download_path)
            return download_path

        except RuntimeError:
            raise
        except Exception as exc:
            log.warning("Attempt %d failed: %s", attempt + 1, exc)
            if download_path:
                Path(download_path).unlink(missing_ok=True)
            if attempt >= MAX_RETRIES:
                raise RuntimeError(f"Failed to download eIBD PDF after {MAX_RETRIES + 1} attempts: {exc}") from exc

    raise RuntimeError("Unreachable")
```

- [ ] **Step 8.2: Manual integration test (run this once with real credentials)**

```bash
python -c "
from dotenv import load_dotenv; load_dotenv()
from scripts.ibd_digest import login_and_download_pdf
path = login_and_download_pdf(headless=False)  # visible browser first
print('Downloaded to:', path)
"
```

Expected: Chromium opens, logs into investors.com, navigates to eIBD, downloads PDF. Check `path` is a valid PDF you can open.

If the download button selector doesn't match, open DevTools on `research.investors.com/eIBD/#/` and inspect the download button's HTML attributes. Update the selector in `login_and_download_pdf()` accordingly.

- [ ] **Step 8.3: Commit**

```bash
git add scripts/ibd_digest.py
git commit -m "feat(ibd-digest): add Playwright browser automation + PDF download"
```

---

### Task 9: Main orchestrator + CLI

**Files:**
- Modify: `scripts/ibd_digest.py` (add `cleanup`, `main`)
- Modify: `tests/test_ibd_digest.py`

- [ ] **Step 9.1: Write failing test for --pdf bypass**

Add to `tests/test_ibd_digest.py`:

```python
import subprocess
import sys
import os


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
```

- [ ] **Step 9.2: Run — expect FAIL**

```bash
python -m pytest tests/test_ibd_digest.py::test_pdf_flag_bypasses_browser -v
```

- [ ] **Step 9.3: Implement cleanup and main**

Add to `scripts/ibd_digest.py`:

```python
import argparse


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

    # Write HTML backup to reports/ (useful for spot-checking against source PDF)
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
```

- [ ] **Step 9.4: Run all tests — expect PASS**

```bash
python -m pytest tests/test_ibd_schema.py tests/test_ibd_digest.py -v
```

Expected: all green.

- [ ] **Step 9.5: Commit**

```bash
git add scripts/ibd_digest.py tests/test_ibd_digest.py
git commit -m "feat(ibd-digest): add main orchestrator + --pdf CLI bypass"
```

---

### Task 10: Windows Task Scheduler setup script

**Files:**
- Create: `scripts/install_task.ps1`

- [ ] **Step 10.1: Implement install_task.ps1**

Create `scripts/install_task.ps1`:

```powershell
# IBD Weekly Digest — Windows Task Scheduler installer
# Run once as Administrator: powershell -ExecutionPolicy Bypass -File scripts\install_task.ps1

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python   = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Script   = Join-Path $RepoRoot "scripts\ibd_digest.py"
$TaskName = "IBD Weekly Digest"

# Verify Python exists
if (-not (Test-Path $Python)) {
    Write-Error "Python not found at $Python — activate venv first."
    exit 1
}

# Install Playwright chromium browser
Write-Host "Installing Playwright chromium..." -ForegroundColor Cyan
& $Python -m playwright install chromium
if ($LASTEXITCODE -ne 0) { Write-Error "playwright install chromium failed"; exit 1 }

# Remove existing task if present
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing task '$TaskName'."
}

# Create trigger: weekly, every Monday at 06:00
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "06:00AM"

# Action: run python scripts/ibd_digest.py from repo root
# Script path is double-quoted in case it contains spaces
$action = New-ScheduledTaskAction `
    -Execute $Python `
    -Argument "`"$Script`"" `
    -WorkingDirectory $RepoRoot

# Settings: stop if runs > 2 hours, start if missed
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -RunOnlyIfNetworkAvailable `
    -StartWhenAvailable

# Principal: run only when user is logged on interactively (required for headless=False fallback)
$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

# Register task
Register-ScheduledTask `
    -TaskName $TaskName `
    -Trigger $trigger `
    -Action $action `
    -Settings $settings `
    -Principal $principal `
    -Force

Write-Host "`nTask '$TaskName' registered successfully." -ForegroundColor Green
Write-Host "It will run every Monday at 06:00 AM when you are logged on."
Write-Host "`nTo test immediately:"
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
```

- [ ] **Step 10.2: Run install script (requires Admin PowerShell)**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_task.ps1
```

Expected output ends with: `Task 'IBD Weekly Digest' registered successfully.`

- [ ] **Step 10.3: Verify task in Task Scheduler**

```powershell
Get-ScheduledTask -TaskName "IBD Weekly Digest" | Select-Object TaskName, State
```

Expected: `TaskName: IBD Weekly Digest, State: Ready`

- [ ] **Step 10.4: Test run with --pdf to avoid live site dependency**

```powershell
# Download a real eIBD PDF manually first, then:
& ".venv\Scripts\python.exe" scripts\ibd_digest.py --pdf path\to\eibd.pdf
```

Expected: email arrives at geoff.cavey@gmail.com.

- [ ] **Step 10.5: Commit**

```bash
git add scripts/install_task.ps1
git commit -m "feat(ibd-digest): add Task Scheduler install script"
```

---

## Final Checklist

- [ ] `python -m pytest tests/test_ibd_schema.py tests/test_ibd_digest.py -v` — all pass
- [ ] `.env` populated with real IBD_USERNAME, IBD_PASSWORD, GMAIL_ADDRESS, GMAIL_APP_PASSWORD
- [ ] Manual integration test: `python scripts/ibd_digest.py --pdf <real-pdf>` — email received
- [ ] Browser integration test: `python scripts/ibd_digest.py` (live site, headless=False first)
- [ ] Task Scheduler registered; test trigger fires and email arrives
- [ ] First 2–3 weeks: spot-check digest buy candidates against source eIBD before trading on them

## Selector Adjustment Note

The download button selector in `login_and_download_pdf()` is a best-guess. After first run, if it fails to find the button:

1. Open `https://research.investors.com/eIBD/#/` in Chrome while logged in
2. Right-click the download button → Inspect
3. Note its `id`, `class`, `aria-label`, or text
4. Update the `page.wait_for_selector(...)` and `page.click(...)` calls in `login_and_download_pdf()`
