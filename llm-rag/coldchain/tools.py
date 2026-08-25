from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

_BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def backend_available() -> bool:
    try:
        import pipeline  
        return True
    except Exception:
        return False


def plan_trip(
    origin: Dict[str, Any],
    destination: Dict[str, Any],
    commodity: str,
    departure_time: str,
    vehicle: str = "non_reefer",
    preference: str = "balanced",
    initial_condition: str = "segar",
    deadline: Optional[str] = None,
    golongan: str = "II_III",
) -> Dict[str, Any]:
    import dashboard_export
    import pipeline
    from contracts import TripRequest

    pipeline.configure_cost(golongan=golongan)

    req = TripRequest(
        origin=(float(origin["lon"]), float(origin["lat"])),
        destination=(float(destination["lon"]), float(destination["lat"])),
        commodity=commodity,
        departure_time=datetime.fromisoformat(departure_time),
        vehicle=vehicle,
        preference=preference,
        deadline=datetime.fromisoformat(deadline) if deadline else None,
        initial_condition=initial_condition,
    )
    result = pipeline.run_pipeline(req)
    payload = dashboard_export.to_dashboard_payload(result, req=req)

    by_id = {o.route.route_id: o for o in result.all_options}
    for opt in payload.get("options", []):
        src = by_id.get(opt["route_id"])
        if src is not None:
            opt["assumptions"] = src.route.assumptions
            opt["geometry"] = src.route.geometry
            opt["toll_segments"] = src.route.toll_segments

    payload["request_echo"] = {
        "origin": origin,
        "destination": destination,
        "commodity": commodity,
        "vehicle": vehicle,
        "preference": preference,
        "departure_time": departure_time,
        "deadline": deadline,
        "initial_condition": initial_condition,
        "golongan": golongan,
    }
    return payload


def geocode_place(name: str) -> Optional[Dict[str, Any]]:

    try:
        import geocode as _geo
        hits = _geo.search(name, limit=1)
        if hits:
            h = hits[0]
            return {"name": h["label"], "lon": h["lon"], "lat": h["lat"]}
    except Exception:
        pass

    try:
        from locations import LOCATIONS
        key = (name or "").strip().lower()
        if key in LOCATIONS:
            loc = LOCATIONS[key]
            return {"name": loc["label"], "lon": loc["lon"], "lat": loc["lat"]}
        for k, loc in LOCATIONS.items():
            if key in loc["label"].lower():
                return {"name": loc["label"], "lon": loc["lon"], "lat": loc["lat"]}
    except Exception:
        pass
    return None
