"""Finnhub company-news vendor (free tier: 60 requests/minute).

Returns headline, source, date and a short summary for each article, for any
date window (so historical runs get historical news, unlike Yahoo's
recent-only feed). The free key is read from ``FINNHUB_API_KEY``; if unset the
vendor raises ``FinnhubNotConfiguredError`` and the router moves to the next
configured vendor (e.g. ``news_data="finnhub,yfinance"``).

The key is sent in the ``X-Finnhub-Token`` header, never in the URL, so it
cannot appear in logged request errors.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone

import requests

from .config import get_config
from .errors import NoMarketDataError, VendorNotConfiguredError, VendorRateLimitError
from .symbol_utils import normalize_symbol
from .utils import safe_ticker_component

API_URL = "https://finnhub.io/api/v1/company-news"
REQUEST_TIMEOUT = 30
SUMMARY_MAX_CHARS = 500


class FinnhubNotConfiguredError(VendorNotConfiguredError):
    """Raised when FINNHUB_API_KEY is missing or rejected."""


class FinnhubRateLimitError(VendorRateLimitError):
    """Raised on HTTP 429 from Finnhub."""


def _clean(text, limit: int) -> str:
    """One line of plain text: no control characters or markdown headings."""
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(text or ""))
    text = re.sub(r"`{3,}|~{3,}|^#+", "", " ".join(text.split()))
    return text[:limit].rstrip() + ("…" if len(text) > limit else "")


def get_news_finnhub(ticker: str, start_date: str, end_date: str) -> str:
    """Company news for ``ticker`` published between start_date and end_date."""
    api_key = (os.getenv("FINNHUB_API_KEY") or "").strip()
    if not api_key:
        raise FinnhubNotConfiguredError("FINNHUB_API_KEY environment variable is not set.")
    safe_ticker_component(ticker)
    canonical = normalize_symbol(ticker)
    start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    try:
        resp = requests.get(
            API_URL,
            params={"symbol": canonical, "from": start_date, "to": end_date},
            headers={"X-Finnhub-Token": api_key},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise NoMarketDataError(ticker, canonical, f"Finnhub request failed: {type(exc).__name__}") from None
    if resp.status_code == 429:
        raise FinnhubRateLimitError("Finnhub rate limit exceeded")
    if resp.status_code in (401, 403):
        raise FinnhubNotConfiguredError(f"Finnhub rejected the API key (HTTP {resp.status_code})")
    if resp.status_code != 200:
        raise NoMarketDataError(ticker, canonical, f"Finnhub HTTP {resp.status_code}")
    try:
        items = resp.json()
    except ValueError:
        raise NoMarketDataError(ticker, canonical, "Finnhub returned non-JSON") from None
    if not isinstance(items, list):
        raise NoMarketDataError(ticker, canonical, "Finnhub returned an unexpected payload")

    articles = []
    for item in items:
        if not isinstance(item, dict):
            continue
        ts = item.get("datetime")
        if not isinstance(ts, (int, float)) or isinstance(ts, bool):
            continue
        published = datetime.fromtimestamp(ts, tz=timezone.utc)
        # Look-ahead safe: half-open window [start, end + 1 day).
        if not (start <= published < end + timedelta(days=1)):
            continue
        headline = _clean(item.get("headline"), 200)
        if headline:
            articles.append((published, headline, item))
    if not articles:
        raise NoMarketDataError(ticker, canonical, f"no Finnhub articles {start_date} to {end_date}")

    articles.sort(key=lambda a: a[0], reverse=True)
    limit = get_config().get("news_article_limit", 20)
    resolved = "" if canonical == ticker else f" (resolved to {canonical})"
    lines = [f"## {ticker}{resolved} News (Finnhub), from {start_date} to {end_date}:", ""]
    for published, headline, item in articles[:limit]:
        lines.append(f"### {headline} (source: {_clean(item.get('source'), 60) or 'Unknown'}, "
                     f"{published:%Y-%m-%d})")
        summary = _clean(item.get("summary"), SUMMARY_MAX_CHARS)
        if summary:
            lines.append(summary)
        url = str(item.get("url") or "")
        if url.startswith(("https://", "http://")):
            lines.append(f"Link: {_clean(url, 300)}")
        lines.append("")
    return "\n".join(lines)
