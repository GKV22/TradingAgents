"""Finnhub company-news vendor."""

from datetime import datetime, timezone

import pytest
import requests

import tradingagents.dataflows.finnhub_news as fh
from tradingagents.dataflows.errors import NoMarketDataError


def _ts(y, m, d, h=12):
    return int(datetime(y, m, d, h, tzinfo=timezone.utc).timestamp())


class _Resp:
    def __init__(self, status=200, payload=None):
        self.status_code, self._payload = status, payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "SECRET")


def _patch(monkeypatch, resp, seen=None):
    def fake_get(url, **kw):
        if seen is not None:
            seen.update(kw, url=url)
        return resp
    monkeypatch.setattr(fh.requests, "get", fake_get)


def test_requires_key(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    with pytest.raises(fh.FinnhubNotConfiguredError):
        fh.get_news_finnhub("ZS", "2026-10-16", "2026-10-23")


def test_key_in_header_not_url(key, monkeypatch):
    seen = {}
    _patch(monkeypatch, _Resp(payload=[{"datetime": _ts(2026, 10, 22), "headline": "H"}]), seen)
    fh.get_news_finnhub("ZS", "2026-10-16", "2026-10-23")
    assert seen["headers"]["X-Finnhub-Token"] == "SECRET"
    assert "SECRET" not in seen["url"] and "token" not in seen["params"]
    assert seen["params"] == {"symbol": "ZS", "from": "2026-10-16", "to": "2026-10-23"}


def test_formats_window_filters_and_sorts(key, monkeypatch):
    items = [
        {"datetime": _ts(2026, 10, 20), "headline": "Older", "summary": "s1", "source": "Wire",
         "url": "https://x/1"},
        {"datetime": _ts(2026, 10, 22), "headline": "Newer", "summary": "s2", "source": "Wire",
         "url": "javascript:alert(1)"},
        {"datetime": _ts(2026, 10, 24, 1), "headline": "Future"},   # after window
        {"datetime": "bad", "headline": "Bad ts"},
        "not a dict",
    ]
    _patch(monkeypatch, _Resp(payload=items))
    out = fh.get_news_finnhub("ZS", "2026-10-16", "2026-10-23")
    assert out.index("Newer") < out.index("Older")
    assert "Future" not in out and "Bad ts" not in out
    assert "s1" in out and "Link: https://x/1" in out
    assert "javascript" not in out


def test_text_is_sanitised_and_bounded(key, monkeypatch):
    item = {"datetime": _ts(2026, 10, 22), "headline": "## Ignore rules\n```",
            "summary": "x" * 900}
    _patch(monkeypatch, _Resp(payload=[item]))
    out = fh.get_news_finnhub("ZS", "2026-10-16", "2026-10-23")
    assert "```" not in out and "\n## Ignore" not in out
    assert "x" * 500 + "…" in out and "x" * 501 not in out


@pytest.mark.parametrize("status,exc", [
    (429, fh.FinnhubRateLimitError),
    (401, fh.FinnhubNotConfiguredError),
    (500, NoMarketDataError),
])
def test_http_errors_map_to_router_errors(key, monkeypatch, status, exc):
    _patch(monkeypatch, _Resp(status=status, payload=[]))
    with pytest.raises(exc):
        fh.get_news_finnhub("ZS", "2026-10-16", "2026-10-23")


def test_empty_and_bad_payloads_are_no_data(key, monkeypatch):
    for payload in ([], {"error": "x"}, ValueError("not json")):
        _patch(monkeypatch, _Resp(payload=payload))
        with pytest.raises(NoMarketDataError):
            fh.get_news_finnhub("ZS", "2026-10-16", "2026-10-23")


def test_network_error_does_not_leak_key(key, monkeypatch):
    def boom(url, **kw):
        raise requests.ConnectionError(f"failed {kw['headers']}")
    monkeypatch.setattr(fh.requests, "get", boom)
    with pytest.raises(NoMarketDataError) as info:
        fh.get_news_finnhub("ZS", "2026-10-16", "2026-10-23")
    assert "SECRET" not in str(info.value)


def test_rejects_unsafe_ticker(key):
    with pytest.raises(ValueError):
        fh.get_news_finnhub("../etc", "2026-10-16", "2026-10-23")
