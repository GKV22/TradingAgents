"""Earnings calendar section in yfinance fundamentals (live runs only)."""

from datetime import date, datetime, timedelta
from types import SimpleNamespace

import tradingagents.dataflows.y_finance as yfin


def _obj(cal):
    return SimpleNamespace(calendar=cal)


def _today():
    return datetime.now().date()


def _cal(days_ahead=30, **extra):
    return {"Earnings Date": [_today() + timedelta(days=days_ahead)],
            "Earnings Average": 1.16, "Revenue Average": 938_160_410, **extra}


def _run(cal, curr_date, monkeypatch):
    monkeypatch.setattr(yfin, "yf_retry", lambda fn: fn())
    return yfin._earnings_calendar_section(_obj(cal), curr_date)


def test_live_run_includes_next_date_and_consensus(monkeypatch):
    out = _run(_cal(), _today().isoformat(), monkeypatch)
    assert "Next Earnings Date" in out
    assert "(30 days after" in out
    assert "Consensus EPS (avg): 1.16" in out
    assert "Consensus Revenue (avg): 938160410" in out


def test_historical_run_omits_section_to_avoid_lookahead(monkeypatch):
    assert _run(_cal(), "2025-06-01", monkeypatch) == ""


def test_past_earnings_dates_ignored(monkeypatch):
    assert _run(_cal(days_ahead=-3), _today().isoformat(), monkeypatch) == ""


def test_date_passed_since_as_of_is_not_reported_as_next(monkeypatch):
    as_of = (_today() - timedelta(days=5)).isoformat()
    cal = {"Earnings Date": [_today() - timedelta(days=2)]}
    assert _run(cal, as_of, monkeypatch) == ""


def test_datetime_values_and_bad_numbers_handled(monkeypatch):
    cal = {"Earnings Date": [datetime.combine(_today() + timedelta(days=5), datetime.min.time())],
           "Earnings Average": "n/a", "Earnings Low": True}
    out = _run(cal, _today().isoformat(), monkeypatch)
    assert "Next Earnings Date" in out
    assert "Consensus EPS" not in out


def test_calendar_failure_is_silent(monkeypatch):
    class Boom:
        @property
        def calendar(self):
            raise RuntimeError("rate limited")

    monkeypatch.setattr(yfin, "yf_retry", lambda fn: fn())
    assert yfin._earnings_calendar_section(Boom(), _today().isoformat()) == ""


def test_missing_or_bad_curr_date(monkeypatch):
    assert _run(_cal(), None, monkeypatch) == ""
    assert _run(_cal(), "not-a-date", monkeypatch) == ""
    assert isinstance(date.today(), date)
