"""SEC EDGAR vendor: point-in-time company facts and the latest earnings release.

Free official data from the SEC, no API key. The SEC requires every request to
carry a User-Agent identifying the caller with a contact address; it is read
from ``SEC_EDGAR_USER_AGENT`` (e.g. ``"TradingAgents you@example.com"``). If it
is unset the vendor raises ``EdgarNotConfiguredError`` and callers degrade to
"not available" instead of crashing.

Look-ahead safety: every XBRL fact and every filing is filtered by its SEC
*filed* date, so a historical run only sees what had been filed by then.

Only ``www.sec.gov`` and ``data.sec.gov`` are ever contacted, and URLs are built
from a numeric CIK resolved through the SEC's own ticker table (which doubles as
the ticker allowlist), never from free-form input.
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from .config import get_config
from .errors import VendorNotConfiguredError
from .utils import safe_ticker_component

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30
# Large-cap companyfacts JSON runs to ~20 MB; anything far beyond is abnormal.
MAX_RESPONSE_BYTES = 40 * 1024 * 1024
_ALLOWED_HOSTS = {"www.sec.gov", "data.sec.gov"}
_MIN_INTERVAL = 0.15  # SEC fair-access limit is 10 requests/second
_last_request = 0.0

_TICKERS_TTL = timedelta(days=7)
_FACTS_TTL = timedelta(hours=12)

REVENUE_CONCEPTS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "RevenuesNetOfInterestExpense",  # banks
)
DEFERRED_PAIRS = (
    ("ContractWithCustomerLiabilityCurrent", "ContractWithCustomerLiabilityNoncurrent"),
    ("DeferredRevenueCurrent", "DeferredRevenueNoncurrent"),
)
RECEIVABLE_CONCEPTS = (
    "AccountsReceivableNetCurrent",
    "AccountsAndOtherReceivablesNetCurrent",
    "ReceivablesNetCurrent",
)
SBC_CONCEPTS = ("ShareBasedCompensation", "AllocatedShareBasedCompensationExpense")
BUYBACK_CONCEPTS = ("PaymentsForRepurchaseOfCommonStock", "PaymentsForRepurchaseOfEquity")
ACQUISITION_CONCEPTS = ("PaymentsToAcquireBusinessesNetOfCashAcquired",)
OCF_CONCEPTS = ("NetCashProvidedByUsedInOperatingActivities",)
CAPEX_CONCEPTS = ("PaymentsToAcquirePropertyPlantAndEquipment",)
# Software companies often tag their main investment spend as capitalised software.
SOFTWARE_CAPEX_CONCEPTS = ("PaymentsToDevelopSoftware",)
CASH_CONCEPTS = ("CashAndCashEquivalentsAtCarryingValue",)
SHORT_TERM_INVESTMENT_CONCEPTS = (
    "ShortTermInvestments",
    "MarketableSecuritiesCurrent",
    "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
    "OtherShortTermInvestments",
)
CONVERTIBLE_TOTAL_CONCEPTS = ("ConvertibleNotesPayable", "ConvertibleDebt")
CONVERTIBLE_NONCURRENT_CONCEPTS = ("ConvertibleLongTermNotesPayable", "ConvertibleDebtNoncurrent")
CONVERTIBLE_CURRENT_CONCEPTS = ("ConvertibleNotesPayableCurrent", "ConvertibleDebtCurrent")
CONVERSION_PRICE_CONCEPT = "DebtInstrumentConvertibleConversionPrice1"
HEDGE_PAYMENT_CONCEPTS = ("PaymentsForProceedsFromHedgeFinancingActivities",)

_OUTLOOK_HEADINGS = ("outlook", "guidance")
_OUTLOOK_END_MARKERS = (
    "these statements are forward-looking",
    "forward-looking statements",
    "conference call",
    "use of non-gaap",
    "non-gaap financial measures",
)
OUTLOOK_MAX_CHARS = 3000


class EdgarNotConfiguredError(VendorNotConfiguredError):
    """Raised when SEC_EDGAR_USER_AGENT is not set."""


def _user_agent() -> str:
    ua = (os.getenv("SEC_EDGAR_USER_AGENT") or "").strip()
    if "@" not in ua:
        raise EdgarNotConfiguredError(
            "SEC_EDGAR_USER_AGENT is not set (the SEC requires a contact, e.g. "
            "'TradingAgents you@example.com')."
        )
    return ua


def _cache_dir() -> Path:
    d = Path(get_config()["data_cache_dir"]) / "sec_edgar"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _fetch(url: str) -> bytes:
    host = urlparse(url).hostname
    if urlparse(url).scheme != "https" or host not in _ALLOWED_HOSTS:
        raise ValueError(f"Refusing non-SEC URL: {url!r}")
    global _last_request
    wait = _MIN_INTERVAL - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()
    # No redirects: the host allowlist above must hold for the URL actually read.
    resp = requests.get(url, headers={"User-Agent": _user_agent()}, timeout=REQUEST_TIMEOUT,
                        allow_redirects=False, stream=True)
    try:
        resp.raise_for_status()
        if resp.is_redirect:
            raise ValueError(f"SEC endpoint redirected; refusing to follow: {url!r}")
        body = bytearray()
        for chunk in resp.iter_content(chunk_size=65536):
            body += chunk
            if len(body) > MAX_RESPONSE_BYTES:
                raise ValueError(f"SEC response exceeds {MAX_RESPONSE_BYTES} bytes: {url!r}")
        return bytes(body)
    finally:
        resp.close()


def _cached_json(url: str, name: str, ttl: timedelta) -> Any:
    path = _cache_dir() / name
    if path.exists():
        age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
        if age < ttl:
            with path.open(encoding="utf-8") as f:
                return json.load(f)
    data = json.loads(_fetch(url))
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def lookup_cik(ticker: str) -> int | None:
    """Map a ticker to its SEC CIK via the SEC's own ticker table, or None."""
    safe_ticker_component(ticker)
    table = _cached_json(
        "https://www.sec.gov/files/company_tickers.json", "company_tickers.json", _TICKERS_TTL
    )
    wanted = {ticker.upper(), ticker.upper().replace(".", "-")}
    for row in table.values():
        if str(row.get("ticker", "")).upper() in wanted:
            return int(row["cik_str"])
    return None


def _company_facts(cik: int) -> dict:
    return _cached_json(
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json",
        f"facts_{cik}.json", _FACTS_TTL,
    )


def _submissions(cik: int) -> dict:
    return _cached_json(
        f"https://data.sec.gov/submissions/CIK{cik:010d}.json",
        f"submissions_{cik}.json", _FACTS_TTL,
    )


# ── XBRL helpers ────────────────────────────────────────────────────────────


def _d(s: str | None) -> date | None:
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def _entries(facts: dict, concept: str, as_of: date, unit: str = "USD") -> list[dict]:
    """Fact entries filed on or before ``as_of``; latest filing wins per period."""
    try:
        raw = facts["facts"]["us-gaap"][concept]["units"][unit]
    except (KeyError, TypeError):
        return []
    best: dict[tuple, dict] = {}
    for e in raw:
        filed, end = _d(e.get("filed")), _d(e.get("end"))
        if not filed or not end or filed > as_of or not isinstance(e.get("val"), (int, float)):
            continue
        key = (e.get("start"), e.get("end"))
        if key not in best or _d(best[key]["filed"]) < filed:
            best[key] = e
    return sorted(best.values(), key=lambda e: e["end"])


def _duration_days(e: dict) -> int | None:
    start, end = _d(e.get("start")), _d(e.get("end"))
    return (end - start).days + 1 if start and end else None


def _instants(facts: dict, concept: str, as_of: date) -> dict[date, float]:
    return {
        _d(e["end"]): float(e["val"])
        for e in _entries(facts, concept, as_of)
        if not e.get("start")
    }


def quarterly_flow(facts: dict, concepts: tuple[str, ...], as_of: date,
                   unit: str = "USD") -> dict[tuple[date, date], float]:
    """Quarterly values of an additive flow (revenue, net income), keyed (start, end).

    Fiscal Q4 is rarely tagged as a quarter (only the 10-K annual is), so it is
    derived as FY minus Q1-Q3. Cash-flow items are often tagged only
    year-to-date (6 and 9 months), so a quarter is also derived as the
    difference between consecutive year-to-date totals. When several concepts
    exist, the one with the freshest data is used (companies switch tags over time).
    """
    candidates = [_entries(facts, c, as_of, unit) for c in concepts]
    entries = max(candidates, key=lambda es: es[-1]["end"] if es else "", default=[])
    quarters = {
        (_d(e["start"]), _d(e["end"])): float(e["val"])
        for e in entries if 80 <= (_duration_days(e) or 0) <= 100
    }
    ytd: dict[date, list[dict]] = {}
    for e in entries:
        if 80 <= (_duration_days(e) or 0) <= 380:
            ytd.setdefault(_d(e["start"]), []).append(e)
    for group in ytd.values():
        group.sort(key=lambda e: e["end"])
        for prev, cur in zip(group, group[1:]):
            key = (_d(prev["end"]) + timedelta(days=1), _d(cur["end"]))
            if 80 <= (key[1] - key[0]).days + 1 <= 100 and key not in quarters:
                quarters[key] = float(cur["val"]) - float(prev["val"])
    for e in entries:
        if 350 <= (_duration_days(e) or 0) <= 380:
            fy_start, fy_end = _d(e["start"]), _d(e["end"])
            inside = sorted(
                (k for k in quarters if k[0] >= fy_start and k[1] < fy_end), key=lambda k: k[1]
            )
            if len(inside) == 3 and not any(k[1] == fy_end for k in quarters):
                q4_start = inside[-1][1] + timedelta(days=1)
                quarters[(q4_start, fy_end)] = float(e["val"]) - sum(quarters[k] for k in inside)
    return quarters


def quarterly_revenue(facts: dict, as_of: date) -> list[dict]:
    """Quarterly revenue (oldest first), deriving fiscal Q4 as FY minus Q1-Q3."""
    quarters = quarterly_flow(facts, REVENUE_CONCEPTS, as_of)
    return [
        {"start": s, "end": t, "revenue": v}
        for (s, t), v in sorted(quarters.items(), key=lambda kv: kv[0][1])
    ]


def ttm_gaap_eps(facts: dict, as_of: date) -> dict | None:
    """Trailing-twelve-month GAAP diluted EPS, approximated as TTM net income ÷
    the latest quarter's diluted weighted-average shares."""
    income = quarterly_flow(facts, ("NetIncomeLoss",), as_of)
    last4 = sorted(income.items(), key=lambda kv: kv[0][1])[-4:]
    if len(last4) < 4 or (last4[-1][0][1] - last4[0][0][0]).days > 380:
        return None
    end = last4[-1][0][1]
    ending = [e for e in _entries(facts, "WeightedAverageNumberOfDilutedSharesOutstanding",
                                  as_of, unit="shares") if _d(e["end"]) == end and e.get("start")]
    # Prefer the quarter's count; a fiscal Q4 usually only has the 10-K annual one.
    shares = sorted(ending, key=lambda e: _duration_days(e) or 0)
    if not shares or not shares[0]["val"]:
        return None
    shares = shares[:1]
    net = sum(v for _, v in last4)
    return {"end": end, "net_income": net, "diluted_shares": float(shares[-1]["val"]),
            "eps": net / float(shares[-1]["val"])}


def ttm_flow(facts: dict, concepts: tuple[str, ...], as_of: date) -> dict | None:
    """Sum of the latest four contiguous quarters of a flow, or None."""
    last4 = sorted(quarterly_flow(facts, concepts, as_of).items(), key=lambda kv: kv[0][1])[-4:]
    if len(last4) < 4 or (last4[-1][0][1] - last4[0][0][0]).days > 380:
        return None
    return {"end": last4[-1][0][1], "value": sum(v for _, v in last4), "period": "ttm"}


def _ttm_or_annual(facts: dict, concepts: tuple[str, ...], as_of: date) -> dict | None:
    """TTM value when four quarters are derivable, else the latest reported
    fiscal year or year-to-date total, whichever ends later."""
    ttm = ttm_flow(facts, concepts, as_of)
    cumulative = []
    for concept in concepts:
        cumulative += [e for e in _entries(facts, concept, as_of)
                       if 80 <= (_duration_days(e) or 0) <= 380]
    latest = max(cumulative, key=lambda e: (e["end"], _duration_days(e)), default=None)
    if ttm and (not latest or ttm["end"] >= _d(latest["end"])):
        return ttm
    if not latest:
        return None
    days = _duration_days(latest)
    return {"end": _d(latest["end"]), "value": float(latest["val"]),
            "period": "fy" if days >= 350 else "ytd", "months": round(days / 30.4)}


def ttm_free_cash_flow(facts: dict, as_of: date) -> dict | None:
    """TTM operating cash flow minus capital expenditure, same quarters.

    Capex is PP&E purchases plus capitalised software, counting each only when
    its TTM ends on the same quarter as operating cash flow.
    """
    ocf = ttm_flow(facts, OCF_CONCEPTS, as_of)
    if not ocf:
        return None
    parts = {}
    for label, concepts in (("PP&E", CAPEX_CONCEPTS), ("capitalised software", SOFTWARE_CAPEX_CONCEPTS)):
        item = ttm_flow(facts, concepts, as_of)
        if item and item["end"] == ocf["end"]:
            parts[label] = item["value"]
    if not parts:
        return None
    capex = sum(parts.values())
    return {"end": ocf["end"], "ocf": ocf["value"], "capex": capex,
            "capex_parts": parts, "fcf": ocf["value"] - capex}


def latest_liquidity(facts: dict, as_of: date) -> dict | None:
    """Cash and short-term investments at the latest filed balance-sheet date."""
    cash = max((_instants(facts, c, as_of) for c in CASH_CONCEPTS),
               key=lambda r: max(r, default=date.min))
    if not cash:
        return None
    end = max(cash)
    sti = next((v for c in SHORT_TERM_INVESTMENT_CONCEPTS
                if (v := _instants(facts, c, as_of).get(end)) is not None), None)
    return {"end": end, "cash": cash[end], "sti": sti}


def convertible_notes(facts: dict, as_of: date) -> dict | None:
    """Latest convertible-notes balance, with the conversion price only when it
    is tagged for the same balance-sheet date (an older price may belong to
    notes since repaid). None when the company has no non-zero balance."""
    def at(concepts: tuple[str, ...], when: date) -> float | None:
        return next((v for c in concepts
                     if (v := _instants(facts, c, as_of).get(when)) is not None), None)

    all_concepts = (CONVERTIBLE_TOTAL_CONCEPTS + CONVERTIBLE_NONCURRENT_CONCEPTS
                    + CONVERTIBLE_CURRENT_CONCEPTS)
    end = max((d for c in all_concepts for d in _instants(facts, c, as_of)), default=None)
    if end is None:
        return None
    total = at(CONVERTIBLE_TOTAL_CONCEPTS, end)
    if total is None:
        total = (at(CONVERTIBLE_NONCURRENT_CONCEPTS, end) or 0) + (at(CONVERTIBLE_CURRENT_CONCEPTS, end) or 0)
    if total <= 0:
        return None
    prices = {_d(e["end"]): float(e["val"])
              for e in _entries(facts, CONVERSION_PRICE_CONCEPT, as_of, unit="USD/shares")}
    price = prices.get(end)
    return {"end": end, "value": total, "conversion_price": price if price and price > 0 else None,
            "hedge_payments": _ttm_or_annual(facts, HEDGE_PAYMENT_CONCEPTS, as_of)}


def _latest_annual(facts: dict, concepts: tuple[str, ...], as_of: date) -> dict | None:
    for concept in concepts:
        annual = [e for e in _entries(facts, concept, as_of)
                  if 350 <= (_duration_days(e) or 0) <= 380]
        if annual:
            e = annual[-1]
            return {"end": _d(e["end"]), "value": float(e["val"]), "concept": concept}
    return None


def deferred_revenue(facts: dict, as_of: date) -> dict[date, float]:
    for current, noncurrent in DEFERRED_PAIRS:
        cur = _instants(facts, current, as_of)
        if cur:
            non = _instants(facts, noncurrent, as_of)
            return {d: v + non.get(d, 0.0) for d, v in cur.items()}
    return _instants(facts, "ContractWithCustomerLiability", as_of)


# ── Earnings release (8-K Item 2.02, Exhibit 99.1) ──────────────────────────


def _html_to_text(raw: str) -> str:
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    t = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|li|h\d)>", "\n", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = html.unescape(t)
    # Drop control characters (keep newlines); collapse whitespace.
    t = re.sub(r"[\x00-\x09\x0b-\x1f\x7f]", " ", t)
    t = re.sub(r"[ \xa0]+", " ", t)
    t = "\n".join(line.strip() for line in t.splitlines())
    return re.sub(r"\n\s*\n+", "\n", t).strip()


def extract_outlook(text: str) -> str | None:
    """Return the guidance/outlook section of an earnings release, or None."""
    lowered = text.lower()
    start = None
    offset = 0
    for line in lowered.splitlines(keepends=True):
        # A short heading line such as "Financial Outlook" or "Fiscal 2027 Guidance:".
        heading = line.strip().rstrip(":").strip()
        if len(heading) <= 60 and heading.endswith(_OUTLOOK_HEADINGS):
            start = offset
            break
        offset += len(line)
    if start is None:
        return None
    # The first paragraph under the heading is often a disclaimer that itself
    # mentions "forward-looking statements"; only end markers after it count.
    body = lowered.find("\n", start) + 1 or len(lowered)
    floor = lowered.find("\n", body)
    floor = floor if floor > 0 else body
    hits = [i for i in (lowered.find(m, floor) for m in _OUTLOOK_END_MARKERS) if i > 0]
    end = min(hits + [start + OUTLOOK_MAX_CHARS])
    return text[start:end].strip()


HEADLINE_MAX_CHARS = 400


def _shorten(text: str, limit: int = HEADLINE_MAX_CHARS) -> str:
    """Collapse whitespace; if too long, cut at the last sentence end and say so,
    so a mid-word cut is not mistaken for a broken data feed."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    cut = cut[:end + 1] if end > 0 else cut[:cut.rfind(" ")] if " " in cut else cut
    return cut + " [shortened by TradingAgents]"


def latest_earnings_release(cik: int, as_of: date) -> dict | None:
    """Latest 8-K with Item 2.02 filed on or before ``as_of``, with its outlook."""
    recent = _submissions(cik).get("filings", {}).get("recent", {})
    forms, items = recent.get("form", []), recent.get("items", [])
    dates, accs = recent.get("filingDate", []), recent.get("accessionNumber", [])
    best = None
    for i, form in enumerate(forms):
        filed = _d(dates[i]) if i < len(dates) else None
        if form == "8-K" and "2.02" in (items[i] if i < len(items) else "") \
                and filed and filed <= as_of and (best is None or filed > best[0]):
            best = (filed, accs[i])
    if not best:
        return None
    filed, acc = best
    acc_path = acc.replace("-", "")
    if not acc_path.isdigit():
        return None
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_path}/"
    index = json.loads(_fetch(base + "index.json"))
    docs = [it.get("name", "") for it in index.get("directory", {}).get("item", [])]
    htm = [n for n in docs if n.lower().endswith((".htm", ".html"))]
    # Prefer Exhibit 99.1 (the press release) over 99.2+ (supplements, slides).
    exhibit = (
        next((n for n in htm if re.search(r"(?i)(ex(hibit)?-?99[-_.]?0?1|_991|991\.)", n)), None)
        or next((n for n in htm if re.search(r"(?i)ex(hibit)?-?99", n)), None)
    )
    if not exhibit or "/" in exhibit or ".." in exhibit:
        return {"filed": filed, "url": base, "outlook": None, "headline": None}
    text = _html_to_text(_fetch(base + exhibit).decode("utf-8", "replace"))
    headline_match = re.search(r"(?i)exhibit 99\.1\s*(.{0,600})", text, re.S)
    return {
        "filed": filed,
        "url": base + exhibit,
        "headline": _shorten(headline_match.group(1)) if headline_match else None,
        "outlook": extract_outlook(text),
    }


# ── Public snapshot ─────────────────────────────────────────────────────────


def _latest_periodic_filing(subs: dict, as_of: date) -> dict | None:
    """Latest 10-Q/10-K filed on or before ``as_of``: which period is public."""
    recent = subs.get("filings", {}).get("recent", {})
    best = None
    for form, filed_s, period_s in zip(
        recent.get("form", []), recent.get("filingDate", []), recent.get("reportDate", [])
    ):
        filed, period = _d(filed_s), _d(period_s)
        if form in ("10-Q", "10-K") and filed and period and filed <= as_of \
                and (best is None or filed > best["filed"]):
            best = {"form": form, "filed": filed, "period_end": period}
    return best



def get_company_snapshot(ticker: str, as_of: date) -> dict | None:
    """Point-in-time SEC data for ``ticker`` as of ``as_of``; None if not an SEC filer."""
    cik = lookup_cik(ticker)
    if cik is None:
        return None
    facts = _company_facts(cik)
    subs = _submissions(cik)

    revenue = quarterly_revenue(facts, as_of)
    # Freshest receivables tag wins (companies switch tags over time).
    receivables = max((_instants(facts, c, as_of) for c in RECEIVABLE_CONCEPTS),
                      key=lambda r: max(r, default=date.min))
    for q in revenue:
        ar = receivables.get(q["end"])
        days = (q["end"] - q["start"]).days + 1
        q["receivables"] = ar
        q["dso"] = ar / (q["revenue"] / days) if ar and q["revenue"] > 0 else None

    latest_filing = _latest_periodic_filing(subs, as_of)
    fye = str(subs.get("fiscalYearEnd") or "")
    return {
        "cik": cik,
        "name": subs.get("name"),
        "fiscal_year_end": fye if re.fullmatch(r"\d{4}", fye) else None,
        "latest_filing": latest_filing,
        "quarters": revenue,
        "receivables_by_quarter": receivables,
        "rpo": _instants(facts, "RevenueRemainingPerformanceObligation", as_of),
        "deferred_revenue": deferred_revenue(facts, as_of),
        "sbc": _ttm_or_annual(facts, SBC_CONCEPTS, as_of),
        "acquisitions": _ttm_or_annual(facts, ACQUISITION_CONCEPTS, as_of),
        "buybacks": _ttm_or_annual(facts, BUYBACK_CONCEPTS, as_of),
        "fcf": ttm_free_cash_flow(facts, as_of),
        "liquidity": latest_liquidity(facts, as_of),
        # Banks, REITs and foreign filers tag no capex: no FCF gap to report for them.
        "capex_tagged": any(_entries(facts, c, as_of)
                            for c in CAPEX_CONCEPTS + SOFTWARE_CAPEX_CONCEPTS),
        "convertible_notes": convertible_notes(facts, as_of),
        "ttm_eps": ttm_gaap_eps(facts, as_of),
        "earnings_release": latest_earnings_release(cik, as_of),
    }
