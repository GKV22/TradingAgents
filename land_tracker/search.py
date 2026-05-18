"""Land listing search — normalize raw API responses into LandListing dataclasses."""
import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional

from serpapi import GoogleSearch


@dataclass
class LandListing:
    listing_id: str
    address: str
    price: int
    acres: float
    description: str
    url: str
    source: str
    wetland_risk: str = "UNKNOWN"   # populated by select.py
    road_access: str = "UNKNOWN"    # populated by select.py


def _parse_price(raw) -> Optional[int]:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return int(raw)
    cleaned = re.sub(r"[^\d.]", "", str(raw))
    try:
        return int(float(cleaned))
    except ValueError:
        return None


def _parse_acres(raw) -> Optional[float]:
    """Extract numeric acreage from a value or string like '12.5 acres'."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).lower()
    # Ignore square-footage values (no "acre" mention)
    if "sq" in s and "acre" not in s:
        return None
    m = re.search(r"([\d,]+\.?\d*)", s)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def _acres_from_description(description: str) -> Optional[float]:
    """Last-resort: scan description for '12.5 acres' / '12.5 ac' patterns."""
    if not description:
        return None
    m = re.search(r"([\d,]+\.?\d*)\s*ac(?:res?)?", description.lower())
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def _make_listing_id(prop: dict, address: str) -> str:
    for key in ("property_id", "listing_id", "zpid"):
        if prop.get(key):
            return str(prop[key])
    raw = f"{address}|{prop.get('price', '')}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _extract_props(response: dict) -> list:
    """google_real_estate returns properties under different keys depending on query."""
    for key in ("properties", "local_results", "results"):
        items = response.get(key)
        if items:
            return items
    return []


def _normalize_serpapi(response: dict) -> list:
    listings = []
    for prop in _extract_props(response):
        try:
            price = _parse_price(prop.get("price"))
            if price is None:
                continue

            # Try dedicated acreage fields before falling back to description
            raw_acres = (
                prop.get("acres")
                or prop.get("lot_size")
                or prop.get("land_area")
            )
            acres = _parse_acres(raw_acres)
            if acres is None:
                acres = _acres_from_description(prop.get("description", ""))
            if acres is None:
                continue  # only show listings with stated acreage

            address_raw = prop.get("address", "")
            if isinstance(address_raw, dict):
                address = ", ".join(
                    filter(None, [
                        address_raw.get("street"),
                        address_raw.get("city"),
                        address_raw.get("state"),
                        address_raw.get("zip"),
                    ])
                )
            else:
                address = str(address_raw)

            listings.append(LandListing(
                listing_id=_make_listing_id(prop, address),
                address=address,
                price=price,
                acres=acres,
                description=prop.get("description", ""),
                url=prop.get("link", ""),
                source="serpapi/google_real_estate",
            ))
        except Exception:
            continue  # skip malformed items
    return listings


def _search_one_location(location: str, api_key: str) -> list:
    params = {
        "engine": "google_real_estate",
        "q": f"land farm acreage for sale {location} SC",
        "hl": "en",
        "gl": "us",
        "api_key": api_key,
    }
    search = GoogleSearch(params)
    return _normalize_serpapi(search.get_dict())


def search_land_serpapi(locations: list, api_key: str) -> list:
    """Search each location separately and deduplicate by listing_id."""
    seen_ids: set = set()
    results = []
    for loc in locations:
        try:
            for listing in _search_one_location(loc, api_key):
                if listing.listing_id not in seen_ids:
                    seen_ids.add(listing.listing_id)
                    results.append(listing)
        except Exception:
            continue  # one failed location doesn't kill the whole run
    return results


def search_land_zillow(locations: list, api_key: str) -> list:
    # TODO: implement via RapidAPI zillow-com1
    # endpoint: /propertyExtendedSearch
    # params: location=locations[0], status_type=ForSale, home_type=LotOrLand
    # header: X-RapidAPI-Key: api_key
    raise NotImplementedError("Zillow provider not yet implemented — add LAND_SEARCH_PROVIDER=zillow and a ZILLOW_API_KEY")


def search_land(locations: list, api_key: str, provider: str = "serpapi") -> list:
    if provider == "serpapi":
        return search_land_serpapi(locations, api_key)
    if provider == "zillow":
        return search_land_zillow(locations, api_key)
    raise ValueError(f"Unknown land search provider: {provider!r}")
