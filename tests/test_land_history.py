import csv
import os
import tempfile
import unittest
import pytest
from land_tracker.search import LandListing
from land_tracker.tracker import _diff, _load_history, _update_history


def make_listing(listing_id="l1", price=100000, acres=15.0,
                 wetland_risk="UNKNOWN", road_access="YES"):
    return LandListing(
        listing_id=listing_id,
        address="123 Farm Rd, Conway SC",
        price=price,
        acres=acres,
        description="Good farmland",
        url="https://example.com",
        source="test",
        wetland_risk=wetland_risk,
        road_access=road_access,
    )


def _write_history(path, rows):
    from land_tracker.tracker import _CSV_FIELDS
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


@pytest.mark.unit
class TestDiff(unittest.TestCase):
    def test_new_listing_detected(self):
        current = [make_listing("l1")]
        history = {}
        new, drops, gone = _diff(current, history)
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0].listing_id, "l1")

    def test_price_drop_detected(self):
        current = [make_listing("l1", price=90000)]
        history = {"l1": {"listing_id": "l1", "current_price": "100000", "status": "active"}}
        new, drops, gone = _diff(current, history)
        self.assertEqual(len(drops), 1)
        listing, old_price = drops[0]
        self.assertEqual(old_price, 100000)
        self.assertEqual(listing.price, 90000)

    def test_price_increase_not_a_drop(self):
        current = [make_listing("l1", price=110000)]
        history = {"l1": {"listing_id": "l1", "current_price": "100000", "status": "active"}}
        new, drops, gone = _diff(current, history)
        self.assertEqual(drops, [])

    def test_gone_listing_detected(self):
        current = []
        history = {"l1": {"listing_id": "l1", "current_price": "100000", "status": "active"}}
        new, drops, gone = _diff(current, history)
        self.assertEqual(gone, ["l1"])

    def test_already_gone_not_re_reported(self):
        current = []
        history = {"l1": {"listing_id": "l1", "current_price": "100000", "status": "gone"}}
        new, drops, gone = _diff(current, history)
        self.assertEqual(gone, [])


@pytest.mark.unit
class TestUpdateHistory(unittest.TestCase):
    def test_new_listing_written(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        try:
            history = _load_history(path)
            _update_history("2026-05-18", [make_listing("l1")], history, path)
            loaded = _load_history(path)
            self.assertIn("l1", loaded)
            self.assertEqual(loaded["l1"]["current_price"], "100000")
            self.assertEqual(loaded["l1"]["status"], "active")
        finally:
            os.unlink(path)

    def test_gone_listing_marked(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        try:
            _write_history(path, [{
                "listing_id": "l1", "first_seen": "2026-05-01", "last_seen": "2026-05-17",
                "address": "123 Farm Rd", "current_price": "100000", "min_price_seen": "100000",
                "acres": "15", "url": "", "source": "test",
                "wetland_risk": "UNKNOWN", "road_access": "YES", "status": "active",
            }])
            history = _load_history(path)
            _update_history("2026-05-18", [], history, path)
            loaded = _load_history(path)
            self.assertEqual(loaded["l1"]["status"], "gone")
        finally:
            os.unlink(path)

    def test_price_updated_min_tracked(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        try:
            _write_history(path, [{
                "listing_id": "l1", "first_seen": "2026-05-01", "last_seen": "2026-05-17",
                "address": "123 Farm Rd", "current_price": "100000", "min_price_seen": "100000",
                "acres": "15", "url": "", "source": "test",
                "wetland_risk": "UNKNOWN", "road_access": "YES", "status": "active",
            }])
            history = _load_history(path)
            _update_history("2026-05-18", [make_listing("l1", price=90000)], history, path)
            loaded = _load_history(path)
            self.assertEqual(loaded["l1"]["current_price"], "90000")
            self.assertEqual(loaded["l1"]["min_price_seen"], "90000")
        finally:
            os.unlink(path)

    def test_min_price_not_overwritten_on_increase(self):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        try:
            _write_history(path, [{
                "listing_id": "l1", "first_seen": "2026-05-01", "last_seen": "2026-05-17",
                "address": "123 Farm Rd", "current_price": "90000", "min_price_seen": "90000",
                "acres": "15", "url": "", "source": "test",
                "wetland_risk": "UNKNOWN", "road_access": "YES", "status": "active",
            }])
            history = _load_history(path)
            _update_history("2026-05-18", [make_listing("l1", price=110000)], history, path)
            loaded = _load_history(path)
            self.assertEqual(loaded["l1"]["min_price_seen"], "90000")  # preserved
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
