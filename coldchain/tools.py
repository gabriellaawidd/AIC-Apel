"""Tool deterministik (KODE). Semua angka lahir di sini — bukan dari LLM.

External API (OSRM / Open-Meteo) dipakai bila `online=True` dan jaringan tersedia;
selain itu memakai mock deterministik agar demo reproducible & jalan offline.
"""
from __future__ import annotations
import hashlib
from datetime import datetime
from typing import List, Dict, Any

from . import config
from .state import Route, Eta, Spoilage


def _seed(*parts) -> int:
    h = hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()
    return int(h[:8], 16)


# --------------------------------------------------------------------------
# 1. get_routes  (OSRM)
# --------------------------------------------------------------------------
def get_routes(origin: Dict, destination: Dict, alternatives: int = 4) -> List[Route]:
    """Mock deterministik 3-5 rute kandidat. Ganti isi ini dengan panggilan OSRM
    `/route/v1/driving/...?alternatives=true` saat online."""
    alternatives = max(3, min(5, alternatives))
    base = _seed(origin.get("name"), destination.get("name"))
    base_km = 80 + (base % 60)                # 80-139 km
    routes = []
    for i in range(alternatives):
        km = round(base_km * (1 + 0.08 * i), 1)
        dur = round(km / (0.75 + 0.05 * (i % 3)), 1)  # menit, kecepatan bervariasi
        toll = round((base % 3 == 0) * 15000 * (i % 2), 0) + (12000 if i == 0 else 0)
        routes.append(Route(route_id=f"r{i+1}", distance_km=km,
                            base_duration_min=dur, toll_cost=float(toll),
                            geometry=f"polyline_{origin.get('name')}_{destination.get('name')}_{i}"))
    return routes


# --------------------------------------------------------------------------
# 2. get_weather  (BMKG / Open-Meteo)
# --------------------------------------------------------------------------
def get_weather(route: Route, departure_time: str, sample_every_km: float = 25.0) -> List[Dict[str, Any]]:
    """Mock deterministik suhu ambien + hujan per segmen. Ganti dengan Open-Meteo saat online."""
    try:
        hour = datetime.fromisoformat(departure_time).hour
    except Exception:
        hour = 12
    n = max(2, int(route.distance_km // sample_every_km))
    s = _seed(route.route_id, departure_time)
    segs = []
    for i in range(n):
        # suhu ambien tropis mengikuti jam (siang panas, malam sejuk)
        diurnal = 6.0 * (1 - abs((hour - 14) / 12.0))
        temp = round(26.0 + diurnal + ((s >> i) % 5) - 2, 1)
        precip = round(max(0.0, ((s >> (i + 3)) % 10) - 6) * 1.5, 1)
        segs.append({"segment_id": i, "ambient_temp_c": temp, "precip_mm": precip,
                     "ts": departure_time})
    return segs


# --------------------------------------------------------------------------
# 3. estimate_eta  (KODE, deterministik)
# --------------------------------------------------------------------------
def estimate_eta(base_duration_min: float, departure_time: str,
                 weather_segments: List[Dict]) -> Eta:
    try:
        hour = datetime.fromisoformat(departure_time).hour
    except Exception:
        hour = 12
    ft = config.f_time(hour)
    max_precip = max((s["precip_mm"] for s in weather_segments), default=0.0)
    fw = config.f_weather(max_precip)
    likely = base_duration_min * ft * fw
    return Eta(
        optimistic_min=round(base_duration_min * config.ETA_OPTIMISTIC_FACTOR, 1),
        likely_min=round(likely, 1),
        pessimistic_min=round(likely * config.ETA_PESSIMISTIC_FACTOR, 1),
        factors={"f_time": ft, "f_weather": fw},
    )


# --------------------------------------------------------------------------
# 4. compute_spoilage  (KODE, deterministik, INTI) — model RRS square-root
# --------------------------------------------------------------------------
def _resolve_commodity(name: str) -> str:
    key = (name or "").strip().lower().replace(" ", "_")
    if key in config.COMMODITY_PARAMS:
        return key
    for k, p in config.COMMODITY_PARAMS.items():
        if name and name.strip().lower() in [a.lower() for a in p["aliases"]]:
            return k
    return config.DEFAULT_COMMODITY


def rrs(T: float, T_ref: float, Tmin: float) -> float:
    """Relative Rate of Spoilage (square-root / Ratkowsky). RRS(T_ref) = 1."""
    if T <= Tmin:
        return 1e-6  # praktis membeku: laju ~ 0
    return ((T - Tmin) / (T_ref - Tmin)) ** 2


def shelf_life_hours(T: float, SL_ref_hours: float, T_ref: float, Tmin: float) -> float:
    return SL_ref_hours / rrs(T, T_ref, Tmin)


def compute_spoilage(commodity: str, initial_condition: str, cargo_mode: str,
                     weather_segments: List[Dict], eta_likely_min: float) -> Spoilage:
    key = _resolve_commodity(commodity)
    p = config.COMMODITY_PARAMS[key]
    assumptions = []
    if key != (commodity or "").strip().lower().replace(" ", "_"):
        assumptions.append(f"komoditas '{commodity}' dipetakan ke proxy '{key}'")

    segs = weather_segments or [{"ambient_temp_c": config.AMBIENT_DEFAULT_C}]
    n = len(segs)
    dt_hours = (eta_likely_min / 60.0) / n

    if cargo_mode == "reefer":
        temps = [config.REEFER_SETPOINT_C] * n
        assumptions.append(f"reefer: suhu kargo diasumsikan setpoint {config.REEFER_SETPOINT_C} C")
    else:
        temps = [s.get("ambient_temp_c", config.AMBIENT_DEFAULT_C) for s in segs]
        assumptions.append("non-reefer: suhu kargo mengikuti suhu ambien")

    damage = config.INITIAL_CONDITION_DAMAGE.get(initial_condition, 0.10)
    chill = 0.0
    for T in temps:
        sl = shelf_life_hours(T, p["SL_ref_hours"], p["T_ref"], p["Tmin"])
        damage += dt_hours / sl
        # Chilling injury / cold-induced sweetening (mis. kentang < 4 C)
        if p.get("chill_sensitive") and p.get("chill_threshold_c") is not None and T < p["chill_threshold_c"]:
            chill += config.CHILL_DAMAGE_K * (p["chill_threshold_c"] - T) * dt_hours

    if chill > 0:
        assumptions.append(
            f"chilling injury: {key} rusak di bawah {p['chill_threshold_c']} C — "
            f"jangan over-dinginkan (hindari reefer ekstrem)")
    damage += chill

    pct_fresh = round(max(0.0, 1.0 - damage) * 100.0, 1)
    return Spoilage(pct_fresh=pct_fresh, damage_fraction=round(damage, 4),
                    risk_level=config.risk_level(pct_fresh), assumptions=assumptions)


# --------------------------------------------------------------------------
# 5. rank_routes  (KODE, deterministik) — Pareto + weighted scoring
# --------------------------------------------------------------------------
def pareto_front(metrics: List[Dict]) -> List[str]:
    """Rute A didominasi jika ada B yang <= di SEMUA kriteria dan < di salah satunya."""
    keys = ("eta", "cost", "risk")
    keep = []
    for a in metrics:
        dominated = any(
            all(b[k] <= a[k] for k in keys) and any(b[k] < a[k] for k in keys)
            for b in metrics if b is not a
        )
        if not dominated:
            keep.append(a["route_id"])
    return keep


def rank_routes(routes_metrics: List[Dict], priority: str) -> Dict[str, Any]:
    w = config.PRIORITY_WEIGHTS.get(priority, config.PRIORITY_WEIGHTS["balanced"])
    keys = ("eta", "cost", "risk")
    # normalisasi min-max (lebih kecil = lebih baik) untuk skor gabungan
    ranges = {k: (min(m[k] for m in routes_metrics), max(m[k] for m in routes_metrics)) for k in keys}

    def norm(k, v):
        lo, hi = ranges[k]
        return 0.0 if hi == lo else (v - lo) / (hi - lo)

    scored = []
    for m in routes_metrics:
        score = sum(w[k] * norm(k, m[k]) for k in keys)  # lebih kecil = lebih baik
        scored.append({"route_id": m["route_id"], "score": round(score, 4)})
    scored.sort(key=lambda x: x["score"])
    front = pareto_front(routes_metrics)
    return {"pareto_front": front, "ranked": scored, "best_route_id": scored[0]["route_id"]}
