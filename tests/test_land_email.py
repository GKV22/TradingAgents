import unittest
import pytest
from land_tracker.search import LandListing
from land_tracker.email_report import build_html, build_subject


def make_listing(listing_id="l1", price=100000, acres=15.0,
                 wetland_risk="UNKNOWN", road_access="YES",
                 address="123 Farm Rd, Conway SC",
                 description="Good farmland"):
    return LandListing(
        listing_id=listing_id,
        address=address,
        price=price,
        acres=acres,
        description=description,
        url="https://example.com",
        source="test",
        wetland_risk=wetland_risk,
        road_access=road_access,
    )


@pytest.mark.unit
class TestBuildSubject(unittest.TestCase):
    def test_shows_new_count(self):
        s = build_subject(3, 0, 10, "29588", "2026-05-18")
        self.assertIn("3 new", s)
        self.assertIn("29588", s)

    def test_shows_price_drops(self):
        s = build_subject(0, 2, 10, "29588", "2026-05-18")
        self.assertIn("2 price drops", s)

    def test_no_changes_message(self):
        s = build_subject(0, 0, 5, "29588", "2026-05-18")
        self.assertIn("no changes", s)

    def test_shows_active_count(self):
        s = build_subject(0, 0, 7, "29588", "2026-05-18")
        self.assertIn("7 active", s)


@pytest.mark.unit
class TestBuildHtml(unittest.TestCase):
    def test_new_listings_shown(self):
        l = make_listing()
        html = build_html([l], [], 0, [l], "29588", "2026-05-18")
        self.assertIn("123 Farm Rd", html)
        self.assertIn("$100,000", html)
        self.assertIn("15 acres", html)

    def test_criteria_reflects_config(self):
        html = build_html([], [], 0, [], "29588", "2026-05-18", min_acres=5.0, max_price=250000)
        self.assertIn("≥5 acres", html)
        self.assertIn("$250,000", html)

    def test_criteria_default_values(self):
        html = build_html([], [], 0, [], "29588", "2026-05-18")
        self.assertIn("≥10 acres", html)

    def test_high_wetland_gets_red_background(self):
        l = make_listing(wetland_risk="HIGH")
        html = build_html([l], [], 0, [l], "29588", "2026-05-18")
        self.assertIn("#ffcccc", html)

    def test_medium_wetland_gets_yellow_background(self):
        l = make_listing(wetland_risk="MEDIUM")
        html = build_html([l], [], 0, [l], "29588", "2026-05-18")
        self.assertIn("#fff3cc", html)

    def test_price_drop_section_shown(self):
        l = make_listing(price=90000)
        html = build_html([], [(l, 100000)], 0, [l], "29588", "2026-05-18")
        self.assertIn("Price Drops", html)
        self.assertIn("$90,000", html)
        self.assertIn("$100,000", html)

    def test_price_drop_section_absent_when_none(self):
        html = build_html([], [], 0, [], "29588", "2026-05-18")
        self.assertNotIn("Price Drops", html)

    def test_html_escapes_address(self):
        l = make_listing(address='<script>alert("xss")</script>')
        html = build_html([l], [], 0, [l], "29588", "2026-05-18")
        self.assertNotIn("<script>", html)

    def test_search_link_present(self):
        html = build_html([], [], 0, [], "29588", "2026-05-18")
        self.assertIn("google.com/search", html)

    def test_gone_count_shown(self):
        html = build_html([], [], 3, [], "29588", "2026-05-18")
        self.assertIn("3 listing(s) removed", html)


if __name__ == "__main__":
    unittest.main()
