import pytest
from pydantic import ValidationError

from scripts.ibd_schema import BuyCandidate, DigestSchema


def test_buy_candidate_valid():
    c = BuyCandidate(
        ticker="NVDA",
        company="Nvidia",
        buy_point="153.20",
        rs_rating=97,
        composite_rating=98,
        rationale="Breaking out. Strong earnings.",
    )
    assert c.ticker == "NVDA"
    assert c.buy_point == "153.20"


def test_ticker_rejects_lowercase():
    with pytest.raises(ValidationError, match="Invalid ticker"):
        BuyCandidate(
            ticker="nvda",
            company="x",
            buy_point="100",
            rs_rating=90,
            composite_rating=90,
            rationale="x",
        )


def test_ticker_rejects_too_long():
    with pytest.raises(ValidationError, match="Invalid ticker"):
        BuyCandidate(
            ticker="TOOLONG",
            company="x",
            buy_point="100",
            rs_rating=90,
            composite_rating=90,
            rationale="x",
        )


def test_ticker_rejects_numbers():
    with pytest.raises(ValidationError, match="Invalid ticker"):
        BuyCandidate(
            ticker="NV1A",
            company="x",
            buy_point="100",
            rs_rating=90,
            composite_rating=90,
            rationale="x",
        )


def test_buy_point_rejects_dollar_sign():
    with pytest.raises(ValidationError, match="buy_point"):
        BuyCandidate(
            ticker="NVDA",
            company="x",
            buy_point="$153.20",
            rs_rating=90,
            composite_rating=90,
            rationale="x",
        )


def test_buy_point_rejects_range():
    with pytest.raises(ValidationError, match="buy_point"):
        BuyCandidate(
            ticker="NVDA",
            company="x",
            buy_point="153.20-155.00",
            rs_rating=90,
            composite_rating=90,
            rationale="x",
        )


def test_buy_point_rejects_text():
    with pytest.raises(ValidationError, match="buy_point"):
        BuyCandidate(
            ticker="NVDA",
            company="x",
            buy_point="near 153",
            rs_rating=90,
            composite_rating=90,
            rationale="x",
        )


def test_rs_rating_out_of_range():
    with pytest.raises(ValidationError):
        BuyCandidate(
            ticker="NVDA",
            company="x",
            buy_point="100",
            rs_rating=100,
            composite_rating=90,
            rationale="x",
        )


def test_rs_rating_zero():
    with pytest.raises(ValidationError):
        BuyCandidate(
            ticker="NVDA",
            company="x",
            buy_point="100",
            rs_rating=0,
            composite_rating=90,
            rationale="x",
        )


def make_valid_digest(**overrides):
    defaults = {
        "date": "2026-05-19",
        "market_pulse": "Confirmed Uptrend",
        "distribution_days": 2,
        "buy_candidates": [],
        "stocks_to_watch": [],
        "avoid_extended": [],
    }
    defaults.update(overrides)
    return DigestSchema(**defaults)


def test_digest_valid():
    d = make_valid_digest()
    assert d.market_pulse == "Confirmed Uptrend"
    assert d.distribution_days == 2


def test_digest_invalid_market_pulse():
    with pytest.raises(ValidationError, match="market_pulse"):
        make_valid_digest(market_pulse="Uptrend")


def test_digest_distribution_days_negative():
    with pytest.raises(ValidationError):
        make_valid_digest(distribution_days=-1)


def test_digest_buy_candidates_max_8():
    candidate = {
        "ticker": "NVDA",
        "company": "x",
        "buy_point": "100",
        "rs_rating": 90,
        "composite_rating": 90,
        "rationale": "x",
    }
    with pytest.raises(ValidationError):
        make_valid_digest(buy_candidates=[candidate] * 9)


def test_digest_empty_buy_candidates_is_valid():
    d = make_valid_digest(buy_candidates=[])
    assert d.buy_candidates == []


def test_all_three_market_pulse_values():
    for pulse in ["Confirmed Uptrend", "Uptrend Under Pressure", "Market in Correction"]:
        d = make_valid_digest(market_pulse=pulse)
        assert d.market_pulse == pulse


def test_ticker_boundary_one_char():
    c = BuyCandidate(
        ticker="A", company="x", buy_point="100", rs_rating=90, composite_rating=90, rationale="x"
    )
    assert c.ticker == "A"


def test_ticker_boundary_five_chars():
    c = BuyCandidate(
        ticker="BRKBX",
        company="x",
        buy_point="100",
        rs_rating=90,
        composite_rating=90,
        rationale="x",
    )
    assert c.ticker == "BRKBX"


def test_buy_candidates_exactly_eight_valid():
    candidate = {
        "ticker": "NVDA",
        "company": "x",
        "buy_point": "100",
        "rs_rating": 90,
        "composite_rating": 90,
        "rationale": "x",
    }
    d = make_valid_digest(buy_candidates=[candidate] * 8)
    assert len(d.buy_candidates) == 8
