# road_viability.py
"""
Road-size awareness for truck routing (F1).

Queries a locally-imported OpenStreetMap PostGIS database (Java extract)
to check whether route segments pass through roads too narrow, or
otherwise unsuitable (access-restricted, unpaved track), for the
configured vehicle profile.

Design note: this module never invents a width. If a road segment has
no width tag and no reliable fallback, it is reported as UNKNOWN rather
than assumed passable or impassable -- the caller decides how to treat
unknowns (see VEHICLE_PROFILES below). This keeps the module consistent
with the rest of the project's no-invented-numbers constraint.

Setup required before this module works: see
F1_F2_IMPLEMENTATION_SPEC.md section 1.2 for the osm2pgsql import steps.
This module degrades cleanly when that setup hasn't been done -- psycopg2
missing, server down, or database absent all surface as
coverage="unavailable" rather than a 500, so /route and the rest of the
app keep working on a machine without the OSM import.
"""

import os
from dataclasses import dataclass
from typing import Optional

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:  # psycopg2 not installed -- F1 is simply unavailable
    psycopg2 = None
    RealDictCursor = None
    PSYCOPG2_AVAILABLE = False

# Aliased so `except _PgError` stays valid even when psycopg2 is absent
# (it would otherwise be an AttributeError on psycopg2.Error at the
# moment we're already handling a failure).
_PgError = psycopg2.Error if PSYCOPG2_AVAILABLE else ()


# Overridable so a teammate whose Homebrew Postgres has no "postgres"
# role (the macOS default -- see the setup runbook) can point at their
# own without editing source.
OSM_DB_DSN = os.environ.get("OSM_DB_DSN", "dbname=cold_chain_osm user=postgres")

# Road classes considered structurally unsuitable for a delivery truck
# regardless of tagged width -- footpaths, tracks, steps, etc.
EXCLUDED_HIGHWAY_TYPES = {"path", "footway", "steps", "track", "cycleway", "pedestrian"}

# Road classes large enough by classification alone that a missing
# width tag can be treated as "assume passable" -- these are built to
# carry significant traffic by definition.
WIDE_BY_DEFAULT_HIGHWAY_TYPES = {"motorway", "trunk", "primary", "secondary"}

# Link roads (motorway_link etc.) inherit the passability of the class
# they connect -- an on-ramp to a motorway is built for the same traffic.
WIDE_BY_DEFAULT_HIGHWAY_TYPES |= {t + "_link" for t in WIDE_BY_DEFAULT_HIGHWAY_TYPES}

# Extra clearance added on top of raw vehicle width when comparing
# against a tagged road width -- accounts for mirrors, safety margin,
# and the fact that OSM width tags are approximate.
SAFETY_MARGIN_M = 0.5

# Upper bound on how many points of a route get a database round-trip.
# A Jakarta->Bandung OSRM geometry is ~2000 points; even at
# sample_every_n_points=3 that would be ~660 queries and would blow the
# "<2 seconds" target in spec section 1.8. The stride widens automatically
# on long routes so the endpoint's latency stays bounded by route
# length rather than growing linearly with it.
MAX_POINTS_CHECKED = 200


class OsmDatabaseUnavailable(RuntimeError):
    """
    Raised when the OSM PostGIS database can't be reached at all --
    psycopg2 missing, server down, database not created, or the import
    never run. Distinct from "the database answered and had no roads
    there", which is a legitimate no_data result, not an error.
    """


@dataclass
class VehicleProfile:
    """
    Truck dimensions used to evaluate road viability.
    All values in meters. This is config, not a model -- these numbers
    should come from the vehicle spec sheet, not be inferred or guessed.
    """
    name: str
    width_m: float
    treat_unknown_width_as: str  # "passable" | "blocked" | "flag"


# TODO: replace placeholder values with real reefer truck dimensions
# for the demo vehicle class before the competition submission.
# (Open question 1 in spec section 4 -- still open, values unchanged
# from the spec so nobody mistakes a guess of mine for a spec sheet.)
VEHICLE_PROFILES = {
    "small_reefer_truck": VehicleProfile(
        name="small_reefer_truck",
        width_m=2.3,
        treat_unknown_width_as="flag",   # unknown segments get surfaced, not silently allowed
    ),
    "large_reefer_truck": VehicleProfile(
        name="large_reefer_truck",
        width_m=2.6,
        treat_unknown_width_as="flag",
    ),
}


def get_osm_connection():
    """
    Open a connection to the OSM PostGIS database.

    Callers should open ONE connection and pass it down through a whole
    route check rather than reconnecting per point -- connection setup
    dominates the cost of these small spatial queries. See
    check_route_viability(), which does exactly that.
    """
    if not PSYCOPG2_AVAILABLE:
        raise OsmDatabaseUnavailable(
            "psycopg2 is not installed -- run: pip install psycopg2-binary"
        )
    try:
        return psycopg2.connect(OSM_DB_DSN, cursor_factory=RealDictCursor)
    except _PgError as exc:
        raise OsmDatabaseUnavailable(
            f"could not connect to the OSM database ({OSM_DB_DSN}): {exc.args[0] if exc.args else exc}"
        ) from exc


# planet_osm_line.way is stored in Web Mercator (3857); the lat/lng we
# hold everywhere else is WGS84 (4326), so the point gets transformed
# rather than the geometry column -- transforming the column would
# defeat the GIST index built in step 7 of the setup runbook.
_ROADS_NEAR_POINT_SQL = """
    SELECT osm_id, highway, width, surface, access,
           ST_Distance(
               way,
               ST_Transform(ST_SetSRID(ST_MakePoint(%(lng)s, %(lat)s), 4326), 3857)
           ) AS dist_m
    FROM planet_osm_line
    WHERE highway IS NOT NULL
      AND ST_DWithin(
              way,
              ST_Transform(ST_SetSRID(ST_MakePoint(%(lng)s, %(lat)s), 4326), 3857),
              %(radius_m)s
          )
    ORDER BY dist_m ASC
    LIMIT %(limit)s;
"""


def query_roads_near_point(lat: float, lng: float, radius_m: float = 50.0,
                           conn=None, limit: int = 5) -> list[dict]:
    """
    Return OSM ways within radius_m of (lat, lng), ordered nearest first.

    conn: an open connection to reuse. When None, one is opened and
          closed for this single call -- convenient for ad-hoc use,
          wasteful in a loop.

    Note ST_MakePoint takes (lng, lat), not (lat, lng) -- the classic
    swap bug. lat and lng stay separate named parameters all the way
    down into the SQL for exactly that reason, matching the convention
    main.py already follows.

    Distances come back in Web Mercator meters, which at Java's latitude
    run about 0.6% larger than true ground meters. Irrelevant against a
    50 m search radius, but worth knowing before someone reports it.
    """
    own_connection = conn is None
    if own_connection:
        conn = get_osm_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(_ROADS_NEAR_POINT_SQL, {
                "lat": lat, "lng": lng, "radius_m": radius_m, "limit": limit,
            })
            return [dict(row) for row in cur.fetchall()]
    except _PgError as exc:
        raise OsmDatabaseUnavailable(
            f"query against planet_osm_line failed: {exc.args[0] if exc.args else exc}. "
            "Has the osm2pgsql import finished?"
        ) from exc
    finally:
        if own_connection:
            conn.close()


def parse_width_m(width_raw) -> Optional[float]:
    """
    Parse an OSM width tag into meters, or None when it isn't a plain
    metric measurement.

    OSM width tags are free text. "6", "6.5" and "6 m" all mean the same
    thing and are parsed. Anything else -- "narrow", "3;4" (two values),
    "10'" (feet), an empty string -- returns None and is treated as an
    absent tag by classify_segment(). Guessing what an ambiguous tag
    meant would be exactly the kind of invented number this project
    rules out.
    """
    if width_raw is None:
        return None

    text = str(width_raw).strip().lower()
    if not text:
        return None

    # Accept a trailing metric unit, reject everything else (notably
    # feet/inch marks, which are a different unit, not a suffix).
    if text.endswith("m"):
        text = text[:-1].strip()
    elif text.endswith("meter") or text.endswith("metre"):
        text = text.rsplit("m", 1)[0].strip()

    try:
        width = float(text)
    except ValueError:
        return None

    # A non-positive or absurd width is a tagging error, not a measurement.
    if width <= 0 or width > 100:
        return None
    return width


def classify_segment(road: dict, profile: VehicleProfile) -> tuple[str, str]:
    """
    Given a single OSM road row (as returned by query_roads_near_point)
    and a vehicle profile, return (verdict, reason) where verdict is
    one of "passable" | "blocked" | "unknown".

    Checks run in order of confidence: hard legal/structural exclusions
    first, then a measured width when one exists, then classification-
    based fallbacks, then the profile's policy for genuine unknowns.
    """
    access = (road.get("access") or "").strip().lower()
    if access in ("private", "no"):
        return "blocked", f"access={access}"

    highway = (road.get("highway") or "").strip().lower()
    if highway in EXCLUDED_HIGHWAY_TYPES:
        return "blocked", f"highway={highway} unsuitable for trucks"

    required_m = profile.width_m + SAFETY_MARGIN_M

    width_m = parse_width_m(road.get("width"))
    if width_m is not None:
        if width_m >= required_m:
            return "passable", f"width {width_m}m >= required {required_m}m"
        return "blocked", f"width {width_m}m < required {required_m}m"

    # No usable width tag from here down.
    if highway in WIDE_BY_DEFAULT_HIGHWAY_TYPES:
        return "passable", f"highway={highway}, no width tag, wide by classification"

    if profile.treat_unknown_width_as == "passable":
        return "passable", f"no width tag (highway={highway}), treated as passable per profile"
    if profile.treat_unknown_width_as == "blocked":
        return "blocked", f"no width tag (highway={highway}), treated as blocked per profile"
    return "unknown", f"no width tag, highway={highway}"


def _sample_indices(point_count: int, sample_every_n_points: int) -> list[int]:
    """
    Pick which route points to check.

    Honours sample_every_n_points, then widens the stride if that would
    exceed MAX_POINTS_CHECKED, and always includes the final point --
    plain [::n] slicing silently drops the destination whenever the
    point count isn't a multiple of n, and the last few hundred meters
    into a delivery address are exactly where narrow roads show up.
    """
    if point_count == 0:
        return []

    stride = max(1, sample_every_n_points)
    projected = (point_count + stride - 1) // stride
    if projected > MAX_POINTS_CHECKED:
        stride = (point_count + MAX_POINTS_CHECKED - 1) // MAX_POINTS_CHECKED

    indices = list(range(0, point_count, stride))
    if indices[-1] != point_count - 1:
        indices.append(point_count - 1)
    return indices


def check_route_viability(
    route_coordinates: list[tuple[float, float]],
    vehicle_profile_name: str = "small_reefer_truck",
    sample_every_n_points: int = 3,
    search_radius_m: float = 50.0,
) -> dict:
    """
    Main entry point. Takes route geometry as a list of (lat, lng) tuples
    -- same shape as the points already flowing through
    sample_points_along_route() in main.py -- and returns a viability
    verdict for the whole route.

    coverage tells the caller how much to trust overall_viable:
      "full"        every sampled point matched OSM road data
      "partial"     some points had no data or no usable width tag
      "no_data"     no sampled point matched any OSM road -- almost
                    certainly a route outside the Java extract
      "unavailable" the database itself could not be reached

    overall_viable is None when coverage is "unavailable", never False --
    "we couldn't check" must not read as "we checked and it's bad".
    """
    if vehicle_profile_name not in VEHICLE_PROFILES:
        return {
            "error": f"unknown vehicle_profile, choose from {list(VEHICLE_PROFILES)}",
        }
    profile = VEHICLE_PROFILES[vehicle_profile_name]

    indices = _sample_indices(len(route_coordinates), sample_every_n_points)
    if not indices:
        return {
            "overall_viable": None,
            "coverage": "no_data",
            "vehicle_profile": vehicle_profile_name,
            "blocked_segments": [],
            "unknown_segments": [],
            "sampled_point_count": 0,
        }

    blocked_segments: list[dict] = []
    unknown_segments: list[dict] = []
    no_osm_data_count = 0

    try:
        conn = get_osm_connection()
    except OsmDatabaseUnavailable as exc:
        return {
            "overall_viable": None,
            "coverage": "unavailable",
            "vehicle_profile": vehicle_profile_name,
            "blocked_segments": [],
            "unknown_segments": [],
            "sampled_point_count": 0,
            "error": str(exc),
        }

    try:
        for i in indices:
            lat, lng = route_coordinates[i]
            try:
                nearby = query_roads_near_point(lat, lng, search_radius_m, conn=conn)
            except OsmDatabaseUnavailable as exc:
                return {
                    "overall_viable": None,
                    "coverage": "unavailable",
                    "vehicle_profile": vehicle_profile_name,
                    "blocked_segments": [],
                    "unknown_segments": [],
                    "sampled_point_count": 0,
                    "error": str(exc),
                }

            if not nearby:
                no_osm_data_count += 1
                unknown_segments.append({
                    "lat": lat, "lng": lng, "osm_id": None,
                    "reason": f"no OSM road within {search_radius_m}m of this point",
                })
                continue

            # The nearest way is the representative segment for this point.
            road = nearby[0]
            verdict, reason = classify_segment(road, profile)
            record = {
                "lat": lat, "lng": lng,
                "osm_id": road.get("osm_id"),
                "highway": road.get("highway"),
                "reason": reason,
            }
            if verdict == "blocked":
                blocked_segments.append(record)
            elif verdict == "unknown":
                unknown_segments.append(record)
    finally:
        conn.close()

    sampled = len(indices)
    if no_osm_data_count == sampled:
        coverage = "no_data"
    elif unknown_segments:
        coverage = "partial"
    else:
        coverage = "full"

    return {
        # A route we have no data for is not "viable" -- it's unverified.
        "overall_viable": None if coverage == "no_data" else not blocked_segments,
        "coverage": coverage,
        "vehicle_profile": vehicle_profile_name,
        "vehicle_width_m": profile.width_m,
        "required_width_m": round(profile.width_m + SAFETY_MARGIN_M, 2),
        "blocked_segments": blocked_segments,
        "unknown_segments": unknown_segments,
        "sampled_point_count": sampled,
        "route_point_count": len(route_coordinates),
    }
