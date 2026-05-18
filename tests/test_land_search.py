import unittest
import pytest
from land_tracker.search import (
    LandListing, _parse_price, _parse_acres, _acres_from_description,
    _normalize_serpapi, _make_listing_id, _extract_props,
)


def _make_prop(price=125000, lot_size="12.5 acres", address="123 Farm Rd, Conway, SC",
               property_id="prop1", description="Beautiful farmland", link="https://example.com"):
    return {
        "price": price,
        "lot_size": lot_size,
        "address": address,
        "property_id": property_id,
        "description": description,
        "link": link,
    }


@pytest.mark.unit
class TestParsePrice(unittest.TestCase):
    def test_int_passthrough(self):
        self.assertEqual(_parse_price(125000), 125000)

    def test_string_with_dollar_comma(self):
        self.assertEqual(_parse_price("$125,000"), 125000)

    def test_none_returns_none(self):
        self.assertIsNone(_parse_price(None))

    def test_non_numeric_returns_none(self):
        self.assertIsNone(_parse_price("contact agent"))


@pytest.mark.unit
class TestParseAcres(unittest.TestCase):
    def test_float_passthrough(self):
        self.assertEqual(_parse_acres(12.5), 12.5)

    def test_string_with_acres(self):
        self.assertEqual(_parse_acres("12.5 acres"), 12.5)

    def test_string_ac(self):
        self.assertEqual(_parse_acres("10 ac"), 10.0)

    def test_sqft_returns_none(self):
        self.assertIsNone(_parse_acres("54,000 sq ft"))

    def test_none_returns_none(self):
        self.assertIsNone(_parse_acres(None))


@pytest.mark.unit
class TestAcresFromDescription(unittest.TestCase):
    def test_extracts_from_description(self):
        self.assertEqual(_acres_from_description("Beautiful 15 acres of farmland"), 15.0)

    def test_extracts_decimal(self):
        self.assertEqual(_acres_from_description("12.5 acre parcel with road frontage"), 12.5)

    def test_no_acres_returns_none(self):
        self.assertIsNone(_acres_from_description("Great location near town"))

    def test_empty_returns_none(self):
        self.assertIsNone(_acres_from_description(""))


@pytest.mark.unit
class TestNormalizeSerpapi(unittest.TestCase):
    def test_extracts_listing(self):
        prop = _make_prop()
        listings = _normalize_serpapi({"properties": [prop]})
        self.assertEqual(len(listings), 1)
        l = listings[0]
        self.assertEqual(l.price, 125000)
        self.assertAlmostEqual(l.acres, 12.5)
        self.assertEqual(l.listing_id, "prop1")

    def test_skips_missing_price(self):
        prop = _make_prop(price=None)
        listings = _normalize_serpapi({"properties": [prop]})
        self.assertEqual(listings, [])

    def test_skips_missing_acreage(self):
        prop = _make_prop(lot_size=None)
        prop["description"] = "Nice lot near town"  # no acreage in description either
        listings = _normalize_serpapi({"properties": [prop]})
        self.assertEqual(listings, [])

    def test_falls_back_to_description_for_acreage(self):
        prop = _make_prop(lot_size=None)
        prop["description"] = "20 acres of prime farmland"
        listings = _normalize_serpapi({"properties": [prop]})
        self.assertEqual(len(listings), 1)
        self.assertEqual(listings[0].acres, 20.0)

    def test_dict_address_joined(self):
        prop = _make_prop(address={"street": "123 Farm Rd", "city": "Conway", "state": "SC", "zip": "29526"})
        listings = _normalize_serpapi({"properties": [prop]})
        self.assertIn("Conway", listings[0].address)

    def test_empty_properties_returns_empty(self):
        self.assertEqual(_normalize_serpapi({}), [])

    def test_malformed_item_skipped(self):
        good = _make_prop(price=100000)
        bad = {"price": "bad", "lot_size": "bad", "description": None}
        listings = _normalize_serpapi({"properties": [bad, good]})
        self.assertEqual(len(listings), 1)

    def test_id_falls_back_to_hash_when_no_property_id(self):
        prop = _make_prop()
        del prop["property_id"]
        listings = _normalize_serpapi({"properties": [prop]})
        self.assertEqual(len(listings), 1)
        self.assertTrue(len(listings[0].listing_id) > 0)

    def test_local_results_key_used_when_properties_absent(self):
        prop = _make_prop()
        listings = _normalize_serpapi({"local_results": [prop]})
        self.assertEqual(len(listings), 1)

    def test_results_key_used_as_fallback(self):
        prop = _make_prop()
        listings = _normalize_serpapi({"results": [prop]})
        self.assertEqual(len(listings), 1)

    def test_properties_key_takes_priority(self):
        prop1 = _make_prop(property_id="p1", price=100000)
        prop2 = _make_prop(property_id="p2", price=200000)
        listings = _normalize_serpapi({"properties": [prop1], "local_results": [prop2]})
        self.assertEqual(len(listings), 1)
        self.assertEqual(listings[0].listing_id, "p1")


if __name__ == "__main__":
    unittest.main()
