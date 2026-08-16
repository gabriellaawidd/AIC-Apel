"""
routing.py — M1 rute + ETA band  (owner: RIO)  [usulan QA, belum di-merge]
==========================================================================
Ini bentuk kontrak-patuh dari yang sekarang ada di main.py RIO. Sengaja ditulis
sebagai MODUL TERPISAH bernama routing.py — nama yang diminta acuan — dan
menghasilkan `RouteCandidate` sesuai contracts.py, bukan dict detik longgar.

Menyelesaikan 3 temuan di reports/rio-2026-08-16.md:
  [T2] hanya 1 rute        -> OSRM alternatives + 1 rute arteri = 3-5 kandidat
  [T3] band ETA terbalik   -> optimistic dihitung dari LIKELY, bukan base
  [T4] bentuk tak sesuai    -> keluar RouteCandidate (jam, route_id, toll_segments)

Yang TIDAK dilakukan di sini (sengaja):
  - Spoilage. Itu wilayah GAB (temuan T1). Modul ini hanya rute + ETA + suhu-hook.

Sumber: OSRM public demo (routing) — dipanggil live; ada fallback fixture kalau
server rate-limited/mati, supaya pipeline tetap demoable (lihat _FALLBACK).
"""

from __future__ import annotations
import sys
from pathlib import Path
from typing import List

from contracts import RouteCandidate, TripRequest

try:
    import requests
except ImportError:
    requests = None

OSRM_BASE = "http://router.project-osrm.org/route/v1/driving"


# ============================================================
# Faktor koreksi ETA — DIPORT PERSIS dari main.py RIO (placeholder).
# Ditaruh di sini supaya eta.py/routing.py berdiri sendiri; ganti dengan
# sumber traffic-aware saat kalibrasi. Tetap satu sumber angka (bukan ML).
# ============================================================
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


def eta_band_hours(base_seconds: float, departure_hour: int, precipitation_mm: float,
                   road_penalty: float = 1.0, apply_time_factor: bool = True) -> dict:
    """Pita ETA dalam JAM. [T3] optimistic relatif ke likely -> tak pernah terbalik.

    road_penalty: >1 untuk rute arteri/non-tol yg lebih lambat dari free-flow OSRM.
    """
    f_time = time_of_day_factor(departure_hour) if apply_time_factor else 1.0
    f_weather = weather_factor(precipitation_mm)

    likely = base_seconds * f_time * f_weather * road_penalty
    optimistic = likely * 0.90          # [T3] selalu <= likely
    pessimistic = likely * 1.25
    return {
        "likely_h": likely / 3600.0,
        "optimistic_h": optimistic / 3600.0,
        "pessimistic_h": pessimistic / 3600.0,
        "f_time": f_time,
        "f_weather": f_weather,
        "road_penalty": road_penalty,
    }


# ============================================================
# Peta koridor -> toll_segments  (kontrak dgn DAVIN)
# Encoding "ruas::asal::tujuan" — string yang BENAR-BENAR ADA di
# tarif_tol_jawa.csv milik DAVIN. Ini parameter statis skenario
# (rulebook: "parameter statis saat demo"). Tambah koridor sesuai kebutuhan.
# ============================================================
CORRIDOR_TOLL = {
    "jakarta_bandung": [
        "Jakarta-Cikampek dan Jakarta -Cikampek II Elevated::Jakarta IC::Karawang Timur",
        "Cikampek-Padalarang::SS Dawuan::SS Padalarang",
        "Padalarang-Cileunyi::SS Padalarang::Pasteur",
    ],
}


def _downsample(coords: list, n: int = 40) -> list:
    if len(coords) <= n:
        return coords
    step = len(coords) / n
    return [coords[int(i * step)] for i in range(n)]


def _osrm(coords_str: str, alternatives: bool) -> list:
    if requests is None:
        return []
    params = {"overview": "full", "geometries": "geojson"}
    if alternatives:
        params["alternatives"] = "true"
    try:
        r = requests.get(f"{OSRM_BASE}/{coords_str}", params=params, timeout=20).json()
        return r.get("routes", []) if r.get("code") == "Ok" else []
    except Exception:
        return []


# Fixture dipakai HANYA kalau OSRM tak terjangkau — supaya demo tetap jalan.
_FALLBACK = [
    dict(route_id="tol-1", name="Via Cipularang (tol, tercepat)", distance_km=167.7,
         base_h=2.08, uses_toll=True, corridor="jakarta_bandung", road_penalty=1.0),
    dict(route_id="tol-2", name="Via Cipularang alternatif (tol)", distance_km=171.2,
         base_h=2.16, uses_toll=True, corridor="jakarta_bandung", road_penalty=1.0),
    dict(route_id="arteri", name="Via Puncak (arteri, non-tol)", distance_km=138.0,
         base_h=2.30, uses_toll=False, corridor=None, road_penalty=1.9),
]


def get_route_candidates(req: TripRequest) -> List[RouteCandidate]:
    """Kontrak: 3-5 RouteCandidate (tol & non-tol) dgn pita ETA & toll_segments."""
    o_lng, o_lat = req.origin
    d_lng, d_lat = req.destination
    dep_hour = req.departure_time.hour

    raw = []  # (route_id, name, distance_km, base_seconds, uses_toll, corridor, road_penalty, geometry)

    # 1-2) rute tol via OSRM alternatives
    alt = _osrm(f"{o_lng},{o_lat};{d_lng},{d_lat}", alternatives=True)
    for i, rt in enumerate(alt[:3]):
        raw.append(dict(
            route_id=f"tol-{i+1}",
            name="Via Cipularang (tol)" if i == 0 else f"Rute tol alternatif {i+1}",
            distance_km=round(rt["distance"] / 1000, 1),
            base_seconds=rt["duration"], uses_toll=True, corridor="jakarta_bandung",
            road_penalty=1.0, geometry=_downsample(rt["geometry"]["coordinates"]),
        ))

    # 3) rute arteri non-tol via titik Puncak (opsi nyata, lebih lambat)
    via = f"{o_lng},{o_lat};107.1425,-6.8120;{d_lng},{d_lat}"
    art = _osrm(via, alternatives=False)
    if art:
        rt = art[0]
        raw.append(dict(
            route_id="arteri", name="Via Puncak (arteri, non-tol)",
            distance_km=round(rt["distance"] / 1000, 1),
            base_seconds=rt["duration"], uses_toll=False, corridor=None,
            road_penalty=1.9, geometry=_downsample(rt["geometry"]["coordinates"]),
        ))

    # fallback total kalau OSRM mati
    if not raw:
        for f in _FALLBACK:
            raw.append(dict(
                route_id=f["route_id"], name=f["name"], distance_km=f["distance_km"],
                base_seconds=f["base_h"] * 3600, uses_toll=f["uses_toll"],
                corridor=f["corridor"], road_penalty=f["road_penalty"], geometry=[],
            ))

    # precipitation placeholder (RIO ambil dari titik awal; di sini 0 utk determinisme)
    precip = 0.0

    candidates: List[RouteCandidate] = []
    for r in raw:
        band = eta_band_hours(r["base_seconds"], dep_hour, precip,
                              road_penalty=r["road_penalty"])
        toll_segments = CORRIDOR_TOLL.get(r["corridor"], []) if r["uses_toll"] else []
        candidates.append(RouteCandidate(
            route_id=r["route_id"], name=r["name"], distance_km=r["distance_km"],
            eta_hours_likely=round(band["likely_h"], 2),
            eta_hours_optimistic=round(band["optimistic_h"], 2),
            eta_hours_pessimistic=round(band["pessimistic_h"], 2),
            uses_toll=r["uses_toll"], toll_segments=toll_segments,
            geometry=r.get("geometry", []),
            assumptions={"f_time": band["f_time"], "f_weather": band["f_weather"],
                         "road_penalty": band["road_penalty"]},
        ))
    return candidates


if __name__ == "__main__":
    from datetime import datetime
    req = TripRequest(origin=(106.8272, -6.1751), destination=(107.6098, -6.9147),
                      commodity="ikan_segar", departure_time=datetime(2026, 8, 20, 8, 0),
                      vehicle="non_reefer", preference="balanced")
    for c in get_route_candidates(req):
        print(f"[{c.route_id:<7}] {c.name:<34} {c.distance_km:>6.1f} km | "
              f"ETA {c.eta_hours_optimistic:.2f}/{c.eta_hours_likely:.2f}/"
              f"{c.eta_hours_pessimistic:.2f} j | tol={c.uses_toll} | "
              f"seg={len(c.toll_segments)} | geom={len(c.geometry)}")
