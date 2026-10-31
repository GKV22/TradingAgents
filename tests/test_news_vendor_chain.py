"""News vendor chain: Yahoo by default; Finnhub first when opted in."""

from tradingagents.dataflows import interface
from web.settings import DEFAULT_WEB_SETTINGS


def test_web_default_news_is_yahoo():
    assert DEFAULT_WEB_SETTINGS["data_vendors"]["news_data"] == "yfinance"


def test_finnhub_registered():
    assert "finnhub" in interface.VENDOR_METHODS["get_news"]
    assert "finnhub" in interface.VENDOR_LIST


def test_missing_finnhub_key_falls_back_to_yfinance(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    monkeypatch.setattr(interface, "get_vendor", lambda cat, method=None: "finnhub,yfinance")
    monkeypatch.setitem(
        interface.VENDOR_METHODS["get_news"], "yfinance", lambda *a, **k: "YF NEWS"
    )
    assert interface.route_to_vendor("get_news", "ZS", "2026-10-16", "2026-10-23") == "YF NEWS"
