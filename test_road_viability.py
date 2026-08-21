# test_road_viability.py
"""
Unit tests for F1 road classification (spec section 1.8, test 1).

Deliberately hits no database: classify_segment() and parse_width_m()
are pure functions over an OSM row dict, so they're testable on a
machine where the osm2pgsql import hasn't been run. Run with:

    python -m unittest test_road_viability -v
"""

import unittest

from road_viability import (
    VEHICLE_PROFILES,
    SAFETY_MARGIN_M,
    VehicleProfile,
    classify_segment,
    parse_width_m,
    _sample_indices,
)

SMALL = VEHICLE_PROFILES["small_reefer_truck"]   # 2.3m + 0.5m margin = 2.8m required
LARGE = VEHICLE_PROFILES["large_reefer_truck"]   # 2.6m + 0.5m margin = 3.1m required


def road(**kwargs) -> dict:
    """An OSM row with everything absent unless the test sets it."""
    base = {"osm_id": 1, "highway": None, "width": None, "surface": None, "access": None}
    base.update(kwargs)
    return base


class TestParseWidth(unittest.TestCase):
    def test_plain_numbers(self):
        self.assertEqual(parse_width_m("6"), 6.0)
        self.assertEqual(parse_width_m("6.5"), 6.5)

    def test_metric_suffix(self):
        self.assertEqual(parse_width_m("6 m"), 6.0)
        self.assertEqual(parse_width_m("3.2m"), 3.2)

    def test_unparseable_returns_none(self):
        # Guessing what these meant would be an invented number.
        for raw in ("narrow", "3;4", "10'", "", None, "wide enough"):
            with self.subTest(raw=raw):
                self.assertIsNone(parse_width_m(raw))

    def test_nonsense_values_rejected(self):
        self.assertIsNone(parse_width_m("0"))
        self.assertIsNone(parse_width_m("-3"))
        self.assertIsNone(parse_width_m("5000"))


class TestClassifySegment(unittest.TestCase):
    def test_tagged_wide_is_passable(self):
        verdict, reason = classify_segment(road(highway="residential", width="6"), SMALL)
        self.assertEqual(verdict, "passable")
        self.assertIn("6.0m", reason)

    def test_tagged_narrow_is_blocked(self):
        verdict, reason = classify_segment(road(highway="residential", width="2.5"), SMALL)
        self.assertEqual(verdict, "blocked")
        self.assertIn("2.8", reason)  # required width appears in the reason

    def test_safety_margin_is_applied(self):
        # 2.5m road, 2.3m truck: fits raw, fails once the margin is added.
        self.assertGreater(2.5, SMALL.width_m)
        verdict, _ = classify_segment(road(highway="residential", width="2.5"), SMALL)
        self.assertEqual(verdict, "blocked")

    def test_same_road_can_differ_by_vehicle(self):
        narrow_ish = road(highway="residential", width="3.0")
        self.assertEqual(classify_segment(narrow_ish, SMALL)[0], "passable")   # needs 2.8
        self.assertEqual(classify_segment(narrow_ish, LARGE)[0], "blocked")    # needs 3.1

    def test_untagged_primary_assumed_passable(self):
        verdict, reason = classify_segment(road(highway="primary"), SMALL)
        self.assertEqual(verdict, "passable")
        self.assertIn("wide by classification", reason)

    def test_untagged_motorway_link_assumed_passable(self):
        self.assertEqual(classify_segment(road(highway="motorway_link"), SMALL)[0], "passable")

    def test_untagged_residential_is_unknown_under_flag_policy(self):
        self.assertEqual(SMALL.treat_unknown_width_as, "flag")
        verdict, reason = classify_segment(road(highway="residential"), SMALL)
        self.assertEqual(verdict, "unknown")
        self.assertIn("no width tag", reason)

    def test_unknown_policy_is_configurable(self):
        permissive = VehicleProfile("permissive", 2.3, "passable")
        strict = VehicleProfile("strict", 2.3, "blocked")
        self.assertEqual(classify_segment(road(highway="residential"), permissive)[0], "passable")
        self.assertEqual(classify_segment(road(highway="residential"), strict)[0], "blocked")

    def test_access_private_is_blocked_even_when_wide(self):
        verdict, reason = classify_segment(
            road(highway="primary", width="12", access="private"), SMALL
        )
        self.assertEqual(verdict, "blocked")
        self.assertIn("access=private", reason)

    def test_excluded_highway_type_blocked_even_when_wide(self):
        verdict, reason = classify_segment(road(highway="footway", width="8"), SMALL)
        self.assertEqual(verdict, "blocked")
        self.assertIn("footway", reason)

    def test_unparseable_width_falls_through_to_unknown(self):
        verdict, _ = classify_segment(road(highway="residential", width="narrow"), SMALL)
        self.assertEqual(verdict, "unknown")

    def test_unparseable_width_on_primary_still_passable(self):
        verdict, _ = classify_segment(road(highway="primary", width="narrow"), SMALL)
        self.assertEqual(verdict, "passable")


class TestSampleIndices(unittest.TestCase):
    def test_respects_stride(self):
        self.assertEqual(_sample_indices(10, 3), [0, 3, 6, 9])

    def test_always_includes_final_point(self):
        # Plain [::3] on 11 points stops at index 9 and drops the
        # destination -- exactly where narrow delivery roads live.
        self.assertEqual(_sample_indices(11, 3)[-1], 10)

    def test_caps_database_round_trips_on_long_routes(self):
        from road_viability import MAX_POINTS_CHECKED
        indices = _sample_indices(5000, 3)
        self.assertLessEqual(len(indices), MAX_POINTS_CHECKED + 1)
        self.assertEqual(indices[-1], 4999)

    def test_empty_route(self):
        self.assertEqual(_sample_indices(0, 3), [])


if __name__ == "__main__":
    unittest.main()
