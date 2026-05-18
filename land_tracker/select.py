"""Land listing scoring — wetland risk and road access flagging, price/acreage filtering."""
import dataclasses

_WETLAND_HIGH = frozenset({
    "wetland", "wetlands", "hydric", "marsh", "swamp", "floodway",
    "bottomland", "tidal",
})
_WETLAND_MEDIUM = frozenset({
    "flood zone", "floodplain", "flood plain", "100-year flood", "fema",
    "ae zone", "ve zone", "x zone", "seasonal flooding", "seasonal wet",
    "ponding", "standing water",
})
_ROAD_POSITIVE = frozenset({
    "road frontage", "road access", "paved road", "county road", "state road",
    "highway frontage", "deeded access", "easement access", "street frontage",
    "hwy frontage", "road front",
})
_ROAD_NEGATIVE = frozenset({
    "no road", "landlocked", "no access", "no frontage", "no road access",
    "no legal access",
})


def _wetland_risk(listing) -> str:
    text = (listing.description + " " + listing.address).lower()
    if any(w in text for w in _WETLAND_HIGH):
        return "HIGH"
    if any(w in text for w in _WETLAND_MEDIUM):
        return "MEDIUM"
    return "UNKNOWN"


def _road_access(listing) -> str:
    text = listing.description.lower()
    if any(w in text for w in _ROAD_NEGATIVE):
        return "NO"
    if any(w in text for w in _ROAD_POSITIVE):
        return "YES"
    return "UNKNOWN"


def score_listing(listing):
    """Return a new LandListing with wetland_risk and road_access populated."""
    return dataclasses.replace(
        listing,
        wetland_risk=_wetland_risk(listing),
        road_access=_road_access(listing),
    )


def filter_and_score(listings: list, max_price: int, min_acres: float) -> list:
    """Filter by price/acreage, then score each listing."""
    result = []
    for l in listings:
        if l.price > max_price:
            continue
        if l.acres < min_acres:
            continue
        result.append(score_listing(l))
    return result
