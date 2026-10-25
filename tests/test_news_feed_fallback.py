"""Empty yfinance news is reported as a feed failure, with a Search fallback."""

from datetime import datetime, timezone

import tradingagents.dataflows.yfinance_news as ynews


class _EmptyTicker:
    def __init__(self, symbol):
        pass

    def get_news(self, count):
        return []


class _FakeSearch:
    def __init__(self, query, news_count, enable_fuzzy_query):
        ts = int(datetime(2026, 10, 22, 15, tzinfo=timezone.utc).timestamp())
        self.news = [
            {"title": "Zscaler beats", "publisher": "Wire", "link": "u1",
             "providerPublishTime": ts, "relatedTickers": ["ZS", "PANW"]},
            {"title": "Unrelated", "publisher": "Wire", "link": "u2",
             "providerPublishTime": ts, "relatedTickers": ["AAPL"]},
        ]


def _patch(monkeypatch, search=_FakeSearch):
    monkeypatch.setattr(ynews.yf, "Ticker", _EmptyTicker)
    monkeypatch.setattr(ynews.yf, "Search", search)
    monkeypatch.setattr(ynews, "yf_retry", lambda fn: fn())


def test_search_fallback_keeps_only_related_articles(monkeypatch):
    _patch(monkeypatch)
    out = ynews.get_news_yfinance("ZS", "2026-10-16", "2026-10-23")
    assert "Zscaler beats" in out
    assert "Unrelated" not in out


def test_total_outage_is_labelled_as_feed_failure(monkeypatch):
    class _NoNews:
        def __init__(self, **kw):
            self.news = []

    _patch(monkeypatch, search=_NoNews)
    out = ynews.get_news_yfinance("ZS", "2026-10-16", "2026-10-23")
    assert out.startswith("NEWS FEED RETURNED NO DATA")
    assert "not" in out.lower() and "evidence" in out


def test_search_error_does_not_break_fetch(monkeypatch):
    def _boom(**kw):
        raise RuntimeError("rate limited")

    _patch(monkeypatch, search=_boom)
    out = ynews.get_news_yfinance("ZS", "2026-10-16", "2026-10-23")
    assert out.startswith("NEWS FEED RETURNED NO DATA")


def test_window_miss_reports_fetched_count(monkeypatch):
    _patch(monkeypatch)
    out = ynews.get_news_yfinance("ZS", "2025-01-01", "2025-01-10")
    assert "1 articles fetched" in out
