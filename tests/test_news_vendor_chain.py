"""Web default news chain: Alpha Vantage first, yfinance when no key is set."""

from tradingagents.dataflows import interface
from web.settings import DEFAULT_WEB_SETTINGS


def test_web_default_news_chain():
    assert DEFAULT_WEB_SETTINGS["data_vendors"]["news_data"] == "alpha_vantage,yfinance"


def test_missing_alpha_vantage_key_falls_back_to_yfinance(monkeypatch):
    monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)
    monkeypatch.setattr(interface, "get_vendor", lambda cat, method=None: "alpha_vantage,yfinance")
    monkeypatch.setitem(
        interface.VENDOR_METHODS["get_news"], "yfinance", lambda *a, **k: "YF NEWS"
    )
    assert interface.route_to_vendor("get_news", "ZS", "2026-10-16", "2026-10-23") == "YF NEWS"
