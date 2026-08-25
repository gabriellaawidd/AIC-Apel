


from __future__ import annotations

from typing import List, Optional

from contracts import RouteCandidate, TripRequest
from toll_detect import summarize_road_usage

try:
    import requests
except ImportError:
    requests = None

OSRM_BASE = "http://router.project-osrm.org/route/v1/driving"
OSRM_TIMEOUT = 25


def time_of_day_factor(departure_hour: int) -> float:
    if 6 <= departure_hour < 9:
        return 1.5
    if 16 <= departure_hour < 20:
        return 1.6
    return 1.1


def weather_factor(precipitation_mm: float) -> float:
    if precipitation_mm >= 10:
        return 1.3
    if precipitation_mm >= 1:
        return 1.15
    return 1.0


def road_penalty_from_mix(toll_km: float, non_toll_km: float) -> float:


    total = toll_km + non_toll_km
    if total <= 0:
        return 1.0
    return round(1.0 + 0.55 * (non_toll_km / total), 3)


def eta_band_hours(base_seconds: float, departure_hour: int, precipitation_mm: float,
                   road_penalty: float = 1.0, apply_time_factor: bool = True) -> dict:
    f_time = time_of_day_factor(departure_hour) if apply_time_factor else 1.0
    f_weather = weather_factor(precipitation_mm)

    likely = base_seconds * f_time * f_weather * road_penalty
    optimistic = likely * 0.90
    pessimistic = likely * 1.25
    return {
        "likely_h": likely / 3600.0,
        "optimistic_h": optimistic / 3600.0,
        "pessimistic_h": pessimistic / 3600.0,
        "f_time": f_time,
        "f_weather": f_weather,
        "road_penalty": road_penalty,
    }


VALIDATED_GATES = {
    "Jakarta-Cikampek dan Jakarta -Cikampek II Elevated": ("Jakarta IC", "Karawang Timur"),
    "Cikampek-Padalarang": ("SS Dawuan", "SS Padalarang"),
    "Padalarang-Cileunyi": ("SS Padalarang", "Pasteur"),
}

FULL_TRAVERSAL_RATIO = 0.85

_CORRIDOR_BOXES = {
    "jakarta": (106.60, -6.40, 107.05, -6.05),
    "bandung": (107.45, -7.05, 107.80, -6.80),
}


def _in_box(lon: float, lat: float, box) -> bool:
    return box[0] <= lon <= box[2] and box[1] <= lat <= box[3]


def _validated_corridor(req: TripRequest):
    ends = set()
    for lon, lat in (req.origin, req.destination):
        for name, box in _CORRIDOR_BOXES.items():
            if _in_box(lon, lat, box):
                ends.add(name)
    return "jakarta_bandung" if ends == {"jakarta", "bandung"} else None


def exact_gates_for(ruas_km: dict) -> dict:

    from toll_detect import ruas_length_km

    out = {}
    for ruas, km in (ruas_km or {}).items():
        gates = VALIDATED_GATES.get(ruas)
        if not gates:
            continue
        panjang = ruas_length_km(ruas)
        if panjang and km >= FULL_TRAVERSAL_RATIO * panjang:
            out[ruas] = gates
    return out


def _perp_distance(pt, start, end) -> float:
    (x, y), (x1, y1), (x2, y2) = pt, start, end
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
    t = ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    px, py = x1 + t * dx, y1 + t * dy
    return ((x - px) ** 2 + (y - py) ** 2) ** 0.5


def _rdp(points: list, epsilon: float) -> list:
    if len(points) < 3:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        dmax, idx = 0.0, i
        for k in range(i + 1, j):
            d = _perp_distance(points[k], points[i], points[j])
            if d > dmax:
                dmax, idx = d, k
        if dmax > epsilon:
            keep[idx] = True
            stack.append((i, idx))
            stack.append((idx, j))
    return [p for p, k in zip(points, keep) if k]


GEOM_EPSILON_DEG = 1e-4
GEOM_MAX_POINTS = 2500


def _simplify(coords: list) -> list:
    if not coords:
        return []
    pts = [(float(c[0]), float(c[1])) for c in coords]
    eps = GEOM_EPSILON_DEG
    out = _rdp(pts, eps)
    while len(out) > GEOM_MAX_POINTS and eps < 1e-2:
        eps *= 2
        out = _rdp(pts, eps)
    return [[round(x, 6), round(y, 6)] for x, y in out]


def _osrm(coords_str: str, *, alternatives: int = 0, exclude: str = None) -> list:
    if requests is None:
        return []
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "true",
    }
    if alternatives:
        params["alternatives"] = str(alternatives)
    if exclude:
        params["exclude"] = exclude
    try:
        r = requests.get(f"{OSRM_BASE}/{coords_str}", params=params, timeout=OSRM_TIMEOUT).json()
        return r.get("routes", []) if r.get("code") == "Ok" else []
    except Exception:
        return []


_FALLBACK = [
    dict(route_id="tol-1", name="Lewat tol — tercepat", distance_km=167.7,
         base_h=2.08, toll_km=150.0, non_toll_km=17.7),
    dict(route_id="tol-2", name="Lewat tol — alternatif", distance_km=171.2,
         base_h=2.16, toll_km=148.0, non_toll_km=23.2),
    dict(route_id="nontol-1", name="Tanpa tol — jalan arteri", distance_km=138.0,
         base_h=2.30, toll_km=0.0, non_toll_km=138.0),
]


def _is_duplicate(rt: dict, chosen: list) -> bool:
    for other in chosen:
        d_ratio = abs(rt["distance"] - other["distance"]) / max(1.0, other["distance"])
        t_ratio = abs(rt["duration"] - other["duration"]) / max(1.0, other["duration"])
        if d_ratio < 0.02 and t_ratio < 0.02:
            return True
    return False


def _longest_ruas(usage: dict) -> Optional[str]:
    ruas_km = usage.get("ruas_km") or {}
    if not ruas_km:
        return None
    return max(ruas_km.items(), key=lambda kv: kv[1])[0]


def _pretty_ruas(ruas: str) -> str:
    short = ruas.split("(")[0].strip()
    short = short.replace(" dan Jakarta -Cikampek II Elevated", "")
    return short


def get_route_candidates(req: TripRequest) -> List[RouteCandidate]:
    o_lng, o_lat = req.origin
    d_lng, d_lat = req.destination
    dep_hour = req.departure_time.hour
    coords_str = f"{o_lng},{o_lat};{d_lng},{d_lat}"

    picked: List[dict] = []

    for rt in _osrm(coords_str, alternatives=3):
        if not _is_duplicate(rt, picked):
            picked.append(rt)
        if len(picked) >= 4:
            break

    for rt in _osrm(coords_str, exclude="motorway"):
        if not _is_duplicate(rt, picked):
            rt["_forced_non_toll"] = True
            picked.append(rt)
        break

    raw: List[dict] = []
    if picked:
        for rt in picked:
            usage = summarize_road_usage(rt)
            toll_km = usage["toll_km"]
            non_toll_km = usage["non_toll_km"]
            if toll_km == 0 and non_toll_km == 0:
                non_toll_km = rt["distance"] / 1000.0
            uses_toll = toll_km >= 1.0 and not rt.get("_forced_non_toll")
            raw.append(dict(
                distance_km=round(rt["distance"] / 1000.0, 1),
                base_seconds=rt["duration"],
                uses_toll=uses_toll,
                toll_km=toll_km,
                non_toll_km=non_toll_km,
                usage=usage,
                geometry=_simplify(rt["geometry"]["coordinates"]),
            ))
    else:
        for f in _FALLBACK:
            raw.append(dict(
                distance_km=f["distance_km"],
                base_seconds=f["base_h"] * 3600,
                uses_toll=f["toll_km"] > 0,
                toll_km=f["toll_km"],
                non_toll_km=f["non_toll_km"],
                usage={"ruas_km": {}, "toll_road_names": [], "unknown_toll_names": []},
                geometry=[],
                fallback_name=f["name"],
                fallback_id=f["route_id"],
            ))

    precip = 0.0

    for r in raw:
        r["road_penalty"] = road_penalty_from_mix(r["toll_km"], r["non_toll_km"])
        r["band"] = eta_band_hours(r["base_seconds"], dep_hour, precip,
                                   road_penalty=r["road_penalty"])

    raw.sort(key=lambda r: r["band"]["likely_h"])
    tercepat = raw[0]

    n_tol = 0
    n_nontol = 0
    candidates: List[RouteCandidate] = []
    for idx, r in enumerate(raw):
        band = r["band"]
        usage = r["usage"]
        ruas_utama = _longest_ruas(usage)

        if r["uses_toll"]:
            n_tol += 1
            if idx == 0:
                nama = "Lewat tol — tercepat"
            elif ruas_utama:
                nama = f"Lewat tol — via {_pretty_ruas(ruas_utama)}"
            else:
                nama = f"Lewat tol — alternatif {n_tol}"
            rid = f"tol-{n_tol}"
        else:
            n_nontol += 1
            nama = ("Tanpa tol — jalan arteri" if n_nontol == 1
                    else f"Tanpa tol — alternatif {n_nontol}")
            rid = f"nontol-{n_nontol}"

        if r.get("fallback_name"):
            nama, rid = r["fallback_name"], r["fallback_id"]

        d_km = r["distance_km"] - tercepat["distance_km"]
        d_min = (band["likely_h"] - tercepat["band"]["likely_h"]) * 60.0
        bagian = []
        if idx == 0:
            bagian.append("Rute dengan waktu tempuh paling singkat")
        else:
            bagian.append(
                f"{abs(d_min):.0f} menit lebih {'lama' if d_min >= 0 else 'cepat'} "
                f"dan {abs(d_km):.1f} km lebih {'jauh' if d_km >= 0 else 'dekat'} "
                f"dibanding rute tercepat"
            )
        if r["uses_toll"]:
            nama_ruas = list((usage.get("ruas_km") or {}).keys())
            if nama_ruas:
                bagian.append("lewat " + ", ".join(_pretty_ruas(x) for x in nama_ruas[:3]))
            bagian.append(f"{r['toll_km']:.0f} km di jalan tol")
        else:
            bagian.append("seluruhnya jalan non-tol — tanpa biaya tol, "
                          "tetapi lebih lambat per kilometernya")
        summary = "; ".join(bagian) + "."

        ruas_km = dict(usage.get("ruas_km") or {})
        gates = exact_gates_for(ruas_km) if r["uses_toll"] else {}
        toll_segments = [f"{ruas}::{a}::{b}" for ruas, (a, b) in gates.items()]

        avg_speed = (r["distance_km"] / band["likely_h"]) if band["likely_h"] > 0 else 0.0

        cand = RouteCandidate(
            route_id=rid,
            name=nama,
            distance_km=r["distance_km"],
            eta_hours_likely=round(band["likely_h"], 2),
            eta_hours_optimistic=round(band["optimistic_h"], 2),
            eta_hours_pessimistic=round(band["pessimistic_h"], 2),
            uses_toll=r["uses_toll"],
            toll_segments=toll_segments,
            geometry=r.get("geometry", []),
            assumptions={
                "f_time": band["f_time"],
                "f_weather": band["f_weather"],
                "road_penalty": band["road_penalty"],
            },
            summary=summary,
            avg_speed_kmh=round(avg_speed, 1),
            toll_road_names=[_pretty_ruas(x) for x in (usage.get("ruas_km") or {})],
            toll_km=round(r["toll_km"], 1),
            non_toll_km=round(r["non_toll_km"], 1),
        )
        cand.ruas_km = ruas_km
        cand.exact_gates = gates
        candidates.append(cand)

    return candidates


if __name__ == "__main__":
    from datetime import datetime
    req = TripRequest(origin=(106.8272, -6.1751), destination=(107.6098, -6.9147),
                      commodity="ikan_segar", departure_time=datetime(2026, 8, 20, 8, 0),
                      vehicle="non_reefer", preference="balanced")
    for c in get_route_candidates(req):
        print(f"[{c.route_id:<9}] {c.name:<42} {c.distance_km:>6.1f} km | "
              f"ETA {c.eta_hours_likely:.2f} j | {c.avg_speed_kmh:>5.1f} km/j | "
              f"tol={c.uses_toll} ({c.toll_km:.0f} km) | titik geom={len(c.geometry)}")
        print(f"            {c.summary}")
