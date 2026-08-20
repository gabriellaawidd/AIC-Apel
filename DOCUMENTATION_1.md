# Cold Chain AI — Code Documentation

**Project:** Quality-aware cold chain routing for perishable goods (Indonesia)
**Competition:** "AI for the Backbone of the Economy" — Smart Logistics domain
**Scope of this document:** The two source files — `main.py` (FastAPI backend) and `static/index.html` (MapKit JS 6 frontend).
**Status:** Four analysis components work end to end (route drawing, temperature profiling, spoilage estimation, calibrated ETA). A migration from a Leaflet frontend to Apple **MapKit JS 6** is in progress; the backend fully supports it, and the frontend code is complete but blocked on a MapKit token (Apple Developer Program enrollment).

---

## 1. What this system does

Given a start and end coordinate, the system:

1. Asks **OSRM** for the driving route between the two points (the road path + a base travel duration).
2. Samples several points along that route and asks **Open-Meteo** for the ambient temperature and rainfall the cargo would be exposed to at each point, at the estimated time of passing it.
3. Runs a **spoilage model** (RRS square-root / Ratkowsky) over that temperature timeline to estimate how much freshness is left when the cargo arrives.
4. Produces a **calibrated ETA band** (optimistic / likely / pessimistic) by adjusting a base duration with time-of-day and weather factors. The base duration is OSRM's free-flow number by default, or a traffic-aware duration supplied by MapKit when available.
5. Draws all of this in the browser: the route on a map, plus a panel showing freshness % and the ETA band.

The design deliberately avoids trained machine-learning models. Every number comes from either an external service (OSRM, Open-Meteo, MapKit) or a transparent arithmetic/scientific formula. This is a design decision, not a limitation — it keeps the results explainable and reproducible.

---

## 2. Architecture and data flow

The core idea is that **the OSRM route geometry is the spine** everything else hangs off. The ETA layer reads its duration (or MapKit's traffic-aware duration); the temperature profile samples weather along its coordinates; the spoilage model consumes that temperature timeline.

```
                 ┌─────────────────────────────────────────────┐
   start/end     │                 main.py (FastAPI)            │
   coordinates ──▶                                              │
                 │   OSRM  ──▶ route geometry + base duration    │
                 │     │                                         │
                 │     ├──▶ sample points along route            │
                 │     │        │                                │
                 │     │        └──▶ Open-Meteo ──▶ temp + rain   │
                 │     │                 │          per point     │
                 │     │                 ▼                        │
                 │     │           temperature profile            │
                 │     │            (dt, temp) segments            │
                 │     │                 │                        │
                 │     │         ┌───────┴────────┐               │
                 │     ▼         ▼                ▼               │
                 │   ETA band   spoilage %     (both reuse the    │
                 │     ▲        (RRS model)      profile builder)  │
                 │     │                                          │
                 │  optional eta_base_seconds override            │
                 │  (traffic-aware duration from MapKit)          │
                 │                                                │
                 │   /mapkit-token ──▶ hands token to frontend    │
                 └─────────────────┬───────────────────────────┘
                                   │  JSON over HTTP
                                   ▼
                 ┌─────────────────────────────────────────────┐
                 │        static/index.html (MapKit JS 6)        │
                 │  draws route overlay + freshness % + ETA band │
                 │  asks MapKit for traffic-aware ETA, feeds it   │
                 │  back into /eta as eta_base_seconds            │
                 └─────────────────────────────────────────────┘
```

Two details worth remembering:

- `/spoilage` and `/eta` both internally call the same `temperature_profile()` function rather than re-implementing the OSRM call. That function is the shared workhorse.
- MapKit does **not** replace OSRM for routing. OSRM still provides the route geometry and the temperature-sampling path. MapKit only (a) renders the map and (b) supplies a traffic-aware travel time that is fed back into `/eta`.

---

## 3. Tech stack and dependencies

| Layer | Choice | Why |
|---|---|---|
| Backend framework | FastAPI | Lightweight, auto-generates docs, easy JSON endpoints |
| Server | Uvicorn | Runs the FastAPI app locally |
| HTTP client | requests | Calls OSRM and Open-Meteo |
| Routing (geometry + free-flow duration) | OSRM public demo server | Free, no key; road network + base duration |
| Weather | Open-Meteo | Free, no key; hourly temperature + precipitation |
| Frontend map | Apple MapKit JS 6 | Traffic-aware directions + native rendering (migration target) |
| Traffic-aware ETA | MapKit `mapkit.Directions` | Real-traffic `expectedTravelTime`, fed back into `/eta` |

**External services are called live.** OSRM's demo server and Open-Meteo are free and keyless, but the OSRM demo server is rate-limited (≈1 request/second) and offers no uptime guarantee. Fine for development and demos; not for production traffic. MapKit JS requires a token (see §6.2).

**Python packages** (installed in the project virtual environment):

```
fastapi
uvicorn
requests
```

---

## 4. Project structure

```
cold-chain-ai/
├── venv/              Virtual environment (not committed / ignored)
├── main.py            FastAPI backend — all endpoints and logic
├── DOCUMENTATION.md   This file
├── README.md          Quick-orientation context primer
└── static/
    └── index.html     MapKit JS 6 frontend (active)
```

> **Migration note.** Earlier iterations kept a Leaflet `index.html` and a parallel `index_mapkit.html`. The active frontend is now the MapKit version shown in §7. The Leaflet approach (OpenStreetMap tiles, `L.geoJSON()` for the route) was the prior iteration and is no longer the served page.

---

## 5. How to run

From the project folder, with the virtual environment active:

```bash
source venv/bin/activate          # activate the venv (macOS/Linux)

# Optional: enable the MapKit frontend once a token exists
export MAPKIT_JS_TOKEN="eyJra..."

uvicorn main:app --reload         # start the server
```

Then open `http://127.0.0.1:8000` in a browser. The `--reload` flag restarts the server automatically whenever `main.py` is saved.

To test individual endpoints, visit their URLs directly, e.g.:

```
http://127.0.0.1:8000/route?start_lat=-6.2088&start_lng=106.8456&end_lat=-6.9175&end_lng=107.6191
```

> **Current demo caveat.** The frontend `index.html` is the MapKit page. Until `MAPKIT_JS_TOKEN` is set, `/mapkit-token` returns an error and the map panel shows "MapKit not ready yet". The JSON API endpoints (`/route`, `/spoilage`, `/eta`, `/temperature-profile`) all work regardless of the token — only the visual map is blocked.

---

## 6. Backend reference (`main.py`)

### 6.1 Imports and app setup

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone
from math import radians, sin, cos, sqrt, atan2
from typing import Optional
import os
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OSRM_BASE = "http://router.project-osrm.org/route/v1/driving"
```

- **CORS middleware** allows the browser frontend to call the backend without cross-origin errors. `allow_origins=["*"]` is permissive — fine for local development; tighten it before any public deployment.
- **`OSRM_BASE`** is the base URL for OSRM's driving-profile routing endpoint. Every routing call is built on top of this string.
- **`Optional` / `os`** were added for the MapKit work: `os` reads the token from the environment; `Optional` types the new `eta_base_seconds` override on `/eta`.

---

### 6.2 `GET /mapkit-token` and MapKit token config

```python
MAPKIT_JS_TOKEN = os.environ.get("MAPKIT_JS_TOKEN", "")


@app.get("/mapkit-token")
def mapkit_token():
    if not MAPKIT_JS_TOKEN:
        return {
            "error": "MAPKIT_JS_TOKEN is not set yet. Generate a token in the "
                     "Apple Developer website once enrollment is approved, "
                     "then set it as an environment variable."
        }
    return {"token": MAPKIT_JS_TOKEN}
```

Hands the MapKit JS frontend its authorization token. Kept as a backend endpoint (rather than hard-coding the token into `index.html`) so the token lives only in the server's environment, never in source control.

- **MapKit JS 6 token model.** MapKit JS 6 (released June 2026) uses a static, domain-restricted token generated directly from the Apple Developer website (Maps → Create a Token). No private key / self-signed JWT is needed anymore, unlike the older MapKit JS 5 flow.
- **Setup once enrollment is approved:** (1) register a Maps identifier for the project's domain, (2) generate a token for it, (3) `export MAPKIT_JS_TOKEN="..."` before starting the server. Nothing in `main.py` needs to change.
- **Graceful un-configured state.** While `MAPKIT_JS_TOKEN` is unset, the endpoint returns a clear `{"error": ...}` object instead of crashing — the expected state until enrollment clears.

**Environment-variable note:** `export VAR=...` is scoped to the current shell session. A new terminal will not have the token set, so re-export (or add it to a shell profile / `.env` loader) when restarting.

---

### 6.3 `GET /route`

Returns the drawable route geometry plus base distance and duration.

```python
@app.get("/route")
def get_route(start_lat: float, start_lng: float, end_lat: float, end_lng: float):
    coords = f"{start_lng},{start_lat};{end_lng},{end_lat}"
    url = f"{OSRM_BASE}/{coords}"
    params = {"overview": "full", "geometries": "geojson"}

    response = requests.get(url, params=params)
    data = response.json()

    if data.get("code") != "Ok":
        return {"error": data.get("code", "unknown error")}

    route = data["routes"][0]
    return {
        "geometry": route["geometry"],
        "duration_seconds": route["duration"],
        "distance_meters": route["distance"],
    }
```

**Critical coordinate-order note:** OSRM expects coordinates as `longitude,latitude` (note the order), which is why `coords` is built as `{start_lng},{start_lat}`. The endpoint accepts `start_lat`/`start_lng` as separate, clearly-named parameters so callers never have to remember the swap — it happens in exactly one place.

- `overview=full` returns the complete route geometry (not a simplified version), which is what the temperature sampler needs.
- `geometries=geojson` makes OSRM return coordinates as GeoJSON. GeoJSON's `[lng, lat]` ordering is understood natively when drawing; note that the MapKit frontend re-swaps each point to `mapkit.Coordinate(lat, lng)` (see §7). (OSRM's default, `polyline`, would return an encoded string requiring a decoder.)

**Response shape:**

```json
{
  "geometry": { "type": "LineString", "coordinates": [[lng, lat], ...] },
  "duration_seconds": 7407.1,
  "distance_meters": 163238.2
}
```

---

### 6.4 `haversine_km()` — helper

Computes the great-circle distance in kilometres between two lat/lng points. Used to measure how far along a route each coordinate sits.

```python
def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371  # Earth radius in km
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng/2)**2
    return 2 * R * atan2(sqrt(a), sqrt(1-a))
```

Standard Haversine formula — nothing project-specific about it. It exists purely so the sampler below can space its sample points evenly by distance.

---

### 6.5 `sample_points_along_route()` — helper

Picks `n_samples` points evenly spaced **by distance** along the route (not by array index).

```python
def sample_points_along_route(coordinates, n_samples=6):
    cum_dist = [0.0]
    for i in range(1, len(coordinates)):
        lng1, lat1 = coordinates[i-1]
        lng2, lat2 = coordinates[i]
        cum_dist.append(cum_dist[-1] + haversine_km(lat1, lng1, lat2, lng2))

    total_dist = cum_dist[-1]
    if total_dist == 0:
        return [{"lat": coordinates[0][1], "lng": coordinates[0][0], "fraction": 0.0}]

    samples = []
    for i in range(n_samples):
        target_fraction = i / (n_samples - 1) if n_samples > 1 else 0
        target_dist = target_fraction * total_dist
        idx = min(range(len(cum_dist)), key=lambda j: abs(cum_dist[j] - target_dist))
        lng, lat = coordinates[idx]
        samples.append({"lat": lat, "lng": lng, "fraction": target_fraction})

    return samples
```

**Why distance-based, not index-based?** OSRM returns many more coordinates where a road curves and fewer on straight stretches. Sampling by array index would cluster samples around bends. Sampling by cumulative distance keeps the points evenly spread across the physical journey.

- `cum_dist` is the running total distance at each coordinate.
- `fraction` is how far into the trip a sample sits (0.0 = start, 1.0 = destination). This fraction is later multiplied by total duration to estimate arrival time at each point.

---

### 6.6 `GET /temperature-profile`

The shared workhorse. Builds the timeline of `(elapsed time, ambient temperature, rainfall)` the cargo experiences along the route.

```python
@app.get("/temperature-profile")
def temperature_profile(start_lat, start_lng, end_lat, end_lng, n_samples=6):
    # 1. OSRM route (same call as /route)
    # 2. sample points evenly by distance
    # 3. estimate elapsed time + clock time per point (steady-progress)
    # 4. one Open-Meteo call for all points (comma-separated coords)
    # 5. match each point's arrival hour to nearest hourly forecast entry
    ...
    return {
        "total_duration_seconds": total_duration_sec,
        "total_distance_meters": route["distance"],
        "profile": points,
    }
```

**Design assumptions worth knowing:**

- **Steady-progress assumption:** elapsed time is a simple fraction of total duration. It does not model the truck speeding up on highways and slowing in towns. Adequate for a temperature timeline; not a precise position-in-time model.
- **Multi-location response handling:** Open-Meteo returns a list when several coordinates are passed and a single object when one is passed. An `isinstance(..., list)` check normalises both cases.
- **Hour matching fallback:** if the target hour isn't in the returned forecast window, it falls back to the first available hour (`idx = 0`) rather than failing.

**Response shape:**

```json
{
  "total_duration_seconds": 7407.1,
  "total_distance_meters": 163238.2,
  "profile": [
    {
      "lat": -6.20875, "lng": 106.845627, "fraction": 0.0,
      "elapsed_seconds": 0.0, "eta_time": "2026-08-15T07:51:39+00:00",
      "ambient_temp_c": 32.9, "precipitation_mm": 0.0
    }
    // ... more points
  ]
}
```

---

### 6.7 `rrs()` — the spoilage rate model

The scientific core. Implements the **Relative Rate of Spoilage (RRS)**, square-root (Ratkowsky) form.

```python
def rrs(temp_c: float, t_ref: float = 0.0, t_min: float = -10.0) -> float:
    if temp_c <= t_min:
        return 0.0  # spoilage effectively halted
    return ((temp_c - t_min) / (t_ref - t_min)) ** 2
```

**The formula:** RRS(T) = ((T − Tmin) / (Tref − Tmin))²

- `t_ref` (default 0 °C) — the reference temperature at which a product's shelf life is known.
- `t_min` (default −10 °C) — the theoretical minimum temperature below which microbial growth effectively stops. A literature-sourced characteristic.
- The result is a **multiplier**: how many times faster spoilage happens at temperature `T` compared to the reference. RRS(Tref) = 1.

**Why this model and not Arrhenius:** for microbial spoilage of fresh food over the 0–25 °C cold-chain range, the square-root model tracks reality better than the Arrhenius equation, which curves rather than staying linear across wide temperature ranges. This follows the FSSP / Ratkowsky approach.

**Validation (FAO sanity check):** with Tmin = −10 °C the model reproduces FAO's empirical rule of thumb:

| Temperature | RRS | Expectation |
|---|---|---|
| 0 °C | 1.0 | reference baseline |
| 5 °C | 2.25 | FAO: ~doubles — ✓ |
| 10 °C | 4.0 | FAO: 5–6× — slightly conservative, acceptable |

These three values are a defensible "our model is validated, not arbitrary" claim.

---

### 6.8 `compute_spoilage()` — damage accumulation

Walks the temperature profile and accumulates spoilage damage segment by segment.

```python
def compute_spoilage(profile, shelf_life_ref_hours, t_ref=0.0, t_min=-10.0):
    damage = 0.0
    segments = []
    for i in range(1, len(profile)):
        dt_hours = (profile[i]["elapsed_seconds"] - profile[i-1]["elapsed_seconds"]) / 3600
        avg_temp = (profile[i]["ambient_temp_c"] + profile[i-1]["ambient_temp_c"]) / 2
        rate = rrs(avg_temp, t_ref=t_ref, t_min=t_min)
        segment_shelf_life = shelf_life_ref_hours / rate if rate > 0 else float("inf")
        segment_damage = dt_hours / segment_shelf_life
        damage += segment_damage
        segments.append({...})  # rounded per-segment breakdown
    pct_fresh = max(0.0, 1 - damage) * 100
    return {"pct_fresh_remaining": ..., "total_damage": ..., "segments": segments}
```

**The logic (additive time-temperature integration):**

- For each segment between two profile points, take its duration (`dt_hours`) and its average temperature.
- Convert temperature to a spoilage rate via `rrs()`.
- The effective shelf life *in that segment* is the reference shelf life divided by the rate (hotter = shorter effective shelf life).
- Damage in that segment = time spent ÷ effective shelf life.
- Sum damage across all segments. `damage = 1.0` means shelf life fully consumed.
- `pct_fresh_remaining = (1 − damage) × 100`, floored at 0.

**Required input — `shelf_life_ref_hours`:** the one commodity-specific number the model cannot derive on its own. It is the product's shelf life at `t_ref` (0 °C), sourced from published tables (FSSP, Dalgaard, FAO, USDA). The current default of 72 hours is a **placeholder** and should be replaced with a real, species-specific value for any demo.

> **⚠️ Cleanup flag — duplicate definition.** `main.py` currently defines `compute_spoilage()` **twice** (back to back). The two are nearly identical; the second definition (which rounds its output values) shadows and replaces the first, so the rounded version is the one actually used. This is harmless at runtime but confusing — delete the first definition to avoid ambiguity.

---

### 6.9 `GET /spoilage`

Thin wrapper that ties the profile builder to the spoilage model.

```python
@app.get("/spoilage")
def spoilage(start_lat, start_lng, end_lat, end_lng, shelf_life_ref_hours=72):
    temp_data = temperature_profile(start_lat, start_lng, end_lat, end_lng)
    if "error" in temp_data:
        return temp_data
    result = compute_spoilage(temp_data["profile"], shelf_life_ref_hours)
    result["route_duration_hours"] = round(temp_data["total_duration_seconds"] / 3600, 2)
    return result
```

Reuses `temperature_profile()`, feeds its output to `compute_spoilage()`, and adds a convenience `route_duration_hours` field.

**Response shape:**

```json
{
  "pct_fresh_remaining": 52.5,
  "total_damage": 0.4753,
  "segments": [ /* per-segment breakdown */ ],
  "route_duration_hours": 2.06
}
```

Because temperature comes from live forecast data, the exact number shifts slightly between calls made minutes apart — expected, not a bug.

---

### 6.10 ETA calibration functions

Three small functions turn a base duration into a realistic uncertainty band.

```python
def time_of_day_factor(departure_hour: int) -> float:
    if 6 <= departure_hour < 9:
        return 1.5
    elif 16 <= departure_hour < 20:
        return 1.6
    else:
        return 1.1


def weather_factor(precipitation_mm: float) -> float:
    if precipitation_mm >= 10:
        return 1.3
    elif precipitation_mm >= 1:
        return 1.15
    else:
        return 1.0


def calibrated_eta(eta_base_seconds, departure_hour, precipitation_mm,
                   apply_time_factor: bool = True) -> dict:
    f_time = time_of_day_factor(departure_hour) if apply_time_factor else 1.0
    f_weather = weather_factor(precipitation_mm)

    eta_likely = eta_base_seconds * f_time * f_weather
    eta_optimistic = eta_base_seconds * 1.05
    eta_pessimistic = eta_likely * 1.25

    return {
        "eta_base_seconds": round(eta_base_seconds, 1),
        "f_time": f_time,
        "f_weather": f_weather,
        "eta_optimistic_seconds": round(eta_optimistic, 1),
        "eta_likely_seconds": round(eta_likely, 1),
        "eta_pessimistic_seconds": round(eta_pessimistic, 1),
    }
```

**The logic:**

- `eta_base` = the base duration. By default OSRM's free-flow duration (tends to underestimate); when MapKit supplies a traffic-aware `expectedTravelTime`, that is passed in instead.
- `f_time` inflates it for rush-hour departures (morning 06–09, evening 16–20 heavier).
- `f_weather` inflates it for rain.
- `eta_likely` = base × time factor × weather factor.
- `eta_optimistic` = base × 1.05 (a floor slightly above the base number).
- `eta_pessimistic` = likely × 1.25 (a ceiling above the likely case).

**`apply_time_factor` — the double-count guard.** When the base duration already reflects real traffic (i.e. it came from MapKit), `f_time` would double-count rush hour: once inside MapKit's number and once via the multiplier. Passing `apply_time_factor=False` sets `f_time = 1.0` so the traffic-aware number is not inflated again. The `/eta` endpoint sets this automatically (see §6.11).

**The multipliers (1.5, 1.6, 1.1, 1.3, 1.15, 1.05, 1.25) are placeholders, not calibrated values.** They produce a reasonable band, but the intended next step is to *calibrate* them against a handful of real comparison numbers (e.g. MapKit / Google Maps for the demo route at several departure times) and adjust to match. This is calibration, not model training — quick and defensible. Once MapKit supplies the base duration, `f_time` calibration matters less (traffic is already baked in), and effort shifts to `f_weather` and the optimistic/pessimistic spread.

---

### 6.11 `GET /eta`

```python
@app.get("/eta")
def eta(start_lat, start_lng, end_lat, end_lng,
        departure_hour: int = 8, eta_base_seconds: Optional[float] = None):
    temp_data = temperature_profile(start_lat, start_lng, end_lat, end_lng)
    if "error" in temp_data:
        return temp_data

    using_traffic_aware_base = eta_base_seconds is not None
    base_seconds = eta_base_seconds if using_traffic_aware_base else temp_data["total_duration_seconds"]

    precipitation_mm = temp_data["profile"][0]["precipitation_mm"]

    band = calibrated_eta(base_seconds, departure_hour, precipitation_mm,
                          apply_time_factor=not using_traffic_aware_base)
    band["precipitation_mm_used"] = precipitation_mm
    band["source"] = "mapkit_traffic_aware" if using_traffic_aware_base else "osrm_free_flow"
    return band
```

**Two modes, selected automatically by whether `eta_base_seconds` is supplied:**

| `eta_base_seconds` | Base used | `apply_time_factor` | `source` field |
|---|---|---|---|
| omitted (default) | OSRM free-flow duration | `True` | `"osrm_free_flow"` |
| provided (from MapKit) | the supplied value | `False` | `"mapkit_traffic_aware"` |

The `source` field lets the frontend show which path produced the number. This is the endpoint change that unblocks the MapKit migration: the MapKit page fetches a traffic-aware time and passes it here as `eta_base_seconds`; the Leaflet-style default behavior (no override) is preserved untouched.

**Known simplification:** rainfall is taken from the **first** sample point only (`profile[0]`) — i.e. "rain near departure." A route-wide average or maximum would be more representative. Left simple for the MVP; flagged so it can be explained or upgraded.

**Response shape:**

```json
{
  "eta_base_seconds": 7407.1,
  "f_time": 1.5,
  "f_weather": 1.0,
  "eta_optimistic_seconds": 7777.5,
  "eta_likely_seconds": 11110.7,
  "eta_pessimistic_seconds": 13888.3,
  "precipitation_mm_used": 0.0,
  "source": "osrm_free_flow"
}
```

---

### 6.12 Static file mount

```python
app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

Serves the `static/` folder (the MapKit frontend) at the site root. **This line must stay last in the file** — it catches all otherwise-unmatched routes, so any endpoint defined after it would be shadowed and unreachable.

---

## 7. Frontend reference (`static/index.html`)

A single self-contained page using **Apple MapKit JS 6**: a map on top, a results panel below. It reuses the same backend endpoints as before, replacing only the rendering layer (Leaflet → MapKit) and adding a traffic-aware ETA path.

**Load and render sequence:**

1. **`loadMapKit()`** — fetches the token from `/mapkit-token`. If the token isn't configured, it shows "MapKit not ready yet" and stops. Otherwise it injects the MapKit JS 6 script (`https://cdn.apple-mapkit.com/mk/6/mapkit.core.js`) with `data-libraries="map,services,annotations,overlays"` and the token, and registers `onMapKitLoaded` as its callback.
2. **`onMapKitLoaded()`** — builds the `mapkit.Map`, drops start/end `MarkerAnnotation`s, then calls `drawOsrmRoute()` and `loadTrafficAwareEta()`.
3. **`drawOsrmRoute(map)`** — fetches `/route` (still OSRM), converts each GeoJSON `[lng, lat]` into a `mapkit.Coordinate(lat, lng)`, draws a `PolylineOverlay`, and fits the map region to the route's bounding box.
4. **`loadTrafficAwareEta()`** — creates `mapkit.Directions` and calls `directions.eta(request, callback)` with `transportType: mapkit.TransportType.Automobile` and a `destinations` array. Both the callback result and any returned Promise are routed through `handleEtaResult()`.
5. **`handleEtaResult(error, data)`** — an idempotent guard (`etaResultHandled` flag) so the panel renders exactly once whether MapKit resolves via callback or Promise. On success it passes MapKit's `expectedTravelTime` to `renderPanel()`; on failure it calls `renderPanel(null)` to fall back to OSRM's duration.
6. **`renderPanel(trafficAwareSeconds)`** — fetches `/spoilage` and `/eta` together via `Promise.all`. When a traffic-aware time exists it appends `&eta_base_seconds=...` to the `/eta` call. The panel shows freshness %, trip duration, the ETA band, and a debug line including `source`, `f_time`, `f_weather`, and rain used.

**Key MapKit JS 6 gotchas already handled in this file (from the migration debugging):**

- **Token via backend**, not hard-coded — supplied through `/mapkit-token`.
- **`overlays` library must be requested** in `data-libraries` or `PolylineOverlay` is undefined.
- **`destinations` is a plural array** on the directions request, not a single `destination`.
- **`transportType: mapkit.TransportType.Automobile`** — the older `mapkit.Directions.Transport` enum is deprecated.
- **Coordinate order** — GeoJSON is `[lng, lat]`; `mapkit.Coordinate` wants `(lat, lng)`, so each route point is swapped on the way in.
- **Promise vs callback for `directions.eta()`** — MapKit JS 6 may resolve via a returned Promise instead of the callback. The `handleEtaResult()` guard + dual handling covers both so the panel never hangs on "Waiting for MapKit token...".

**Current blocker:** everything above the token fetch is ready; the page cannot render the map until `MAPKIT_JS_TOKEN` is set on the server (pending Apple Developer Program enrollment). Whether `directions.eta()` resolves via callback or Promise in practice can only be confirmed once a token exists and the page actually loads.

---

## 8. API quick reference

| Endpoint | Query parameters | Returns |
|---|---|---|
| `GET /route` | `start_lat, start_lng, end_lat, end_lng` | Route geometry, duration (s), distance (m) |
| `GET /temperature-profile` | `start_lat, start_lng, end_lat, end_lng, n_samples` (default 6) | Per-point timeline of temp + rain along the route |
| `GET /spoilage` | `start_lat, start_lng, end_lat, end_lng, shelf_life_ref_hours` (default 72) | Freshness % remaining + per-segment damage |
| `GET /eta` | `start_lat, start_lng, end_lat, end_lng, departure_hour` (default 8), `eta_base_seconds` (optional) | Optimistic / likely / pessimistic ETA band + `source` |
| `GET /mapkit-token` | — | `{"token": ...}` or `{"error": ...}` if unset |

All coordinates are decimal degrees. The routing/weather endpoints return `{"error": "..."}` if OSRM cannot produce a route.

---

## 9. Known limitations and simplifications

These are intentional MVP scoping decisions, documented so they can be explained honestly or upgraded later.

1. **ETA base is traffic-oblivious until MapKit is live.** OSRM ignores live traffic and tends to underestimate. The band and the time/weather multipliers compensate transparently. MapKit's traffic-aware duration replaces this once a token is set; the plumbing is done.
2. **ETA rainfall uses only the departure point.** A route-wide average or maximum would be more representative.
3. **`shelf_life_ref_hours` default (72h) is a placeholder.** Real, species-specific values should come from FSSP / Dalgaard / FAO for any demo.
4. **Steady-progress time model.** Elapsed time at each point is a linear fraction of total duration; it doesn't model varying speed along the route.
5. **Cargo temperature = ambient temperature.** The current model assumes non-refrigerated transport (cargo tracks outside air). A refrigerated ("reefer") scenario would hold a constant setpoint instead — see roadmap.
6. **External service dependence.** OSRM demo server (≈1 req/s, no uptime guarantee) and Open-Meteo are live calls; results vary with real forecast data and network availability.
7. **MapKit map blocked on token.** The frontend map cannot render until `MAPKIT_JS_TOKEN` is configured. The JSON endpoints are unaffected.
8. **Duplicate `compute_spoilage()` definition** in `main.py` (see §6.8) — a cleanup item, not a runtime bug.
9. **Hard-coded demo inputs in the frontend.** Route (Jakarta → Bandung), commodity shelf life (72h), and departure hour (7) are fixed in `index.html`.

---

## 10. Roadmap (not yet built / in progress)

- **[in progress] MapKit JS 6 migration** — backend complete; frontend complete but blocked on token. Confirm `directions.eta()` resolution shape (callback vs Promise) once a token exists.
- **[next] Reefer vs non-reefer comparison** — run the same route twice, once tracking ambient temperature and once holding a constant refrigerated setpoint, and show the freshness gap side by side. A strong, intuitive demonstration of why cold chain matters.
- **Real commodity shelf-life data** — replace the 72h placeholder with looked-up values (FSSP / Dalgaard / FAO) for one or two specific products; consider a dropdown of pre-researched commodities.
- **Calibrate the ETA multipliers** — tune `f_time` / `f_weather` against real traffic-aware comparison numbers for the demo route.
- **Route-wide precipitation** — replace the departure-point-only rainfall with a route average or maximum in `/eta`.
- **User-editable inputs** — let the user pick start/end (map clicks), commodity, and departure time in the UI.
- **Route optimisation layer** — Pareto scoring across candidate routes on time / cost / spoilage-risk.
- **LLM narration layer** — a deterministic pipeline feeding an LLM that explains results and gives handling advice, with all numbers coming from the Python functions (never invented by the LLM).
