import re

from pydantic import BaseModel, Field, field_validator

VALID_MARKET_PULSE = {
    "Confirmed Uptrend",
    "Uptrend Under Pressure",
    "Market in Correction",
}

class BuyCandidate(BaseModel):
    ticker: str
    company: str
    buy_point: str
    rs_rating: int = Field(ge=1, le=99)
    composite_rating: int = Field(ge=1, le=99)
    rationale: str

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        if not re.fullmatch(r"[A-Z]{1,5}", v):
            raise ValueError(f"Invalid ticker: {v!r} — must be 1–5 uppercase letters")
        return v

    @field_validator("buy_point")
    @classmethod
    def validate_buy_point(cls, v: str) -> str:
        if not re.fullmatch(r"[1-9]\d*(\.\d{1,2})?", v):
            raise ValueError(f"buy_point must be a single decimal number (e.g. '153.20'), got: {v!r}")
        return v

class DigestSchema(BaseModel):
    date: str
    market_pulse: str
    distribution_days: int = Field(ge=0)
    buy_candidates: list[BuyCandidate] = Field(max_length=8)
    stocks_to_watch: list[str]
    avoid_extended: list[str]

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            raise ValueError(f"date must be YYYY-MM-DD, got: {v!r}")
        return v

    @field_validator("market_pulse")
    @classmethod
    def validate_pulse(cls, v: str) -> str:
        if v not in VALID_MARKET_PULSE:
            raise ValueError(f"Unknown market_pulse: {v!r}. Must be one of: {sorted(VALID_MARKET_PULSE)}")
        return v
