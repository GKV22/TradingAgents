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


def test_extract_outlook_skips_disclaimer_paragraph_under_heading():
    # Shopify style: the first paragraph cross-refers to "Forward-looking Statements".
    text = ("Results\n2026 Outlook\nThe outlook that follows is forward-looking information. "
            "See \"Forward-looking Statements\" at the end of this press release.\n"
            "For the third quarter of 2026, we expect:\n"
            "• Revenue to grow at a low-thirties percentage rate;\n"
            "Forward-looking Statements\nBoilerplate.")
    out = edgar.extract_outlook(text)
    assert "low-thirties" in out and "Boilerplate" not in out


def test_receivables_fall_back_to_other_tags(monkeypatch):
    facts = {"facts": {"us-gaap": {
        "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
            _fact("2026-04-01", "2026-06-30", 3_583.0, "2026-08-05")]}},
        "AccountsAndOtherReceivablesNetCurrent": {"units": {"USD": [
            _fact(None, "2026-06-30", 466.0, "2026-08-05")]}},
    }}}
    monkeypatch.setattr(edgar, "lookup_cik", lambda t: 1)
    monkeypatch.setattr(edgar, "_company_facts", lambda c: facts)
    monkeypatch.setattr(edgar, "_submissions", lambda c: {})
    monkeypatch.setattr(edgar, "latest_earnings_release", lambda c, d: None)
    snap = edgar.get_company_snapshot("SHOP", date(2026, 9, 1))
    assert snap["quarters"][-1]["receivables"] == 466.0


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


def test_latest_earnings_release_finds_spelled_out_exhibit_name(monkeypatch):
    subs = {"filings": {"recent": {"form": ["8-K"], "items": ["2.02"],
                                   "filingDate": ["2026-08-05"],
                                   "accessionNumber": ["0001-26-000046"]}}}
    monkeypatch.setattr(edgar, "_submissions", lambda cik: subs)
    names = ["shop-20260805.htm", "exhibit991pressreleaseq220.htm"]

    def fake_fetch(url):
        if url.endswith("index.json"):
            return ('{"directory": {"item": [%s]}}'
                    % ", ".join('{"name": "%s"}' % n for n in names)).encode()
        return b"<p>2026 Outlook</p><p>For Q3 we expect revenue growth in the low thirties.</p>"

    monkeypatch.setattr(edgar, "_fetch", fake_fetch)
    rel = edgar.latest_earnings_release(1594805, date(2026, 9, 1))
    assert rel["url"].endswith("exhibit991pressreleaseq220.htm")
    assert "low thirties" in rel["outlook"]


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


def test_ttm_gaap_eps_uses_annual_shares_for_fiscal_q4():
    facts = {"facts": {"us-gaap": {
        "NetIncomeLoss": {"units": {"USD": [
            _fact("2025-08-01", "2025-10-31", -11.6, "2025-12-03"),
            _fact("2025-11-01", "2026-01-31", -34.3, "2026-02-27"),
            _fact("2026-02-01", "2026-04-30", -13.9, "2026-05-28"),
            _fact("2025-08-01", "2026-07-31", -63.2, "2026-09-03", "10-K"),
        ]}},
        "WeightedAverageNumberOfDilutedSharesOutstanding": {"units": {"shares": [
            _fact("2025-08-01", "2026-07-31", 160.2, "2026-09-03", "10-K"),
        ]}},
    }}}
    eps = edgar.ttm_gaap_eps(facts, date(2026, 10, 30))
    assert eps["end"] == date(2026, 7, 31)
    assert eps["net_income"] == pytest.approx(-63.2)
    assert eps["eps"] == pytest.approx(-63.2 / 160.2)
    # Before the 10-K, Q4 net income is unknown: no TTM figure.
    assert edgar.ttm_gaap_eps(facts, date(2026, 8, 15)) is None


# Cash-flow items: only year-to-date totals in 10-Qs (calendar fiscal year).
CASH_FACTS = {"facts": {"us-gaap": {
    "PaymentsForRepurchaseOfCommonStock": {"units": {"USD": [
        _fact("2025-01-01", "2025-06-30", 0.0, "2025-08-06"),
        _fact("2025-01-01", "2025-09-30", 0.0, "2025-11-05"),
        _fact("2025-01-01", "2025-12-31", 100.0, "2026-02-15", "10-K"),
        _fact("2026-01-01", "2026-03-31", 491.0, "2026-05-07"),
        _fact("2026-01-01", "2026-06-30", 1_911.0, "2026-08-06"),
    ]}},
    "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [
        _fact("2025-01-01", "2025-09-30", 1_200.0, "2025-11-05"),
        _fact("2025-01-01", "2025-12-31", 2_000.0, "2026-02-15", "10-K"),
        _fact("2026-01-01", "2026-03-31", 481.0, "2026-05-07"),
        _fact("2026-01-01", "2026-06-30", 1_139.0, "2026-08-06"),
    ]}},
    "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": [
        _fact("2025-01-01", "2025-09-30", 30.0, "2025-11-05"),
        _fact("2025-01-01", "2025-12-31", 40.0, "2026-02-15", "10-K"),
        _fact("2026-01-01", "2026-03-31", 5.0, "2026-05-07"),
        _fact("2026-01-01", "2026-06-30", 9.0, "2026-08-06"),
    ]}},
}}}


def test_quarters_derived_from_year_to_date_totals():
    q = edgar.quarterly_flow(CASH_FACTS, ("PaymentsForRepurchaseOfCommonStock",), date(2026, 9, 1))
    assert q[(date(2026, 4, 1), date(2026, 6, 30))] == pytest.approx(1_420.0)
    assert q[(date(2025, 10, 1), date(2025, 12, 31))] == pytest.approx(100.0)


def test_buybacks_ttm_built_from_10q_year_to_date():
    # FY2025 10-K shows only $100 of buybacks; H1 2026 10-Qs show $1,911 more.
    ttm = edgar._ttm_or_annual(CASH_FACTS, edgar.BUYBACK_CONCEPTS, date(2026, 9, 1))
    assert ttm == {"end": date(2026, 6, 30), "value": pytest.approx(2_011.0), "period": "ttm"}
    # Before the H1 10-Q only three quarters are derivable: the Q1 year-to-date
    # total is fresher than the FY2025 10-K, so it is shown (never "none").
    ytd = edgar._ttm_or_annual(CASH_FACTS, edgar.BUYBACK_CONCEPTS, date(2026, 6, 1))
    assert ytd == {"end": date(2026, 3, 31), "value": pytest.approx(491.0),
                   "period": "ytd", "months": 3}
    fy = edgar._ttm_or_annual(CASH_FACTS, edgar.BUYBACK_CONCEPTS, date(2026, 3, 1))
    assert fy["period"] == "fy" and fy["value"] == pytest.approx(100.0)


def test_ttm_free_cash_flow():
    facts = {"facts": {"us-gaap": {
        k: {"units": {"USD": [
            _fact("2025-07-01", "2025-09-30", v[0], "2025-11-05"),
            _fact("2025-10-01", "2025-12-31", v[1], "2026-02-15", "10-K"),
            _fact("2026-01-01", "2026-03-31", v[2], "2026-05-07"),
            _fact("2026-01-01", "2026-06-30", v[2] + v[3], "2026-08-06"),
        ]}} for k, v in (("NetCashProvidedByUsedInOperatingActivities", (500.0, 738.0, 481.0, 658.0)),
                         ("PaymentsToAcquirePropertyPlantAndEquipment", (8.0, 8.0, 5.0, 4.0)))
    }}}
    fcf = edgar.ttm_free_cash_flow(facts, date(2026, 9, 1))
    assert fcf["end"] == date(2026, 6, 30)
    assert fcf["ocf"] == pytest.approx(2_377.0)
    assert fcf["fcf"] == pytest.approx(2_377.0 - 25.0)


def test_headline_shortened_at_sentence_boundary():
    text = "Shopify reports results. " + "AI representation grew strongly " * 20
    out = edgar._shorten(text, limit=100)
    assert out == "Shopify reports results. [shortened by TradingAgents]"
    assert edgar._shorten("Short headline") == "Short headline"


# ONTO-style: new convertible notes with a conversion price tagged at the same date.
CONVERT_FACTS = {"facts": {"us-gaap": {
    "ConvertibleLongTermNotesPayable": {"units": {"USD": [
        _fact(None, "2026-06-30", 1_471.7e6, "2026-08-06"),
    ]}},
    "ConvertibleNotesPayableCurrent": {"units": {"USD": [
        _fact(None, "2026-06-30", 10.0e6, "2026-08-06"),
    ]}},
    "DebtInstrumentConvertibleConversionPrice1": {"units": {"USD/shares": [
        _fact(None, "2024-07-31", 150.8, "2024-09-10", "10-K"),
        _fact(None, "2026-06-30", 254.53, "2026-08-06"),
    ]}},
    "PaymentsForProceedsFromHedgeFinancingActivities": {"units": {"USD": [
        _fact("2026-01-04", "2026-06-30", 88.9e6, "2026-08-06"),
    ]}},
}}}


def test_convertible_notes_sum_parts_and_take_same_date_conversion_price():
    notes = edgar.convertible_notes(CONVERT_FACTS, date(2026, 10, 30))
    assert notes["end"] == date(2026, 6, 30)
    assert notes["value"] == pytest.approx(1_481.7e6)
    assert notes["conversion_price"] == 254.53
    assert notes["hedge_payments"]["value"] == pytest.approx(88.9e6)


def test_convertible_conversion_price_from_older_notes_is_not_reused():
    facts = {"facts": {"us-gaap": {
        "ConvertibleLongTermNotesPayable": CONVERT_FACTS["facts"]["us-gaap"]["ConvertibleLongTermNotesPayable"],
        "DebtInstrumentConvertibleConversionPrice1": {"units": {"USD/shares": [
            _fact(None, "2024-07-31", 150.8, "2024-09-10", "10-K")]}},
    }}}
    notes = edgar.convertible_notes(facts, date(2026, 10, 30))
    assert notes["conversion_price"] is None


def test_convertible_notes_point_in_time_and_zero_balance():
    assert edgar.convertible_notes(CONVERT_FACTS, date(2026, 8, 1)) is None  # not yet filed
    zero = {"facts": {"us-gaap": {"ConvertibleDebtCurrent": {"units": {"USD": [
        _fact(None, "2025-12-31", 0.0, "2026-02-15", "10-K")]}}}}}
    assert edgar.convertible_notes(zero, date(2026, 10, 30)) is None


# MNTN-style: capex tagged only as capitalised software; cash newer than the vendor.
SOFTWARE_FACTS = {"facts": {"us-gaap": {
    "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [
        _fact("2025-07-01", "2025-09-30", 9.3, "2025-11-05"),
        _fact("2025-01-01", "2025-12-31", 60.0, "2026-02-20", "10-K"),
        _fact("2025-01-01", "2025-09-30", 30.4, "2025-11-05"),
        _fact("2026-01-01", "2026-03-31", 7.1, "2026-05-07"),
        _fact("2026-01-01", "2026-06-30", 34.0, "2026-08-06"),
        _fact("2026-01-01", "2026-09-30", 43.5, "2026-11-10"),
    ]}},
    "PaymentsToDevelopSoftware": {"units": {"USD": [
        _fact("2025-07-01", "2025-09-30", 3.0, "2025-11-05"),
        _fact("2025-01-01", "2025-12-31", 12.0, "2026-02-20", "10-K"),
        _fact("2025-01-01", "2025-09-30", 8.7, "2025-11-05"),
        _fact("2026-01-01", "2026-03-31", 3.4, "2026-05-07"),
        _fact("2026-01-01", "2026-06-30", 7.0, "2026-08-06"),
        _fact("2026-01-01", "2026-09-30", 9.4, "2026-11-10"),
    ]}},
    "CashAndCashEquivalentsAtCarryingValue": {"units": {"USD": [
        _fact(None, "2026-06-30", 237.3, "2026-08-06"),
        _fact(None, "2026-09-30", 252.3, "2026-11-10"),
    ]}},
    "MarketableSecuritiesCurrent": {"units": {"USD": [
        _fact(None, "2026-09-30", 10.0, "2026-11-10"),
    ]}},
}}}


def test_fcf_counts_capitalised_software_as_capex():
    fcf = edgar.ttm_free_cash_flow(SOFTWARE_FACTS, date(2026, 11, 11))
    # OCF TTM: Q4'25 (60.0-30.4) + 43.5 = 73.1; software: (12.0-8.7) + 9.4 = 12.7
    assert fcf["end"] == date(2026, 9, 30)
    assert fcf["ocf"] == pytest.approx(73.1)
    assert fcf["capex_parts"] == {"capitalised software": pytest.approx(12.7)}
    assert fcf["fcf"] == pytest.approx(60.4)


def test_latest_liquidity_is_point_in_time():
    assert edgar.latest_liquidity(SOFTWARE_FACTS, date(2026, 11, 11)) == {
        "end": date(2026, 9, 30), "cash": 252.3, "sti": 10.0}
    before = edgar.latest_liquidity(SOFTWARE_FACTS, date(2026, 11, 9))  # Q3 10-Q not yet filed
    assert before == {"end": date(2026, 6, 30), "cash": 237.3, "sti": None}
