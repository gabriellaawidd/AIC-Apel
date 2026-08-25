


from __future__ import annotations
import sys
from pathlib import Path
from datetime import timedelta

from contracts import TempProfile, RouteCandidate, TripRequest

try:
    import requests
except ImportError:
    requests = None

OSRM_BASE = "http://router.project-osrm.org/route/v1/driving"
OPEN_METEO = "https://api.open-meteo.com/v1/forecast"

REEFER_SETPOINT_C = 4.0

SAMPLE_STEP_HOURS = 1.0
MIN_SAMPLES = 2
MAX_SAMPLES = 25
N_SAMPLES = 6


def samples_for_duration(total_hours: float) -> int:
    import math
    n = int(math.ceil(max(0.0, total_hours) / SAMPLE_STEP_HOURS)) + 1
    return max(MIN_SAMPLES, min(MAX_SAMPLES, n))


def _ambient_temps(req: TripRequest, route: RouteCandidate, n: int) -> list:

    o_lng, o_lat = req.origin
    d_lng, d_lat = req.destination

    geo = route.geometry
    if geo and len(geo) >= n:
        idx = [int(i * (len(geo) - 1) / (n - 1)) for i in range(n)]
        pts = [(geo[j][1], geo[j][0]) for j in idx]
    else:
        pts = [(o_lat + (d_lat - o_lat) * i / (n - 1),
                o_lng + (d_lng - o_lng) * i / (n - 1)) for i in range(n)]

    if requests is None:
        return [31.0] * n

    try:
        lat_list = ",".join(str(p[0]) for p in pts)
        lng_list = ",".join(str(p[1]) for p in pts)
        resp = requests.get(OPEN_METEO, params={
            "latitude": lat_list, "longitude": lng_list,
            "hourly": "temperature_2m", "timezone": "UTC", "forecast_days": 3,
        }, timeout=20).json()
        blocks = resp if isinstance(resp, list) else [resp]

        total_h = route.eta_hours_likely
        temps = []
        for i, w in enumerate(blocks[:n]):
            elapsed_h = total_h * i / (n - 1)
            when = req.departure_time + timedelta(hours=elapsed_h)
            key = when.strftime("%Y-%m-%dT%H:00")
            times = w["hourly"]["time"]
            arr = w["hourly"]["temperature_2m"]
            j = times.index(key) if key in times else 0
            temps.append(float(arr[j]))
        if len(temps) == n:
            return temps
    except Exception:
        pass
    return [31.0] * n


def build_temp_profile(route: RouteCandidate, req: TripRequest, n: int = None) -> TempProfile:

    total_h = route.eta_hours_likely
    if n is None:
        n = samples_for_duration(total_h)
    times_h = [round(min(total_h, i * SAMPLE_STEP_HOURS), 3) for i in range(n)]
    times_h[-1] = round(total_h, 3)

    if req.vehicle == "reefer":
        temps_c = [REEFER_SETPOINT_C] * n
        source = "reefer_setpoint"
    else:
        temps_c = _ambient_temps(req, route, n)
        source = "ambient_openmeteo"

    return TempProfile(route_id=route.route_id, times_h=times_h,
                       temps_c=temps_c, source=source)


if __name__ == "__main__":
    from datetime import datetime
    from routing import get_route_candidates
    req = TripRequest(origin=(106.8272, -6.1751), destination=(107.6098, -6.9147),
                      commodity="ikan_segar", departure_time=datetime(2026, 8, 20, 8, 0),
                      vehicle="non_reefer", preference="balanced")
    routes = get_route_candidates(req)
    for veh in ("non_reefer", "reefer"):
        req.vehicle = veh
        p = build_temp_profile(routes[0], req)
        print(f"[{veh:<10}] source={p.source:<18} "
              f"times_h={p.times_h} temps_c={[round(t,1) for t in p.temps_c]}")
