# Cold Chain AI — M1 Extensions Reference (F1 + F2)

> **Companion to `DOCUMENTATION_1.md`.** That file documents the original
> `/route`, `/temperature-profile`, `/spoilage` and `/eta` core. This one
> covers everything added in M1: road-size awareness (F1) and live GPS
> tracking with dynamic re-routing (F2). Nothing in the original core
> changed behaviour — see §6 for the one internal refactor.
>
> Implemented from `F1_F2_IMPLEMENTATION_SPEC.md`. Where this
> implementation deliberately departs from that spec, §7 says so and why.

---

## 1. What's new

**F1 — road size awareness.** Given a route, checks whether any segment
passes through a road too narrow (or otherwise unsuitable) for the
configured truck. Queries a locally imported OpenStreetMap PostGIS
database. It is a *veto layer*, not a routing engine — OSRM still
computes the path; F1 only flags problems with it.

**F2 — live trip tracking.** Introduces the system's first stateful
concept: a **trip**. A trip captures the plan at departure, ingests live
GPS positions from the driver's browser, and detects when reality has
drifted far enough from the plan to be worth re-routing. When it has, the
frontend fetches candidate routes from MapKit and the backend ranks them
by projected freshness.

Both are **additive**. No existing endpoint changed its contract.

---

## 2. Prerequisites and degradation

This is the most important section for integration, because the two
features have very different setup costs.

| Feature | Needs | If missing |
|---|---|---|
| F1 `/road-viability` | `psycopg2` + PostgreSQL + PostGIS + OSM import (~1h one-time) | Returns `coverage: "unavailable"` with an explanatory `error`. **Never 500s.** |
| F2 trip endpoints | Nothing beyond the existing stack | — |
| F2 route *alternatives* | MapKit JS token in the browser | Drift is still detected and surfaced; only the ranked-alternatives banner degrades to a plain warning |

**A machine without the OSM import runs the whole app fine.** F1 is the
only thing that goes quiet, by design — `road_viability.py` is imported
inside a `try/except` in `main.py`, so a missing `psycopg2` disables one
endpoint rather than stopping the server.

Setup for F1 is documented in `F1_F2_IMPLEMENTATION_SPEC.md` §1.2, with
corrections in the team setup runbook. Two corrections matter enough to
repeat: **do not** install `postgresql@15` alongside an existing server,
and **do not** use `--flat-nodes` for a Java-sized extract (it creates a
~90 GB file regardless of extract size).

Verify a machine is ready:

```bash
./venv/bin/python -c "
import main
r = main.road_viability(start_lat=-6.2088, start_lng=106.8456,
                        end_lat=-6.9175, end_lng=107.6191)
print(r['coverage'], '|', r['sampled_point_count'], 'points checked')
"
```

`partial` or `full` means ready. `unavailable` means the import hasn't
been done on that machine.

---

## 3. New endpoint reference

All four are `POST`. Scalars are **query parameters**; where a JSON body
is required it is called out explicitly.

### 3.1 `POST /road-viability`

Checks the OSRM route for this start/end pair against a vehicle profile.

**Query parameters**

| Name | Type | Default | Notes |
|---|---|---|---|
| `start_lat`, `start_lng`, `end_lat`, `end_lng` | float | — | required |
| `vehicle_profile` | string | `small_reefer_truck` | see §8.2 |
| `sample_every_n_points` | int | `3` | stride along the route geometry |

**Response**

```json
{
  "overall_viable": false,
  "coverage": "partial",
  "vehicle_profile": "small_reefer_truck",
  "vehicle_width_m": 2.3,
  "required_width_m": 2.8,
  "blocked_segments": [
    { "lat": -6.55, "lng": 107.21, "osm_id": 123456789,
      "highway": "living_street", "reason": "width 2.0m < required 2.8m" }
  ],
  "unknown_segments": [
    { "lat": -6.41, "lng": 107.02, "osm_id": 987654321,
      "highway": "residential", "reason": "no width tag, highway=residential" }
  ],
  "sampled_point_count": 197,
  "route_point_count": 4492,
  "route_duration_seconds": 7407.5
}
```

**`coverage` — read this before trusting `overall_viable`**

| Value | Meaning |
|---|---|
| `full` | Every sampled point matched OSM road data |
| `partial` | Some points had no data or no usable width tag |
| `no_data` | No sampled point matched any road — almost certainly outside the Java extract |
| `unavailable` | The database could not be reached at all |

**`overall_viable` is `true`, `false`, or `null`.** It is `null` whenever
coverage is `no_data` or `unavailable`. Integrators must not collapse
`null` into `false`: *"we could not check"* is not *"we checked and it is
bad"*. Treat `null` as "no signal" and show nothing.

### 3.2 `POST /trip/create`

Called once, when the driver **actually departs** — not at planning time.
`departure_time` becomes the clock all later drift is measured against,
so creating a trip early corrupts every subsequent comparison.

**Query parameters:** `start_lat`, `start_lng`, `end_lat`, `end_lng`,
`shelf_life_ref_hours` (default `72`).

```json
{
  "trip_id": "bf7568d3-74e2-459c-ba66-c39ee01b4741",
  "original_projected_freshness_pct": 64.4,
  "original_duration_seconds": 7407.5,
  "departure_time": "2026-08-21T13:48:06.484862+00:00",
  "end_lat": -6.9175,
  "end_lng": 107.6191
}
```

Returns `{"error": "..."}` if OSRM or Open-Meteo cannot produce a
baseline — no session is stored in that case, so there is no half-built
trip to clean up.

### 3.3 `POST /trip/{trip_id}/position`

Ingests one GPS fix and returns whether a re-route is worth considering.
Does **not** fetch alternatives itself.

**Query parameters:** `lat`, `lng`, `accuracy_m` (default `0.0`).

Full response, when a drift check actually ran:

```json
{
  "reroute_suggested": false,
  "triggers": [],
  "current_projected_freshness_pct": 69.6,
  "original_projected_freshness_pct": 64.4,
  "freshness_drift_pct": -5.2,
  "eta_drift_pct": -2.2,
  "elapsed_seconds": 0.1,
  "remaining_seconds": 7244.8,
  "damage_accrued_so_far": 0.0,
  "position_count": 1
}
```

**Short response, when suppressed by cooldown** — note the missing
freshness fields, which is the shape integrators most often trip over:

```json
{
  "reroute_suggested": false,
  "reason": "cooldown",
  "seconds_until_next_check": 118.1,
  "position_count": 2
}
```

A drift check runs at most once every `MIN_SECONDS_BETWEEN_REROUTE_CHECKS`
(120s), because each one costs an OSRM call plus an Open-Meteo call.
Position history is still recorded on every call. **Always check for the
presence of a field before reading it**, or key off `reason`.

Other early return: `{"reroute_suggested": false, "reason":
"recompute_failed", "detail": "..."}` when the weather lookup fails.
Live tracking survives a transient Open-Meteo outage rather than 500ing.

`triggers` is a list containing any of `"freshness_drift"`,
`"eta_drift"` — both can fire together.

### 3.4 `POST /trip/{trip_id}/evaluate-alternatives`

Ranks candidate routes by projected freshness. **Requires a JSON body.**

```json
{
  "alternatives": [
    { "geometry": [[-6.35, 106.95], [-6.60, 107.20]], "eta_seconds": 7000 }
  ],
  "current_lat": -6.35,
  "current_lng": 106.95
}
```

`geometry` is `[[lat, lng], ...]` — **MapKit order, not GeoJSON order.**
This is the one place in the codebase that takes lat-first, because it
receives MapKit `path` data directly. `current_lat`/`current_lng` are
optional; omitted, the backend falls back to the last recorded GPS fix,
then to the trip's start point.

```json
{
  "current_route": {
    "projected_freshness_pct": 69.6, "eta_seconds": 7244.8, "total_damage": 0.3037
  },
  "alternatives": [
    { "candidate_index": 0, "projected_freshness_pct": 69.4,
      "eta_seconds": 7000.0, "total_damage": 0.306,
      "freshness_delta_pct": -0.2, "eta_delta_seconds": -244.8,
      "geometry": [[-6.35, 106.95], [-6.60, 107.20]] }
  ],
  "skipped_candidate_count": 1,
  "trip_id": "bf7568d3-..."
}
```

Sorted by `projected_freshness_pct` descending, so `alternatives[0]` is
the best candidate. Deltas are relative to `current_route`, so a positive
`freshness_delta_pct` means genuinely better. Candidates that cannot be
scored are counted in `skipped_candidate_count` rather than ranked on a
fabricated number — **the best alternative can still be worse than the
current route**, and the caller must compare before offering a switch.

`current_route` is `null` if OSRM fails; the deltas are then absent.

### 3.5 `POST /trip/{trip_id}/accept-alternative`

Records that the driver switched. The original plan stays on the session
for post-trip analysis.

**Body:** `{"geometry": [[lat, lng], ...]}`

```json
{ "trip_id": "bf7568d3-...", "active_route_point_count": 3,
  "reroute_offered_count": 1 }
```

> This endpoint is not in the spec's §5 appendix, which lists four. It
> exists because §2.9 step 5 describes the behaviour ("treat the new
> route as the trip's active plan going forward") and nothing else
> implements it.

All five return `{"error": "no trip session found for trip_id=..."}`
for an unknown trip.

---

## 4. Integration recipes

### 4.1 Planning: route + viability

```
GET  /route                → draw it
POST /road-viability       → warn if overall_viable === false
```

Run them as **two separate calls**, not one. This was an explicit design
decision (spec §1.6, option (a)): folding the check into `/route` would
make every route call depend on the OSM database, so a teammate without
the import would lose routing entirely. Keeping it separate means F1 is
an optional signal layered on top.

Render three distinct states, not two:

- `overall_viable === false` → red: "N segment(s) may be too narrow"
- `unknown_segments.length > 0` with nothing blocked → amber: **"not
  confirmed"**, not "confirmed fine"
- `coverage` is `null`/`unavailable` → show nothing

### 4.2 A live trip

```
POST /trip/create                      → keep trip_id AND destination
     ↓  browser: navigator.geolocation.watchPosition()
POST /trip/{id}/position               → every ~30s or ~100m moved
     ↓  if reroute_suggested
     browser: mapkit.Directions({ alternatives: true })
POST /trip/{id}/evaluate-alternatives  → ranked candidates
     ↓  if driver accepts
POST /trip/{id}/accept-alternative
```

Three things the caller owns:

1. **Throttle position posts.** `watchPosition` fires on every small
   movement. `static/live-tracking.js` posts at most every 30s or 100m
   (whichever comes first), using the same haversine formula as the
   backend so both agree on distance.
2. **Store the destination client-side.** `/trip/create` returns
   `end_lat`/`end_lng` precisely because the alternatives call needs them
   and only the browser knows the trip is still running.
3. **Serialise the alternatives lookup.** A second position update can
   arrive while the first MapKit call is in flight. `live-tracking.js`
   guards this with a `pendingRerouteCheck` flag.

### 4.3 Secure context (F2 only)

The Geolocation API requires a secure context. `http://localhost` and
`http://127.0.0.1` qualify, so desktop development needs no TLS. Opening
the page on a phone via a LAN IP will **silently** deny location — no
error, just no fixes. A phone demo needs HTTPS (tunnel or local cert).

---

## 5. Module map

```
cold-chain-ai/
├── main.py                  FastAPI app — all endpoints, both features wired in
├── road_viability.py        F1: OSM/PostGIS queries + width classification
├── trip_session.py          F2: trip state, drift detection, alternative scoring
├── test_road_viability.py   20 tests, no database needed
├── test_trip_session.py     17 tests, no network needed
├── requirements.txt
└── static/
    ├── index.html           Map, controls, viability + reroute banners
    └── live-tracking.js     GPS loop, throttling, banner rendering
```

**`road_viability.py`** never invents a width. A road with no usable
width tag is reported `unknown`, and the *caller* decides what that
means via the profile's `treat_unknown_width_as` setting. This is the
same no-invented-numbers constraint the spoilage model follows.

**`trip_session.py`** receives `get_route`, `temperature_profile`,
`compute_spoilage` and `build_profile_from_geometry` through
`configure()` rather than importing them. `main.py` imports *from*
`trip_session`, so importing back would be circular — and injection is
what lets `test_trip_session.py` drive the trigger logic with synthetic
routes instead of live OSRM and Open-Meteo calls.

---

## 6. The one change to existing code

`temperature_profile()` was split. The weather-sampling half is now
`build_profile_from_geometry(coordinates_lnglat, total_duration_seconds,
n_samples=6)`, and the endpoint is a thin wrapper that fetches an OSRM
route and calls it.

**The `/temperature-profile` HTTP contract is unchanged.** The split
exists so F2 can score MapKit-supplied geometry: those candidate routes
came from MapKit, so sending them back through OSRM would both waste a
call and score a *different path* than the one the driver was offered.

`build_profile_from_geometry` also added error handling that
`temperature_profile` never had — a failed Open-Meteo call now returns
`{"error": ...}` instead of raising `KeyError` on `w["hourly"]`. F2
recomputes this on every position update, so a transient weather failure
must not take down live tracking.

If the main system calls `temperature_profile()` in-process, nothing
changes. If it wants a profile for a geometry it already holds, call
`build_profile_from_geometry()` and skip the OSRM round-trip.

---

## 7. Where this differs from the spec

Three deliberate departures, recorded so nobody "fixes" them back.

### 7.1 Drift comparisons were rebuilt

The math sketched in spec §2.5 compares quantities of different kinds and
would essentially never fire.

Recomputing freshness from the current position covers only the
**remaining** leg, so it always looks better than the original
whole-trip projection — the comparison hides drift instead of detecting
it. Same for ETA: remaining duration is naturally smaller than the
original total, so that trigger reads as permanently ahead of schedule.

What is implemented instead:

- **Freshness** reconstructs a like-for-like projection of freshness *at
  delivery*: damage already accrued (integrated off the original plan's
  own damage curve up to the elapsed time, via `damage_accrued_by()`)
  plus damage projected for the leg still ahead (recomputed live).
- **ETA** compares remaining-duration-now against what the plan implies
  should be remaining now (`original_duration − elapsed`), expressed as a
  percentage of the original total.

Concretely: a trip that degrades from 80% to 65% projected freshness
fires under the implemented version and stays **silent** under the naive
one. Both regressions are pinned by tests
(`test_mid_trip_projection_includes_damage_already_accrued`,
`test_remaining_time_is_not_compared_against_whole_trip`).

### 7.2 `overall_viable` can be `null`

Spec §1.9 asks that a no-coverage route not be silently called viable.
The inverse matters equally, so unverified routes return `null` rather
than `false`.

### 7.3 Sampling is capped

The spec's `sample_every_n_points=3` on a Jakarta–Bandung route (~4,500
geometry points) would mean ~1,500 database round-trips and blow the
"under 2 seconds" target in §1.8. `MAX_POINTS_CHECKED = 200` widens the
stride automatically on long routes, keeping latency bounded by route
length rather than growing linearly with it. Measured: **1.34s** for
Jakarta–Bandung, 197 points checked.

Sampling also always includes the **final** point. Plain `[::3]` slicing
drops the destination whenever the point count isn't a multiple of 3 —
and the last few hundred metres into a delivery address is exactly where
narrow roads appear.

---

## 8. Configuration

### 8.1 Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `MAPKIT_JS_TOKEN` | `""` | MapKit JS token, served via `/mapkit-token` |
| `OSM_DB_DSN` | `dbname=cold_chain_osm user=postgres` | F1 database connection |

`OSM_DB_DSN` exists because Homebrew's PostgreSQL creates a superuser
named after the macOS account, not `postgres`. A teammate who skipped
`createuser -s postgres` can point at their own role without editing
source.

### 8.2 Vehicle profiles (`road_viability.py`)

| Profile | Width | Unknown-width policy |
|---|---|---|
| `small_reefer_truck` | 2.3 m | `flag` |
| `large_reefer_truck` | 2.6 m | `flag` |

Plus `SAFETY_MARGIN_M = 0.5` for mirrors and OSM's approximate tags, so
`small_reefer_truck` actually requires 2.8 m of tagged width.

`treat_unknown_width_as` accepts `passable`, `blocked` or `flag`. `flag`
surfaces unknowns as their own category instead of silently allowing or
denying them.

> **Open question 1 (spec §4).** These dimensions are still the spec's
> placeholders. They need real reefer truck figures before submission.

### 8.3 Drift thresholds (`trip_session.py`)

| Constant | Value | Rationale |
|---|---|---|
| `FRESHNESS_DRIFT_THRESHOLD_PCT` | 5.0 | placeholder |
| `ETA_DRIFT_THRESHOLD_PCT` | 15.0 | matches the magnitude of the existing rush-hour multiplier in `calibrated_eta()` |
| `MIN_SECONDS_BETWEEN_REROUTE_CHECKS` | 120 | one OSRM + one Open-Meteo call per check |

> **Open question 2 (spec §4).** Judgment calls, not calibrated values.
> Whichever survives to submission should be documented as a deliberate
> choice rather than left as a bare constant.

---

## 9. Data quality — the honest caveat

Spec §1.8 asks for width-tag coverage to be recorded and published rather
than hidden. Measured against the imported Java extract:

| Road class | Ways | Tagged with width |
|---|---|---|
| `residential` | 1,936,499 | **5.11%** |
| `service` | 351,978 | 1.31% |
| `living_street` | 325,473 | 17.37% |
| `tertiary` | 50,025 | 16.86% |
| `secondary` | 24,023 | 21.68% |
| `primary` | 19,220 | 26.16% |
| `trunk` | 16,331 | 20.35% |
| `motorway` | 5,621 | 10.85% |

**94.9% of residential roads in Java carry no width tag.** This is the
single most important number in F1 and should be volunteered, not
defended: it is why unknowns are a first-class category, why the UI
separates "confirmed too narrow" from "width unknown", and why
`WIDE_BY_DEFAULT_HIGHWAY_TYPES` exists (a `primary` road is wide by
construction, so a missing tag there is safe to treat as passable).

---

## 10. Testing

```bash
./venv/bin/python -m unittest discover -p "test_*.py"
```

37 tests, ~0.002s, **no database and no network required** — they run on
a teammate's machine before the OSM import. Uses stdlib `unittest`, so
no test framework to install.

Coverage: width parsing including unparseable tags; every
`classify_segment` branch; sampling stride and the final-point rule;
damage integration; both drift triggers; cooldown; candidate ranking and
malformed-candidate handling.

For manual and end-to-end testing (spot-checking known-narrow Jakarta
streets, DevTools GPS override, forcing a drift trigger via curl), see
the team setup runbook.

---

## 11. Known limitations

Carried forward from the spec, plus what implementation revealed.

1. **Java-only coverage.** Routes outside Java return `coverage:
   "no_data"` and `overall_viable: null`.
2. **Width-tag sparsity** — see §9.
3. **Nearest-way matching can pick the wrong road.** The representative
   segment for a point is the closest OSM way within
   `search_radius_m` (50 m default). On the Jakarta–Bandung test route
   this flagged a `footway` running parallel to the actual road.
   Reducing the radius to ~25 m cuts these false positives at the cost
   of more `no data` points. **Not yet tuned.**
4. **In-memory trip store.** `_trip_sessions` does not survive a restart
   and will not work across multiple uvicorn workers. `uvicorn --reload`
   wipes in-progress trips on every save — expected friction, not a bug.
   (Open question 3: a SQLite upgrade before submission.)
5. **No automatic alternative generation.** F1 detects a problem; it does
   not route around it. F2 ranks alternatives *MapKit supplies*.
6. **F1 and F2 do not talk to each other yet.** Spec §3 step 5 wants
   re-route candidates checked for road viability before being offered,
   so the system never suggests an "improvement" that is less
   truck-friendly. Not implemented — this is the natural next task, and
   `check_route_viability()` already accepts the `[(lat, lng)]` shape
   that `evaluate_alternative_routes()` holds. (Open question 4.)
7. **Slum/informal-settlement exclusion is not solvable via OSM tags.**
   It would need a separate curated polygon dataset checked with
   `ST_Intersects`.
8. **Mercator distance.** Distances are computed in SRID 3857, ~0.6%
   larger than true ground metres at Java's latitude. Irrelevant against
   a 50 m radius; worth knowing before someone reports it as a bug.

---

## 12. Next tasks

1. **Wire F1 into F2** (§11.6) — highest value, and the pieces already fit.
2. **Tune `search_radius_m`** against the false-positive footway case.
3. **Real truck dimensions** (open question 1).
4. **Trip persistence** — SQLite, to survive `--reload` (open question 3).
5. **Document the threshold choices** (open question 2).
