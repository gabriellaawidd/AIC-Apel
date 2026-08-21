# Cold Chain AI — Context Primer

> **Purpose of this file.** A compact, high-signal orientation for an AI model (or a new collaborator / judge) picking up this project cold. Read this first; the exhaustive per-function reference lives in `DOCUMENTATION_1.md` (original core) and `DOCUMENTATION_2.md` (M1 extensions: road-size awareness, live GPS, dynamic re-routing).

---

## What this is

A **quality-aware cold chain routing tool for perishable goods in Indonesia**, built for the "AI for the Backbone of the Economy" competition (Smart Logistics domain). Given a start and end point, it predicts **how fresh the cargo will still be on arrival** and gives a **realistic ETA band** — using live weather along the actual driving route and a published food-spoilage model.

The problem it targets: Indonesia loses a large share of perishable produce and fish to post-harvest and in-transit spoilage, worsened by cold-storage gaps and hot, humid, traffic-heavy logistics. This tool makes the freshness cost of a route *visible and quantified* before the truck leaves.

## Core philosophy (important — do not violate)

- **No trained ML models.** Every output is either a live API value (OSRM, Open-Meteo, MapKit) or a transparent arithmetic/scientific formula. This is a deliberate choice for explainability and reproducibility, not a gap to "fix" by adding a black-box model.
- **OSRM route geometry is the spine.** Weather sampling, spoilage, and ETA all hang off the one route.
- **Any future LLM layer narrates numbers, it never invents them.** All figures come from the Python functions.
- **Hackathon scope discipline.** Prefer a working, demoable slice over theoretical depth. Push back on scope creep.

---

## Architecture at a glance

```
start/end coords
      │
      ▼
   OSRM ──► route geometry + base duration
      │
      ├──► sample points along route ──► Open-Meteo ──► temp + rain per point
      │                                        │
      │                                        ▼
      │                              temperature profile (dt, temp)
      │                               ┌────────┴────────┐
      ▼                               ▼                 ▼
   ETA band  ◄── (optional MapKit   spoilage %      shared profile
                traffic-aware base)  (RRS model)      builder reused
      │
      ▼
  Browser (MapKit JS 6): route overlay + freshness % + ETA band
```

Two additive layers sit on top of that spine (M1, see `DOCUMENTATION_2.md`):

```
  F1  route geometry ──► local OSM/PostGIS ──► "is any road too narrow?"
      (veto layer — flags problems, never reroutes)

  F2  browser GPS ──► trip session ──► drift vs. the plan captured at departure
      (if drift: MapKit supplies alternatives, backend ranks them by freshness)
```

- **Backend:** `main.py` — FastAPI (Python), all endpoints + logic.
  `road_viability.py` (F1) and `trip_session.py` (F2) are separate modules.
- **Frontend:** `static/index.html` — Apple MapKit JS 6 (active; migrated from an earlier Leaflet version), plus `static/live-tracking.js` for the F2 GPS loop.
- **The application layer is HTTP calls + arithmetic**, not ML training. OSRM does routing internally; no custom pathfinding needed.
- **F1 needs a one-time local PostGIS + OSM import.** Without it, `/road-viability` reports `coverage: "unavailable"` and everything else works normally. F2 needs nothing extra.

## Stack

Python (FastAPI, uvicorn, requests) · OSRM public demo (routing) · Open-Meteo (weather) · Apple MapKit JS 6 (map render + traffic-aware ETA) · Ratkowsky square-root spoilage model.

---

## Endpoints

| Endpoint | What it returns |
|---|---|
| `GET /route` | Route geometry, duration, distance (OSRM) |
| `GET /temperature-profile` | Temp + rain sampled along the route over time |
| `GET /spoilage` | Freshness % remaining + per-segment damage |
| `GET /eta` | Optimistic / likely / pessimistic ETA band |
| `GET /mapkit-token` | Hands the frontend its MapKit token (or an error if unset) |

All take `start_lat, start_lng, end_lat, end_lng`. `/spoilage` adds `shelf_life_ref_hours` (default 72). `/eta` adds `departure_hour` (default 8) and an optional `eta_base_seconds` override.

**M1 additions** (all `POST`, full contracts in `DOCUMENTATION_2.md` §3):

| Endpoint | What it does |
|---|---|
| `POST /road-viability` | F1 — flags route segments too narrow for a vehicle profile |
| `POST /trip/create` | F2 — starts a trip, captures the baseline plan at departure |
| `POST /trip/{id}/position` | F2 — ingests a GPS fix, answers "is a re-route worth considering?" |
| `POST /trip/{id}/evaluate-alternatives` | F2 — ranks MapKit-supplied candidates by projected freshness |
| `POST /trip/{id}/accept-alternative` | F2 — records that the driver switched |

Two contract details that bite integrators: `overall_viable` can be **`null`** (meaning "couldn't check" — never collapse it to `false`), and `/trip/{id}/position` returns a **short response without freshness fields** when suppressed by its 120s cooldown.

## The spoilage model in one paragraph

`rrs(T)` = Relative Rate of Spoilage, square-root/Ratkowsky form: `((T − Tmin) / (Tref − Tmin))²`, with `Tref = 0 °C`, `Tmin = −10 °C`. It's a multiplier for how much faster food spoils at temperature `T` vs. the 0 °C reference. `compute_spoilage()` integrates this over the route's temperature timeline segment by segment to get `pct_fresh_remaining`. **Sanity check (FAO):** RRS = 1.0 at 0 °C, 2.25 at 5 °C, 4.0 at 10 °C. The one input the model can't derive itself is `shelf_life_ref_hours` — a commodity-specific literature value (FSSP / Dalgaard / FAO), currently a 72h placeholder.

## The ETA model in one paragraph

Take a base duration and multiply by a time-of-day factor (`f_time`, heavier in rush hours) and a weather factor (`f_weather`, heavier in rain) to get a likely time, plus an optimistic floor and pessimistic ceiling. The base is OSRM's free-flow duration by default, or MapKit's traffic-aware `expectedTravelTime` when supplied via `eta_base_seconds` — in which case `f_time` is skipped (`apply_time_factor=False`) so traffic isn't double-counted. All multipliers are **placeholders pending calibration**.

---

## How to run

```bash
source venv/bin/activate
pip install -r requirements.txt
MAPKIT_JS_TOKEN="eyJra..." uvicorn main:app --reload   # token optional
# open http://127.0.0.1:8000
```

Setting the token **on the same line** avoids the most common setup failure: a process captures its environment at launch, and `--reload` never re-reads it, so exporting after the server is already running has no effect.

The JSON endpoints work with or without a MapKit token, and F1/F2 are both usable without one. Demo route is hard-coded Jakarta → Bandung.

`/road-viability` additionally needs a one-time local PostgreSQL + PostGIS + OSM import (~1 hour, mostly waiting). Check whether a machine is ready:

```bash
./venv/bin/python -c "import main; print(main.road_viability(start_lat=-6.2088, start_lng=106.8456, end_lat=-6.9175, end_lng=107.6191)['coverage'])"
```

`partial`/`full` = ready. `unavailable` = import not done on this machine (everything else still works).

## Current state (as of this writing)

- ✅ `/route`, `/temperature-profile`, `/spoilage`, `/eta` all working end to end.
- ✅ **F1 road-size awareness** — implemented and verified against a real Java OSM import (1.34s for Jakarta→Bandung, 197 points checked). Degrades cleanly on machines without the import.
- ✅ **F2 live GPS + dynamic re-routing** — all four endpoints working end to end against live OSRM/Open-Meteo. 37 unit tests, no DB or network needed.
- 🚧 **MapKit JS 6 migration:** backend done; frontend done with a `handleEtaResult()` guard for the callback-vs-Promise ambiguity. Token now generated — remaining risk is the **domain restriction** on the token (localhost is not a registered origin) and confirming `directions.eta()` / `alternatives: true` resolution shapes live.
- 🧹 `main.py` has a **duplicate `compute_spoilage()` definition** (the rounded second one wins) — harmless, worth deleting.

## What's next (priority order)

1. **Wire F1 into F2** — check re-route candidates for road viability before offering them, so the system never suggests an "improvement" that's less truck-friendly. The pieces already fit (spec §3 step 5).
2. Confirm MapKit `directions.eta()` and `alternatives: true` shapes against a live token.
3. Tune F1's `search_radius_m` — at 50 m it sometimes matches a parallel footway instead of the actual road.
4. **Reefer vs non-reefer comparison** — run the route holding a constant setpoint vs. tracking ambient, show the freshness gap. Strongest single demo.
5. Real commodity shelf-life values, real truck dimensions, calibrated drift thresholds (all still placeholders).
6. Trip persistence (SQLite) — the in-memory store dies on every `--reload`.
7. Route-wide precipitation (currently uses departure point only).

## Gotchas to remember

- OSRM wants `lng,lat`; GeoJSON is `[lng, lat]`; `mapkit.Coordinate` wants `(lat, lng)`. Swaps happen in one place each — don't scatter them. **Exception:** `/trip/{id}/evaluate-alternatives` takes `[[lat, lng], ...]` because it receives MapKit `path` data directly.
- `app.mount("/", ...)` **must stay the last line** in `main.py`, or later routes get shadowed. This now matters more — five endpoints are registered above it.
- `export VAR=...` is session-scoped **and captured at process start**. `--reload` re-reads your *code*, never the environment, so a token exported after launch will not be picked up. Restart with `MAPKIT_JS_TOKEN="..." uvicorn ...` on one line.
- `--reload` runs two processes; `Ctrl+C` sometimes leaves the worker holding port 8000. `pkill -f "uvicorn main:app"` clears it. An `Address already in use` error means your *new* server never started — the old one is still answering, which makes config changes look like they failed.
- Never hard-code secrets (MapKit token) into source — they go in the environment, served via `/mapkit-token`.
- MapKit is only the *render + traffic-ETA + alternatives* layer. OSRM remains the routing/geometry source, and both F1 and F2 work without a MapKit token.
- The OSM `.pbf` and the PostGIS database live **outside** the repo. Never commit them.
- Geolocation needs a secure context. `localhost` counts; a LAN IP does not, and fails **silently**.

---

*Full technical reference: `DOCUMENTATION_1.md` (core) and `DOCUMENTATION_2.md` (M1 extensions + integration guide).*
