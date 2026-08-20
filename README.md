# Cold Chain AI — Context Primer

> **Purpose of this file.** A compact, high-signal orientation for an AI model (or a new collaborator / judge) picking up this project cold. Read this first; the exhaustive per-function reference lives in `DOCUMENTATION.md`.

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

- **Backend:** `main.py` — FastAPI (Python), all endpoints + logic.
- **Frontend:** `static/index.html` — Apple MapKit JS 6 (active; migrated from an earlier Leaflet version).
- **The application layer is HTTP calls + arithmetic**, not ML training. OSRM does routing internally; no custom pathfinding needed.

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

## The spoilage model in one paragraph

`rrs(T)` = Relative Rate of Spoilage, square-root/Ratkowsky form: `((T − Tmin) / (Tref − Tmin))²`, with `Tref = 0 °C`, `Tmin = −10 °C`. It's a multiplier for how much faster food spoils at temperature `T` vs. the 0 °C reference. `compute_spoilage()` integrates this over the route's temperature timeline segment by segment to get `pct_fresh_remaining`. **Sanity check (FAO):** RRS = 1.0 at 0 °C, 2.25 at 5 °C, 4.0 at 10 °C. The one input the model can't derive itself is `shelf_life_ref_hours` — a commodity-specific literature value (FSSP / Dalgaard / FAO), currently a 72h placeholder.

## The ETA model in one paragraph

Take a base duration and multiply by a time-of-day factor (`f_time`, heavier in rush hours) and a weather factor (`f_weather`, heavier in rain) to get a likely time, plus an optimistic floor and pessimistic ceiling. The base is OSRM's free-flow duration by default, or MapKit's traffic-aware `expectedTravelTime` when supplied via `eta_base_seconds` — in which case `f_time` is skipped (`apply_time_factor=False`) so traffic isn't double-counted. All multipliers are **placeholders pending calibration**.

---

## How to run

```bash
source venv/bin/activate
export MAPKIT_JS_TOKEN="..."   # optional; only needed for the map to render
uvicorn main:app --reload
# open http://127.0.0.1:8000
```

The JSON endpoints work with or without a MapKit token. Demo route is hard-coded Jakarta → Bandung.

## Current state (as of this writing)

- ✅ `/route`, `/temperature-profile`, `/spoilage`, `/eta` all working end to end.
- 🚧 **MapKit JS 6 migration:** backend done (`/mapkit-token`, `/eta` override); frontend code done with a `handleEtaResult()` guard for the callback-vs-Promise ambiguity. **Blocked on the MapKit token** (Apple Developer Program enrollment). Until the token is set, the map panel shows "MapKit not ready yet" — the API still works.
- 🧹 `main.py` has a **duplicate `compute_spoilage()` definition** (the rounded second one wins) — harmless, worth deleting.

## What's next (priority order)

1. Unblock MapKit (token) and confirm `directions.eta()` resolution shape live.
2. **Reefer vs non-reefer comparison** — run the route holding a constant setpoint vs. tracking ambient, show the freshness gap. Strongest single demo.
3. Real commodity shelf-life values to replace the 72h placeholder.
4. Calibrate ETA multipliers against real traffic-aware numbers.
5. Route-wide precipitation (currently uses departure point only).

## Gotchas to remember

- OSRM wants `lng,lat`; GeoJSON is `[lng, lat]`; `mapkit.Coordinate` wants `(lat, lng)`. Swaps happen in one place each — don't scatter them.
- `app.mount("/", ...)` **must stay the last line** in `main.py`, or later routes get shadowed.
- `export VAR=...` is session-scoped; a new terminal won't have the token.
- Never hard-code secrets (MapKit token) into source — they go in the environment, served via `/mapkit-token`.
- MapKit is only the *render + traffic-ETA* layer. OSRM remains the routing/geometry source.

---

*Full technical reference: see `DOCUMENTATION.md`.*
