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

# --- MapKit JS config ---------------------------------------------------
# MapKit JS 6 (released June 2026) uses a static, domain-restricted token
# generated straight from the Apple Developer website (Maps > Create a Token)
# -- no private key / self-signed JWT needed anymore, unlike the older
# MapKit JS 5 flow. Once the Developer Program enrollment is approved:
#   1. Register a Maps identifier for this project's domain
#   2. Generate a token for that identifier
#   3. Set it as an environment variable before starting the server:
#        export MAPKIT_JS_TOKEN="eyJra..."
# Nothing above needs to change in this file.

MAPKIT_JS_TOKEN = os.environ.get("MAPKIT_JS_TOKEN", "")


@app.get("/mapkit-token")
def mapkit_token():
    """
    Hands the MapKit JS frontend its authorization token.

    Kept as a backend endpoint (rather than hard-coding the token into
    index_mapkit.html) so the token never has to live in source control --
    only in the server's environment. Returns a clear "not configured yet"
    error instead of crashing while MAPKIT_JS_TOKEN is unset, which is the
    expected state until the Developer Program enrollment clears and a
    token has actually been generated.
    """
    if not MAPKIT_JS_TOKEN:
        return {
            "error": "MAPKIT_JS_TOKEN is not set yet. Generate a token in the "
                     "Apple Developer website once enrollment is approved, "
                     "then set it as an environment variable."
        }
    return {"token": MAPKIT_JS_TOKEN}


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


def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng/2)**2
    return 2 * R * atan2(sqrt(a), sqrt(1-a))


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


@app.get("/temperature-profile")
def temperature_profile(start_lat: float, start_lng: float, end_lat: float, end_lng: float, n_samples: int = 6):
    coords = f"{start_lng},{start_lat};{end_lng},{end_lat}"
    url = f"{OSRM_BASE}/{coords}"
    params = {"overview": "full", "geometries": "geojson"}
    osrm_data = requests.get(url, params=params).json()

    if osrm_data.get("code") != "Ok":
        return {"error": osrm_data.get("code", "unknown error")}

    route = osrm_data["routes"][0]
    total_duration_sec = route["duration"]
    geometry_coords = route["geometry"]["coordinates"]

    points = sample_points_along_route(geometry_coords, n_samples=n_samples)

    now = datetime.now(timezone.utc)
    for p in points:
        p["elapsed_seconds"] = p["fraction"] * total_duration_sec
        p["eta_time"] = (now + timedelta(seconds=p["elapsed_seconds"])).isoformat()

    lat_list = ",".join(str(p["lat"]) for p in points)
    lng_list = ",".join(str(p["lng"]) for p in points)

    weather_url = "https://api.open-meteo.com/v1/forecast"
    weather_params = {
        "latitude": lat_list,
        "longitude": lng_list,
        "hourly": "temperature_2m,precipitation",
        "timezone": "UTC",
        "forecast_days": 3,
    }
    weather_resp = requests.get(weather_url, params=weather_params).json()

    weather_by_point = weather_resp if isinstance(weather_resp, list) else [weather_resp]

    for p, w in zip(points, weather_by_point):
        hourly_times = w["hourly"]["time"]
        hourly_temps = w["hourly"]["temperature_2m"]
        hourly_precip = w["hourly"]["precipitation"]

        target_time = now + timedelta(seconds=p["elapsed_seconds"])
        target_str_hour = target_time.strftime("%Y-%m-%dT%H:00")

        if target_str_hour in hourly_times:
            idx = hourly_times.index(target_str_hour)
        else:
            idx = 0

        p["ambient_temp_c"] = hourly_temps[idx]
        p["precipitation_mm"] = hourly_precip[idx]

    return {
        "total_duration_seconds": total_duration_sec,
        "total_distance_meters": route["distance"],
        "profile": points,
    }

def rrs(temp_c: float, t_ref: float = 0.0, t_min: float = -10.0) -> float:
    """
    Relative Rate of Spoilage, square-root (Ratkowsky) model.
    RRS(T) = ((T - Tmin) / (Tref - Tmin))^2
    """
    if temp_c <= t_min:
        return 0.0  # spoilage effectively halted
    return ((temp_c - t_min) / (t_ref - t_min)) ** 2


def compute_spoilage(profile: list, shelf_life_ref_hours: float, t_ref: float = 0.0, t_min: float = -10.0):
    """
    profile: list of dicts with 'elapsed_seconds' and 'ambient_temp_c',
             sorted by elapsed_seconds (as returned by /temperature-profile)
    shelf_life_ref_hours: shelf life at t_ref, e.g. from FSSP/literature
    """
    damage = 0.0
    segments = []

    for i in range(1, len(profile)):
        dt_hours = (profile[i]["elapsed_seconds"] - profile[i-1]["elapsed_seconds"]) / 3600
        # use the average temp of the two endpoints for this segment
        avg_temp = (profile[i]["ambient_temp_c"] + profile[i-1]["ambient_temp_c"]) / 2

        rate = rrs(avg_temp, t_ref=t_ref, t_min=t_min)
        segment_shelf_life = shelf_life_ref_hours / rate if rate > 0 else float("inf")
        segment_damage = dt_hours / segment_shelf_life

        damage += segment_damage
        segments.append({
            "from_hours": profile[i-1]["elapsed_seconds"] / 3600,
            "to_hours": profile[i]["elapsed_seconds"] / 3600,
            "avg_temp_c": avg_temp,
            "rrs": rate,
            "segment_damage": segment_damage,
        })

    pct_fresh = max(0.0, 1 - damage) * 100
    return {
        "pct_fresh_remaining": pct_fresh,
        "total_damage": damage,
        "segments": segments,
    }

def compute_spoilage(profile: list, shelf_life_ref_hours: float, t_ref: float = 0.0, t_min: float = -10.0):
    damage = 0.0
    segments = []

    for i in range(1, len(profile)):
        dt_hours = (profile[i]["elapsed_seconds"] - profile[i-1]["elapsed_seconds"]) / 3600
        avg_temp = (profile[i]["ambient_temp_c"] + profile[i-1]["ambient_temp_c"]) / 2

        rate = rrs(avg_temp, t_ref=t_ref, t_min=t_min)
        segment_shelf_life = shelf_life_ref_hours / rate if rate > 0 else float("inf")
        segment_damage = dt_hours / segment_shelf_life

        damage += segment_damage
        segments.append({
            "from_hours": round(profile[i-1]["elapsed_seconds"] / 3600, 2),
            "to_hours": round(profile[i]["elapsed_seconds"] / 3600, 2),
            "avg_temp_c": round(avg_temp, 1),
            "rrs": round(rate, 2),
            "segment_damage": round(segment_damage, 4),
        })

    pct_fresh = max(0.0, 1 - damage) * 100
    return {
        "pct_fresh_remaining": round(pct_fresh, 1),
        "total_damage": round(damage, 4),
        "segments": segments,
    }



@app.get("/spoilage")
def spoilage(start_lat: float, start_lng: float, end_lat: float, end_lng: float, shelf_life_ref_hours: float = 72):
    temp_data = temperature_profile(start_lat, start_lng, end_lat, end_lng)
    if "error" in temp_data:
        return temp_data

    result = compute_spoilage(temp_data["profile"], shelf_life_ref_hours)
    result["route_duration_hours"] = round(temp_data["total_duration_seconds"] / 3600, 2)
    return result

def time_of_day_factor(departure_hour: int) -> float:
    """
    departure_hour: 0-23 (24-hour format)
    Returns a multiplier for OSRM's free-flow duration.
    Rough Jakarta-area rush hour assumption: 6-9am and 4-8pm are heavier.

    CHANGE VALUES LATER WITH TRAFFIC AWARE SOURCE
    """
    if 6 <= departure_hour < 9: 
        return 1.5
    elif 16 <= departure_hour < 20:
        return 1.6
    else:
        return 1.1

def weather_factor(precipitation_mm: float) -> float:
    """
    precipitation_mm: rainfall amount for the relevant hour
    Returns a multiplier for OSRM's free-flow duration.
    Heavier rain = slower traffic, more caution needed.
    """
    if precipitation_mm >= 10:
        return 1.3   # heavy rain
    elif precipitation_mm >= 1:
        return 1.15  # light-moderate rain
    else:
        return 1.0   # dry

def calibrated_eta(eta_base_seconds: float, departure_hour: int, precipitation_mm: float,
                    apply_time_factor: bool = True) -> dict:
    """
    eta_base_seconds: base duration in seconds. Either OSRM's free-flow
        number, or (once MapKit is wired up) MapKit Directions' traffic-aware
        expectedTravelTime.
    departure_hour: 0-23
    precipitation_mm: rainfall expected along the route
    apply_time_factor: set False when eta_base_seconds already reflects real
        traffic (e.g. from MapKit) -- otherwise rush hour gets counted twice,
        once by MapKit and once by our placeholder f_time multiplier.
    Returns optimistic / likely / pessimistic ETA band, in seconds.
    """
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

@app.get("/eta")
def eta(start_lat: float, start_lng: float, end_lat: float, end_lng: float,
        departure_hour: int = 8, eta_base_seconds: Optional[float] = None):
    """
    eta_base_seconds: optional override. Leave unset to keep using OSRM's
        free-flow duration (current Leaflet frontend behavior). Pass a value
        here once the MapKit frontend supplies a traffic-aware duration from
        mapkit.Directions -- f_time is then skipped automatically so traffic
        isn't double-counted.
    """
    temp_data = temperature_profile(start_lat, start_lng, end_lat, end_lng)
    if "error" in temp_data:
        return temp_data

    using_traffic_aware_base = eta_base_seconds is not None
    base_seconds = eta_base_seconds if using_traffic_aware_base else temp_data["total_duration_seconds"]

    # use the precipitation from the FIRST sample point (start of trip) as a simple stand-in
    # for "expected weather along the route" — refinable later
    precipitation_mm = temp_data["profile"][0]["precipitation_mm"]

    band = calibrated_eta(base_seconds, departure_hour, precipitation_mm,
                           apply_time_factor=not using_traffic_aware_base)
    band["precipitation_mm_used"] = precipitation_mm
    band["source"] = "mapkit_traffic_aware" if using_traffic_aware_base else "osrm_free_flow"
    return band

app.mount("/", StaticFiles(directory="static", html=True), name="static")