# trip_session.py
"""
Live trip tracking and dynamic re-routing (F2).

Introduces a stateful "trip" concept on top of the otherwise-stateless
route/spoilage/eta endpoints. A TripSession remembers the originally
planned route and its projected freshness/ETA, then compares that
baseline against reality as GPS position updates arrive.

Design note: this module reuses the existing temperature_profile() and
compute_spoilage() functions from main.py rather than reimplementing
spoilage math -- the only new logic here is session state and drift
detection. Keeps the no-invented-numbers constraint intact: every
freshness/ETA number still traces back to OSRM/MapKit + Open-Meteo +
the RRS formula, just recomputed from a moving start point.

Those functions arrive through configure() rather than an import.
main.py imports FROM this module, so importing back from main would be
circular -- and injection additionally lets the unit tests drive the
trigger logic with synthetic routes instead of live OSRM/Open-Meteo
calls (spec section 2.10, test 1).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional
import uuid

# --- Tunable thresholds -------------------------------------------------
# Open question 2 in spec section 4: these remain judgment calls, not
# calibrated values. Documented here so the reasoning is visible in the
# submission rather than buried as magic numbers.
FRESHNESS_DRIFT_THRESHOLD_PCT = 5.0    # TODO: tune with real data. Placeholder.
ETA_DRIFT_THRESHOLD_PCT = 15.0         # TODO: tune. Matches the magnitude of
                                        # the existing rush-hour multiplier in
                                        # calibrated_eta(), not an arbitrary
                                        # new number.
MIN_SECONDS_BETWEEN_REROUTE_CHECKS = 120  # avoid re-checking on every GPS ping


# --- Injected dependencies ---------------------------------------------
_get_route: Optional[Callable] = None
_temperature_profile: Optional[Callable] = None
_compute_spoilage: Optional[Callable] = None
_profile_from_geometry: Optional[Callable] = None


def configure(get_route, temperature_profile, compute_spoilage, profile_from_geometry):
    """
    Wire in main.py's existing route/weather/spoilage functions.

    profile_from_geometry(coordinates_lnglat, total_duration_seconds,
    n_samples) builds a temperature profile for a geometry we already
    hold, instead of asking OSRM to route it again -- needed for scoring
    MapKit alternatives, whose geometry came from MapKit, not OSRM.
    """
    global _get_route, _temperature_profile, _compute_spoilage, _profile_from_geometry
    _get_route = get_route
    _temperature_profile = temperature_profile
    _compute_spoilage = compute_spoilage
    _profile_from_geometry = profile_from_geometry


@dataclass
class PositionUpdate:
    lat: float
    lng: float
    accuracy_m: float
    timestamp: datetime


@dataclass
class TripSession:
    trip_id: str
    start_lat: float
    start_lng: float
    end_lat: float
    end_lng: float
    shelf_life_ref_hours: float
    departure_time: datetime

    original_route_geometry: list           # [[lng, lat], ...] GeoJSON order, from /route
    original_projected_freshness_pct: float  # from /spoilage at trip creation
    original_duration_seconds: float

    # The original plan's damage curve, kept so drift can be measured
    # against what the plan predicted for THIS moment rather than against
    # the whole-trip total. See should_suggest_reroute().
    original_spoilage_segments: list = field(default_factory=list)

    position_history: list[PositionUpdate] = field(default_factory=list)
    last_reroute_check: Optional[datetime] = None
    reroute_offered_count: int = 0
    active_route_geometry: Optional[list] = None  # set if driver accepts a re-route

    def last_position(self) -> Optional[PositionUpdate]:
        return self.position_history[-1] if self.position_history else None


# Module-level in-memory store.
# TODO: replace with SQLite (or similar) before anything beyond a
# single-machine demo -- this does not survive a server restart and
# will not work across multiple uvicorn workers. (Open question 3 in
# spec section 4.) Note during development: uvicorn --reload wipes every
# in-progress trip on each save of main.py. Expected friction, not a bug.
_trip_sessions: dict[str, TripSession] = {}


def create_trip_session(
    start_lat: float, start_lng: float, end_lat: float, end_lng: float,
    shelf_life_ref_hours: float = 72.0,
) -> TripSession:
    """
    Capture the baseline plan for a trip that is departing now.

    Called when the driver actually departs, not at route-planning time --
    departure_time is used as the clock against which all later drift is
    measured, so it has to be the real moment of departure.

    Raises ValueError if the underlying route/weather lookups fail, so
    the caller can return a clear error rather than storing a session
    with a meaningless baseline.
    """
    route_data = _get_route(start_lat, start_lng, end_lat, end_lng)
    if "error" in route_data:
        raise ValueError(f"could not plan route: {route_data['error']}")

    temp_data = _temperature_profile(start_lat, start_lng, end_lat, end_lng)
    if "error" in temp_data:
        raise ValueError(f"could not build temperature profile: {temp_data['error']}")

    spoilage_data = _compute_spoilage(temp_data["profile"], shelf_life_ref_hours)

    session = TripSession(
        trip_id=str(uuid.uuid4()),
        start_lat=start_lat, start_lng=start_lng,
        end_lat=end_lat, end_lng=end_lng,
        shelf_life_ref_hours=shelf_life_ref_hours,
        departure_time=datetime.now(timezone.utc),
        original_route_geometry=route_data["geometry"]["coordinates"],
        original_projected_freshness_pct=spoilage_data["pct_fresh_remaining"],
        original_duration_seconds=route_data["duration_seconds"],
        original_spoilage_segments=spoilage_data["segments"],
    )
    _trip_sessions[session.trip_id] = session
    return session


def get_trip_session(trip_id: str) -> Optional[TripSession]:
    return _trip_sessions.get(trip_id)


def damage_accrued_by(segments: list, elapsed_hours: float) -> float:
    """
    Integrate the original plan's damage curve up to elapsed_hours.

    compute_spoilage() returns per-segment damage with from_hours /
    to_hours bounds; this sums the segments already behind us and takes
    a linear share of the one we're currently inside. Linear within a
    segment is the same assumption compute_spoilage() already makes when
    it averages the two endpoint temperatures, so this introduces no new
    modelling -- it just reads the existing curve at a point in time.
    """
    if elapsed_hours <= 0:
        return 0.0

    total = 0.0
    for seg in segments:
        if seg["to_hours"] <= elapsed_hours:
            total += seg["segment_damage"]
            continue
        if seg["from_hours"] < elapsed_hours:
            span = seg["to_hours"] - seg["from_hours"]
            if span > 0:
                fraction = (elapsed_hours - seg["from_hours"]) / span
                total += seg["segment_damage"] * fraction
        break
    return total


def should_suggest_reroute(session: TripSession, current_lat: float, current_lng: float) -> dict:
    """
    Core trigger logic. Decides whether the current position warrants
    suggesting a re-route.

    Both comparisons here are deliberately NOT the naive ones sketched in
    spec section 2.5, because those compare quantities of different kinds
    and would essentially never fire:

    - Freshness: recomputing from the current position covers only the
      REMAINING leg, so it always looks better than the original
      whole-trip projection. Comparing them directly hides drift instead
      of detecting it. Instead we reconstruct a like-for-like projection
      of freshness AT DELIVERY: damage already accrued (read off the
      original plan's own curve, up to the elapsed time) plus damage
      projected for the remaining leg (recomputed live from here).

    - ETA: remaining duration from the current position is naturally
      smaller than the original total for the same reason. We compare it
      against what the original plan implies should be remaining right
      now (original total minus elapsed), and express the gap as a
      percentage of the original total.

    Returns {"reroute_suggested": False, ...} or a dict describing which
    trigger(s) fired and by how much.
    """
    now = datetime.now(timezone.utc)

    if session.last_reroute_check is not None:
        elapsed_since_check = (now - session.last_reroute_check).total_seconds()
        if elapsed_since_check < MIN_SECONDS_BETWEEN_REROUTE_CHECKS:
            return {
                "reroute_suggested": False,
                "reason": "cooldown",
                "seconds_until_next_check": round(
                    MIN_SECONDS_BETWEEN_REROUTE_CHECKS - elapsed_since_check, 1
                ),
            }
    session.last_reroute_check = now

    elapsed_seconds = (now - session.departure_time).total_seconds()
    elapsed_hours = elapsed_seconds / 3600

    # --- Freshness drift ------------------------------------------------
    temp_data = _temperature_profile(current_lat, current_lng,
                                     session.end_lat, session.end_lng)
    if "error" in temp_data:
        return {
            "reroute_suggested": False,
            "reason": "recompute_failed",
            "detail": temp_data["error"],
        }

    remaining = _compute_spoilage(temp_data["profile"], session.shelf_life_ref_hours)
    damage_so_far = damage_accrued_by(session.original_spoilage_segments, elapsed_hours)
    projected_total_damage = damage_so_far + remaining["total_damage"]
    current_projected_freshness_pct = max(0.0, 1 - projected_total_damage) * 100

    freshness_drift_pct = (
        session.original_projected_freshness_pct - current_projected_freshness_pct
    )

    # --- ETA drift ------------------------------------------------------
    eta_drift_pct = 0.0
    current_remaining_seconds = None
    route_data = _get_route(current_lat, current_lng, session.end_lat, session.end_lng)
    if "error" not in route_data:
        current_remaining_seconds = route_data["duration_seconds"]
        expected_remaining_seconds = max(
            0.0, session.original_duration_seconds - elapsed_seconds
        )
        if session.original_duration_seconds > 0:
            eta_drift_pct = (
                (current_remaining_seconds - expected_remaining_seconds)
                / session.original_duration_seconds * 100
            )

    triggers = []
    if freshness_drift_pct > FRESHNESS_DRIFT_THRESHOLD_PCT:
        triggers.append("freshness_drift")
    if eta_drift_pct > ETA_DRIFT_THRESHOLD_PCT:
        triggers.append("eta_drift")

    verdict = {
        "reroute_suggested": bool(triggers),
        "triggers": triggers,
        "current_projected_freshness_pct": round(current_projected_freshness_pct, 1),
        "original_projected_freshness_pct": session.original_projected_freshness_pct,
        "freshness_drift_pct": round(freshness_drift_pct, 1),
        "eta_drift_pct": round(eta_drift_pct, 1),
        "elapsed_seconds": round(elapsed_seconds, 1),
        "remaining_seconds": (
            round(current_remaining_seconds, 1) if current_remaining_seconds is not None else None
        ),
        "damage_accrued_so_far": round(damage_so_far, 4),
    }

    if triggers:
        session.reroute_offered_count += 1
        verdict["reroute_offered_count"] = session.reroute_offered_count

    return verdict


def _score_geometry(geometry_latlng: list, eta_seconds: float,
                    shelf_life_ref_hours: float) -> Optional[dict]:
    """
    Project freshness at delivery for one candidate geometry.

    geometry_latlng: [(lat, lng), ...] -- MapKit's order. Converted to
    GeoJSON [lng, lat] on the way into the profile builder, which shares
    main.py's convention.

    Note this scores the REMAINING leg only, which is the right basis for
    ranking candidates against each other: they all start from the same
    current position, so damage already accrued is a shared constant and
    doesn't affect their relative order.
    """
    if not geometry_latlng:
        return None

    coordinates_lnglat = [[lng, lat] for lat, lng in geometry_latlng]
    temp_data = _profile_from_geometry(coordinates_lnglat, eta_seconds)
    if "error" in temp_data:
        return None

    spoilage_data = _compute_spoilage(temp_data["profile"], shelf_life_ref_hours)
    return {
        "projected_freshness_pct": spoilage_data["pct_fresh_remaining"],
        "eta_seconds": round(eta_seconds, 1),
        "total_damage": spoilage_data["total_damage"],
    }


def evaluate_alternative_routes(session: TripSession, current_lat: float, current_lng: float,
                                alternatives: list[dict]) -> dict:
    """
    Score MapKit-provided alternative routes by projected freshness,
    reusing the same spoilage machinery as everywhere else in the app.

    alternatives: list of dicts shaped as
        { "geometry": [(lat, lng), ...], "eta_seconds": float }

    The currently-active route is scored on the same basis (recomputed
    from the current position) and returned alongside, so the frontend
    can show a delta rather than an unanchored list. Candidates that
    can't be scored are dropped with a note rather than ranked on a
    fabricated number.
    """
    baseline = None
    current_route_data = _get_route(current_lat, current_lng,
                                    session.end_lat, session.end_lng)
    if "error" not in current_route_data:
        baseline_geometry = [
            (lat, lng) for lng, lat in current_route_data["geometry"]["coordinates"]
        ]
        baseline = _score_geometry(
            baseline_geometry,
            current_route_data["duration_seconds"],
            session.shelf_life_ref_hours,
        )

    scored = []
    skipped = 0
    for i, candidate in enumerate(alternatives):
        geometry = candidate.get("geometry") or []
        eta_seconds = candidate.get("eta_seconds")
        if eta_seconds is None or not geometry:
            skipped += 1
            continue

        result = _score_geometry(geometry, float(eta_seconds),
                                 session.shelf_life_ref_hours)
        if result is None:
            skipped += 1
            continue

        result["candidate_index"] = i
        result["geometry"] = geometry
        if baseline is not None:
            result["freshness_delta_pct"] = round(
                result["projected_freshness_pct"] - baseline["projected_freshness_pct"], 1
            )
            result["eta_delta_seconds"] = round(
                result["eta_seconds"] - baseline["eta_seconds"], 1
            )
        scored.append(result)

    scored.sort(key=lambda c: c["projected_freshness_pct"], reverse=True)

    return {
        "current_route": baseline,
        "alternatives": scored,
        "skipped_candidate_count": skipped,
        "trip_id": session.trip_id,
    }


def accept_alternative(session: TripSession, geometry_latlng: list) -> None:
    """
    Record that the driver switched to an alternative. The original plan
    stays on the session for post-trip analysis (spec section 2.9 step 5).
    """
    session.active_route_geometry = geometry_latlng
