import unittest
import pytest
from land_tracker.search import LandListing
from land_tracker.select import filter_and_score, score_listing, _wetland_risk, _road_access


def make_listing(price=100000, acres=15.0, description="", address="123 Farm Rd",
                 listing_id="l1"):
    return LandListing(
        listing_id=listing_id,
        address=address,
        price=price,
        acres=acres,
        description=description,
        url="https://example.com",
        source="test",
    )


@pytest.mark.unit
class TestWetlandRisk(unittest.TestCase):
    def test_high_on_wetland_keyword(self):
        l = make_listing(description="Beautiful wetland property")
        self.assertEqual(_wetland_risk(l), "HIGH")

    def test_high_on_marsh(self):
        l = make_listing(description="50 acres including marsh areas")
        self.assertEqual(_wetland_risk(l), "HIGH")

    def test_medium_on_flood_zone(self):
        l = make_listing(description="Partially in flood zone AE")
        self.assertEqual(_wetland_risk(l), "MEDIUM")

    def test_medium_on_fema(self):
        l = make_listing(description="Check FEMA maps for flood designation")
        self.assertEqual(_wetland_risk(l), "MEDIUM")

    def test_unknown_when_no_signals(self):
        l = make_listing(description="Prime farmland with road frontage")
        self.assertEqual(_wetland_risk(l), "UNKNOWN")

    def test_high_takes_priority_over_medium(self):
        l = make_listing(description="Wetland area in flood zone")
        self.assertEqual(_wetland_risk(l), "HIGH")

    def test_scans_address_too(self):
        l = make_listing(description="Nice property", address="Swamp Road, Conway SC")
        self.assertEqual(_wetland_risk(l), "HIGH")


@pytest.mark.unit
class TestRoadAccess(unittest.TestCase):
    def test_yes_on_road_frontage(self):
        l = make_listing(description="150 ft of road frontage on county road")
        self.assertEqual(_road_access(l), "YES")

    def test_yes_on_paved_road(self):
        l = make_listing(description="Paved road access to property")
        self.assertEqual(_road_access(l), "YES")

    def test_no_on_landlocked(self):
        l = make_listing(description="Landlocked parcel, requires easement")
        self.assertEqual(_road_access(l), "NO")

    def test_unknown_when_not_mentioned(self):
        l = make_listing(description="Great farmland, 20 acres")
        self.assertEqual(_road_access(l), "UNKNOWN")


@pytest.mark.unit
class TestFilterAndScore(unittest.TestCase):
    def test_filters_by_price(self):
        listings = [make_listing(price=200000), make_listing(price=300000, listing_id="l2")]
        result = filter_and_score(listings, max_price=250000, min_acres=10)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].price, 200000)

    def test_filters_by_acres(self):
        listings = [make_listing(acres=15.0), make_listing(acres=5.0, listing_id="l2")]
        result = filter_and_score(listings, max_price=250000, min_acres=10)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].acres, 15.0)

    def test_scores_wetland_risk(self):
        l = make_listing(description="Property includes wetlands")
        result = filter_and_score([l], max_price=250000, min_acres=10)
        self.assertEqual(result[0].wetland_risk, "HIGH")

    def test_scores_road_access(self):
        l = make_listing(description="County road frontage on all sides")
        result = filter_and_score([l], max_price=250000, min_acres=10)
        self.assertEqual(result[0].road_access, "YES")

    def test_empty_input_returns_empty(self):
        self.assertEqual(filter_and_score([], 250000, 10), [])


if __name__ == "__main__":
    unittest.main()
