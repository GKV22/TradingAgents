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

import fitz  # PyMuPDF


def extract_text(pdf_path: str) -> str:
    """Extract full text from all pages of a PDF."""
    doc = fitz.open(pdf_path)
    pages = [page.get_text() for page in doc]
    doc.close()
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
