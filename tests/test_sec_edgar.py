"""SEC EDGAR vendor: configuration, host allowlist, point-in-time filtering."""

from datetime import date

import pytest

import tradingagents.dataflows.sec_edgar as edgar


def _fact(start, end, val, filed, form="10-Q"):
    e = {"end": end, "val": val, "filed": filed, "form": form}
    if start:
        e["start"] = start
    return e


FACTS = {"facts": {"us-gaap": {
    "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
        _fact("2024-08-01", "2025-07-31", 2_673.0, "2025-09-05", "10-K"),
        _fact("2025-08-01", "2025-10-31", 788.0, "2025-12-03"),
        _fact("2025-11-01", "2026-01-31", 816.0, "2026-02-27"),
        _fact("2026-02-01", "2026-04-30", 850.0, "2026-05-28"),
        _fact("2025-08-01", "2026-07-31", 3_352.0, "2026-09-03", "10-K"),
    ]}},
    "AccountsReceivableNetCurrent": {"units": {"USD": [
        _fact(None, "2026-04-30", 730.0, "2026-05-28"),
        _fact(None, "2026-07-31", 1_149.0, "2026-09-03", "10-K"),
    ]}},
}}}


def test_requires_user_agent(monkeypatch):
    monkeypatch.delenv("SEC_EDGAR_USER_AGENT", raising=False)
    with pytest.raises(edgar.EdgarNotConfiguredError):
        edgar._user_agent()
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "no contact here")
    with pytest.raises(edgar.EdgarNotConfiguredError):
        edgar._user_agent()


@pytest.mark.parametrize("url", [
    "https://evil.example.com/x.json",
    "http://www.sec.gov/files/company_tickers.json",
    "https://www.sec.gov.evil.com/x",
])
def test_fetch_refuses_non_sec_urls(url, monkeypatch):
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "TA test@example.com")
    with pytest.raises(ValueError):
        edgar._fetch(url)


def test_lookup_validates_ticker():
    with pytest.raises(ValueError):
        edgar.lookup_cik("../../etc")


def test_lookup_uses_sec_table(monkeypatch):
    table = {"0": {"cik_str": 1713683, "ticker": "ZS"}, "1": {"cik_str": 1067983, "ticker": "BRK-B"}}
    monkeypatch.setattr(edgar, "_cached_json", lambda *a, **k: table)
    assert edgar.lookup_cik("ZS") == 1713683
    assert edgar.lookup_cik("BRK.B") == 1067983
    assert edgar.lookup_cik("NOPE") is None


def test_q4_derived_from_annual_minus_three_quarters():
    qs = edgar.quarterly_revenue(FACTS, date(2026, 10, 1))
    q4 = qs[-1]
    assert (q4["start"], q4["end"]) == (date(2026, 5, 1), date(2026, 7, 31))
    assert q4["revenue"] == pytest.approx(3_352.0 - 788.0 - 816.0 - 850.0)


def test_point_in_time_excludes_later_filings():
    # Before the 10-K was filed (2026-09-03) the Q4 figure did not exist yet.
    qs = edgar.quarterly_revenue(FACTS, date(2026, 8, 15))
    assert qs[-1]["end"] == date(2026, 4, 30)
    ar = edgar._instants(FACTS, "AccountsReceivableNetCurrent", date(2026, 8, 15))
    assert date(2026, 7, 31) not in ar


def test_freshest_revenue_concept_wins():
    facts = {"facts": {"us-gaap": {
        "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
            _fact("2014-10-01", "2014-12-31", 1.0, "2015-02-01")]}},
        "RevenuesNetOfInterestExpense": {"units": {"USD": [
            _fact("2026-04-01", "2026-06-30", 2.0, "2026-08-01")]}},
    }}}
    assert edgar.quarterly_revenue(facts, date(2026, 10, 1))[-1]["revenue"] == 2.0


def test_extract_outlook_handles_heading_variants():
    text = "Results\nRevenue grew.\nFinancial Outlook:\nRevenue of $935M.\n" \
           "These statements are forward-looking and may differ.\nMore."
    out = edgar.extract_outlook(text)
    assert out.startswith("Financial Outlook")
    assert "$935M" in out and "may differ" not in out
    assert edgar.extract_outlook("No guidance section here at all, sorry.") is None


def test_html_to_text_strips_scripts_and_controls():
    raw = "<p>Hello</p><script>ignore()</script><div>W\x07orld&amp;</div>"
    assert edgar._html_to_text(raw) == "Hello\nW orld&"


def test_latest_earnings_release_respects_filed_date(monkeypatch):
    subs = {"filings": {"recent": {
        "form": ["8-K", "8-K", "10-Q"],
        "items": ["2.02,9.01", "2.02,9.01", ""],
        "filingDate": ["2026-09-03", "2026-05-26", "2026-06-01"],
        "accessionNumber": ["0001-26-000156", "0001-26-000095", "0001-26-000100"],
    }}}
    fetched = []
    monkeypatch.setattr(edgar, "_submissions", lambda cik: subs)

    def fake_fetch(url):
        fetched.append(url)
        if url.endswith("index.json"):
            return b'{"directory": {"item": [{"name": "zs-04302026_991.htm"}]}}'
        return b"<p>Exhibit 99.1 Q3 results</p><p>Outlook</p><p>Q4 revenue $875M.</p>"

    monkeypatch.setattr(edgar, "_fetch", fake_fetch)
    rel = edgar.latest_earnings_release(1713683, date(2026, 8, 1))
    assert rel["filed"] == date(2026, 5, 26)
    assert "000126000095" in fetched[0]
    assert "$875M" in rel["outlook"]


class _Resp:
    def __init__(self, chunks, redirect=False):
        self._chunks, self.is_redirect, self.closed = chunks, redirect, False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield from self._chunks

    def close(self):
        self.closed = True


def test_fetch_does_not_follow_redirects(monkeypatch):
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "TA test@example.com")
    seen = {}

    def fake_get(url, **kw):
        seen.update(kw)
        return _Resp([], redirect=True)

    monkeypatch.setattr(edgar.requests, "get", fake_get)
    with pytest.raises(ValueError, match="redirected"):
        edgar._fetch("https://data.sec.gov/x.json")
    assert seen["allow_redirects"] is False


def test_fetch_caps_response_size(monkeypatch):
    monkeypatch.setenv("SEC_EDGAR_USER_AGENT", "TA test@example.com")
    monkeypatch.setattr(edgar, "MAX_RESPONSE_BYTES", 10)
    monkeypatch.setattr(edgar.requests, "get", lambda url, **kw: _Resp([b"123456", b"789012"]))
    with pytest.raises(ValueError, match="exceeds"):
        edgar._fetch("https://data.sec.gov/x.json")
    monkeypatch.setattr(edgar.requests, "get", lambda url, **kw: _Resp([b"12345"]))
    assert edgar._fetch("https://data.sec.gov/x.json") == b"12345"
