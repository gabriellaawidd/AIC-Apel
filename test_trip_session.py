# test_trip_session.py
"""
Unit tests for F2 re-route trigger logic (spec section 2.10, test 1).

Drives should_suggest_reroute() with injected fake route/weather/spoilage
functions instead of live OSRM and Open-Meteo calls, so the thresholds
can be exercised deterministically and offline. Run with:

    python -m unittest test_trip_session -v
"""

import unittest
from datetime import datetime, timedelta, timezone

import trip_session
from trip_session import (
    TripSession,
    FRESHNESS_DRIFT_THRESHOLD_PCT,
    ETA_DRIFT_THRESHOLD_PCT,
    MIN_SECONDS_BETWEEN_REROUTE_CHECKS,
    damage_accrued_by,
    should_suggest_reroute,
)


def make_session(*, original_freshness=80.0, original_duration=4 * 3600,
                 departed_minutes_ago=0.0, segments=None) -> TripSession:
    """
    A trip whose original plan accrues 0.05 damage per hour over 4 hours
    -- 0.20 total, i.e. 80% freshness at delivery. Matching
    original_freshness to that curve keeps the fixtures self-consistent.
    """
    if segments is None:
        segments = [
            {"from_hours": h, "to_hours": h + 1, "segment_damage": 0.05}
            for h in range(4)
        ]
    return TripSession(
        trip_id="test-trip",
        start_lat=-6.2088, start_lng=106.8456,
        end_lat=-6.9175, end_lng=107.6191,
        shelf_life_ref_hours=72.0,
        departure_time=datetime.now(timezone.utc) - timedelta(minutes=departed_minutes_ago),
        original_route_geometry=[[106.8456, -6.2088], [107.6191, -6.9175]],
        original_projected_freshness_pct=original_freshness,
        original_duration_seconds=original_duration,
        original_spoilage_segments=segments,
    )


class TriggerTestCase(unittest.TestCase):
    """Injects fakes for the functions trip_session normally gets from main."""

    remaining_damage = 0.20
    route_duration_seconds = 4 * 3600
    route_fails = False

    def setUp(self):
        test = self

        def fake_get_route(start_lat, start_lng, end_lat, end_lng):
            if test.route_fails:
                return {"error": "NoRoute"}
            return {
                "geometry": {"coordinates": [[start_lng, start_lat], [end_lng, end_lat]]},
                "duration_seconds": test.route_duration_seconds,
                "distance_meters": 150000.0,
            }

        def fake_temperature_profile(start_lat, start_lng, end_lat, end_lng, n_samples=6):
            return {"total_duration_seconds": test.route_duration_seconds, "profile": ["stub"]}

        def fake_compute_spoilage(profile, shelf_life_ref_hours, **kwargs):
            return {
                "pct_fresh_remaining": round(max(0.0, 1 - test.remaining_damage) * 100, 1),
                "total_damage": test.remaining_damage,
                "segments": [],
            }

        def fake_profile_from_geometry(coordinates_lnglat, total_duration_seconds, n_samples=6):
            return {"total_duration_seconds": total_duration_seconds, "profile": ["stub"]}

        trip_session.configure(
            get_route=fake_get_route,
            temperature_profile=fake_temperature_profile,
            compute_spoilage=fake_compute_spoilage,
            profile_from_geometry=fake_profile_from_geometry,
        )


class TestDamageAccrued(unittest.TestCase):
    SEGMENTS = [
        {"from_hours": 0, "to_hours": 1, "segment_damage": 0.05},
        {"from_hours": 1, "to_hours": 2, "segment_damage": 0.05},
        {"from_hours": 2, "to_hours": 3, "segment_damage": 0.10},
    ]

    def test_nothing_accrued_at_departure(self):
        self.assertEqual(damage_accrued_by(self.SEGMENTS, 0), 0.0)

    def test_whole_segments(self):
        self.assertAlmostEqual(damage_accrued_by(self.SEGMENTS, 2), 0.10)

    def test_partial_segment_is_prorated(self):
        # Half-way through the third segment: 0.05 + 0.05 + (0.10 * 0.5)
        self.assertAlmostEqual(damage_accrued_by(self.SEGMENTS, 2.5), 0.15)

    def test_past_the_end_caps_at_total(self):
        self.assertAlmostEqual(damage_accrued_by(self.SEGMENTS, 99), 0.20)


class TestFreshnessDrift(TriggerTestCase):
    def test_no_drift_when_conditions_match_plan(self):
        self.remaining_damage = 0.20   # exactly the original whole-trip damage
        session = make_session()
        verdict = should_suggest_reroute(session, -6.3, 106.9)
        self.assertFalse(verdict["reroute_suggested"])
        self.assertAlmostEqual(verdict["freshness_drift_pct"], 0.0)

    def test_drift_beyond_threshold_fires(self):
        self.remaining_damage = 0.35   # 65% at delivery vs 80% planned
        session = make_session()
        verdict = should_suggest_reroute(session, -6.3, 106.9)
        self.assertTrue(verdict["reroute_suggested"])
        self.assertIn("freshness_drift", verdict["triggers"])
        self.assertGreater(verdict["freshness_drift_pct"], FRESHNESS_DRIFT_THRESHOLD_PCT)

    def test_small_drift_stays_quiet(self):
        self.remaining_damage = 0.23   # 3 points worse -- under the 5-point threshold
        session = make_session()
        verdict = should_suggest_reroute(session, -6.3, 106.9)
        self.assertFalse(verdict["reroute_suggested"])

    def test_mid_trip_projection_includes_damage_already_accrued(self):
        """
        The regression the corrected drift math exists to prevent.

        Two hours into a four-hour trip, 0.10 damage is already behind
        us. If the remaining leg now projects 0.25 damage (planned: 0.10),
        freshness at delivery is 100 - (0.10 + 0.25) = 65%, a 15-point
        drift that must fire.

        Comparing the remaining leg alone against the original whole-trip
        number -- the naive reading of spec section 2.5 -- would report
        75% and a 5-point drift, which sits under the threshold and
        silently misses genuine degradation.
        """
        self.remaining_damage = 0.25
        session = make_session(departed_minutes_ago=120)
        verdict = should_suggest_reroute(session, -6.5, 107.1)

        self.assertAlmostEqual(verdict["damage_accrued_so_far"], 0.10, places=3)
        self.assertAlmostEqual(verdict["current_projected_freshness_pct"], 65.0, places=1)
        self.assertNotAlmostEqual(verdict["current_projected_freshness_pct"], 75.0, places=1)
        self.assertTrue(verdict["reroute_suggested"])


class TestEtaDrift(TriggerTestCase):
    # One hour into the four-hour plan, 0.05 damage is behind us and the
    # remaining three hours should cost 0.15. Holding the remaining leg
    # at exactly that keeps freshness on plan, so these tests isolate the
    # ETA trigger instead of accidentally tripping the freshness one.
    ON_SCHEDULE_REMAINING_DAMAGE = 0.15

    def test_on_schedule_does_not_fire(self):
        # One hour in, three hours of a four-hour trip left: exactly on plan.
        self.remaining_damage = self.ON_SCHEDULE_REMAINING_DAMAGE
        self.route_duration_seconds = 3 * 3600
        session = make_session(departed_minutes_ago=60)
        verdict = should_suggest_reroute(session, -6.4, 107.0)
        self.assertFalse(verdict["reroute_suggested"])
        self.assertAlmostEqual(verdict["eta_drift_pct"], 0.0, places=1)
        self.assertAlmostEqual(verdict["freshness_drift_pct"], 0.0, places=1)

    def test_remaining_time_is_not_compared_against_whole_trip(self):
        """
        Naively comparing remaining duration against the original TOTAL
        makes every in-progress trip look massively ahead of schedule,
        so the ETA trigger could never fire. Three hours remaining on a
        four-hour trip, one hour in, is drift of zero -- not -25%.
        """
        self.remaining_damage = self.ON_SCHEDULE_REMAINING_DAMAGE
        self.route_duration_seconds = 3 * 3600
        session = make_session(departed_minutes_ago=60)
        verdict = should_suggest_reroute(session, -6.4, 107.0)
        self.assertNotAlmostEqual(verdict["eta_drift_pct"], -25.0, places=1)

    def test_running_late_beyond_threshold_fires(self):
        # One hour in, but 3h50m still to go against 3h planned: +21%.
        # Freshness is held on plan so this proves the ETA trigger alone.
        self.remaining_damage = self.ON_SCHEDULE_REMAINING_DAMAGE
        self.route_duration_seconds = int(3.833 * 3600)
        session = make_session(departed_minutes_ago=60)
        verdict = should_suggest_reroute(session, -6.4, 107.0)
        self.assertTrue(verdict["reroute_suggested"])
        self.assertEqual(verdict["triggers"], ["eta_drift"])
        self.assertGreater(verdict["eta_drift_pct"], ETA_DRIFT_THRESHOLD_PCT)

    def test_route_failure_does_not_break_the_check(self):
        # A dead OSRM must not take down position ingestion; the
        # freshness trigger still gets evaluated.
        self.route_fails = True
        self.remaining_damage = 0.35
        session = make_session()
        verdict = should_suggest_reroute(session, -6.3, 106.9)
        self.assertTrue(verdict["reroute_suggested"])
        self.assertEqual(verdict["triggers"], ["freshness_drift"])
        self.assertIsNone(verdict["remaining_seconds"])


class TestCooldown(TriggerTestCase):
    def test_second_check_within_cooldown_is_suppressed(self):
        self.remaining_damage = 0.35   # would otherwise fire
        session = make_session()

        first = should_suggest_reroute(session, -6.3, 106.9)
        self.assertTrue(first["reroute_suggested"])

        second = should_suggest_reroute(session, -6.31, 106.91)
        self.assertFalse(second["reroute_suggested"])
        self.assertEqual(second["reason"], "cooldown")
        self.assertGreater(second["seconds_until_next_check"], 0)

    def test_check_resumes_after_cooldown_expires(self):
        self.remaining_damage = 0.35
        session = make_session()
        should_suggest_reroute(session, -6.3, 106.9)

        session.last_reroute_check = (
            datetime.now(timezone.utc)
            - timedelta(seconds=MIN_SECONDS_BETWEEN_REROUTE_CHECKS + 1)
        )
        verdict = should_suggest_reroute(session, -6.31, 106.91)
        self.assertTrue(verdict["reroute_suggested"])

    def test_cooldown_does_not_inflate_the_offered_count(self):
        self.remaining_damage = 0.35
        session = make_session()
        should_suggest_reroute(session, -6.3, 106.9)
        should_suggest_reroute(session, -6.31, 106.91)
        self.assertEqual(session.reroute_offered_count, 1)


class TestEvaluateAlternatives(TriggerTestCase):
    def test_candidates_rank_by_freshness_and_carry_deltas(self):
        session = make_session()
        alternatives = [
            {"geometry": [(-6.3, 106.9), (-6.9, 107.6)], "eta_seconds": 4000},
            {"geometry": [(-6.4, 107.0), (-6.9, 107.6)], "eta_seconds": 5000},
        ]
        result = trip_session.evaluate_alternative_routes(session, -6.3, 106.9, alternatives)

        self.assertIsNotNone(result["current_route"])
        self.assertEqual(len(result["alternatives"]), 2)
        self.assertEqual(result["skipped_candidate_count"], 0)
        for candidate in result["alternatives"]:
            self.assertIn("freshness_delta_pct", candidate)
            self.assertIn("eta_delta_seconds", candidate)

        scores = [c["projected_freshness_pct"] for c in result["alternatives"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_malformed_candidates_are_skipped_not_scored(self):
        session = make_session()
        alternatives = [
            {"geometry": [], "eta_seconds": 4000},          # no geometry
            {"geometry": [(-6.3, 106.9)]},                    # no eta
            {"geometry": [(-6.3, 106.9)], "eta_seconds": 4000},
        ]
        result = trip_session.evaluate_alternative_routes(session, -6.3, 106.9, alternatives)
        self.assertEqual(result["skipped_candidate_count"], 2)
        self.assertEqual(len(result["alternatives"]), 1)


if __name__ == "__main__":
    unittest.main()
