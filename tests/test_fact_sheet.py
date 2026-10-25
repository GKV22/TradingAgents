"""Fact sheet: deterministic figures, look-ahead gating, never raises."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

import tradingagents.dataflows.fact_sheet as fs
from tradingagents.agents.utils.agent_utils import get_instrument_context_from_state


def _rows(end="2026-10-23"):
    dates = pd.bdate_range(end=end, periods=260)
    close = np.linspace(120, 255.15, len(dates))
    return pd.DataFrame({"Date": dates, "Close": close})


class _FakeTicker:
    def __init__(self, *a):
        col = pd.Timestamp("2026-07-31")
        self.quarterly_balance_sheet = pd.DataFrame(
            {col: [928.35e6, 2545.8e6, 1855.82e6, 163.055e6]},
            index=["Cash And Cash Equivalents", "Other Short Term Investments",
                   "Total Debt", "Ordinary Shares Number"])
        self.quarterly_income_stmt = pd.DataFrame({col: [161.872e6]}, index=["Diluted Average Shares"])
        self.calendar = {}
        self.revenue_estimate = pd.DataFrame(
            {"avg": [3.93e9], "growth": [0.173], "numberOfAnalysts": [np.int64(46)]}, index=["0y"])
        self.earnings_estimate = pd.DataFrame()
        self.analyst_price_targets = {"mean": 235.19, "median": 247.0, "low": 164.75, "high": 298.0}
        self.recommendations = pd.DataFrame(
            {"strongBuy": [np.int64(7)], "buy": [np.int64(29)], "hold": [np.int64(11)],
             "sell": [np.int64(0)], "strongSell": [np.int64(0)]})
        self.upgrades_downgrades = pd.DataFrame()
        self.earnings_history = pd.DataFrame()
        self.info = {"shortPercentOfFloat": 0.054, "shortRatio": 1.5}


SNAP = {
    "fiscal_year_end": "0731",
    "latest_filing": {"form": "10-K", "filed": date(2026, 9, 3), "period_end": date(2026, 7, 31)},
    "quarters": [
        {"start": date(2025, 5, 1), "end": date(2025, 7, 31), "revenue": 719.2e6,
         "receivables": 992.2e6, "dso": 127.0},
        {"start": date(2026, 5, 1), "end": date(2026, 7, 31), "revenue": 898.2e6,
         "receivables": 1149.1e6, "dso": 118.0},
    ],
    "rpo": {date(2025, 7, 31): 5.78e9, date(2026, 7, 31): 7.3654e9},
    "deferred_revenue": {date(2026, 7, 31): 2.9258e9},
    "sbc_annual": {"end": date(2026, 7, 31), "value": 821.9e6},
    "acquisitions_annual": None,
    "buybacks_annual": {"end": date(2021, 7, 31), "value": 0.0},
    "earnings_release": {"filed": date(2026, 9, 3), "url": "https://www.sec.gov/x",
                         "headline": "Q4 results", "outlook": "Financial Outlook\nRevenue $3.9B ```"},
}


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(fs, "_verified_rows", lambda s, d: _rows())
    monkeypatch.setattr(fs.yf, "Ticker", _FakeTicker)
    monkeypatch.setattr(fs, "yf_retry", lambda fn: fn())
    monkeypatch.setattr(fs.sec_edgar, "get_company_snapshot", lambda t, d: SNAP)
    monkeypatch.setattr(fs, "_earnings_calendar_section", lambda o, d: "")


def test_core_figures(patched):
    out = fs.build_fact_sheet("ZS", "2026-10-23")
    assert "Decision price: **$255.15**" in out
    assert "net cash $1,618.3M" in out
    assert "Fiscal year ends **July 31**" in out
    assert "| 2026-07-31 | $898.2M | +24.9% | $1,149.1M | 118 |" in out
    assert "(+27.4% YoY)" in out  # RPO
    assert "Share buybacks: none reported since fiscal year ended 2021-07-31" in out
    assert "Revenue $3.9B" in out and "```text" in out
    assert out.count("```") == 2  # embedded fence neutralised


def test_live_run_includes_consensus_with_numpy_values(patched, monkeypatch):
    today = date.today().isoformat()
    monkeypatch.setattr(fs, "_verified_rows", lambda s, d: _rows(today))
    out = fs.build_fact_sheet("ZS", today)
    assert "mean $235.19" in out
    assert "strongBuy 7, buy 29, hold 11" in out
    assert "46 analysts" in out
    assert "Short interest: 5.4% of float" in out


def test_historical_run_omits_as_of_today_feeds(patched):
    out = fs.build_fact_sheet("ZS", "2026-10-23")
    if abs((date.today() - date(2026, 10, 23)).days) > 7:
        assert "price targets" not in out
        assert "as-of-today only" in out


def test_failures_become_gaps_not_exceptions(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(fs, "_verified_rows", boom)
    monkeypatch.setattr(fs.yf, "Ticker", _FakeTicker)
    monkeypatch.setattr(fs, "yf_retry", lambda fn: boom())
    monkeypatch.setattr(fs.sec_edgar, "get_company_snapshot",
                        lambda t, d: (_ for _ in ()).throw(fs.sec_edgar.EdgarNotConfiguredError("x")))
    out = fs.build_fact_sheet("ZS", "2026-10-23")
    assert "### Data gaps" in out
    assert "decision price unavailable" in out
    assert "SEC EDGAR not configured" in out


def test_balance_sheet_waits_for_filing(patched, monkeypatch):
    # Before the 10-K is public the 2026-07-31 balance sheet must not be used.
    snap = dict(SNAP, latest_filing={"form": "10-Q", "filed": date(2026, 6, 1),
                                     "period_end": date(2026, 4, 30)})
    monkeypatch.setattr(fs.sec_edgar, "get_company_snapshot", lambda t, d: snap)
    out = fs.build_fact_sheet("ZS", "2026-08-15")
    assert "balance sheet unavailable" in out
    assert "net cash $1,618.3M" not in out


def test_bad_date_returns_empty():
    assert fs.build_fact_sheet("ZS", "not-a-date") == ""


def test_fact_sheet_reaches_every_agent_context():
    ctx = get_instrument_context_from_state(
        {"company_of_interest": "ZS", "fact_sheet": "## Fact sheet X", "research_policies": "RULES"})
    assert "## Fact sheet X" in ctx and ctx.index("Fact sheet") < ctx.index("RULES")


def test_crypto_has_price_only(patched):
    out = fs.build_fact_sheet("BTC-USD", "2026-10-23", asset_type="crypto")
    assert "Decision price" in out and "Balance sheet" not in out
    assert isinstance(timedelta, type)
