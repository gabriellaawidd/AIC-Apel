import json
from typing import Any, Dict, List, Optional, Tuple

from contracts import RankedResult, RouteOption
from optimizer import shelf_life_deadline_hours


def _criteria(o: RouteOption) -> Dict[str, float]:
    return {
        "eta_hours": o.route.eta_hours_likely,
        "cost_rp": o.cost.total_cost_rp,
        "risk": o.quality.spoil_risk,
    }


_CRITERIA_LABEL = {"eta_hours": "waktu tempuh", "cost_rp": "biaya", "risk": "risiko busuk"}


def _dominated_by(a: RouteOption, options: List[RouteOption]) -> Tuple[Optional[str], Optional[str]]:
    ca = _criteria(a)
    for b in options:
        if b is a:
            continue
        cb = _criteria(b)
        le_all = all(cb[k] <= ca[k] for k in ca)
        lt_any = any(cb[k] < ca[k] for k in ca)
        if le_all and lt_any:
            alasan = [_CRITERIA_LABEL[k] for k in ca if cb[k] < ca[k]]
            return b.route.route_id, f"{b.route.name} lebih baik di: {', '.join(alasan)}"
    return None, None


def route_option_to_dict(
    o: RouteOption,
    *,
    is_pareto: bool,
    is_best: bool,
    dominated_by: Optional[str],
    dominated_reason: Optional[str],
) -> Dict[str, Any]:
    return {
        "route_id": o.route.route_id,
        "name": o.route.name,
        "summary": o.route.summary,
        "distance_km": o.route.distance_km,
        "uses_toll": o.route.uses_toll,
        "avg_speed_kmh": o.route.avg_speed_kmh,
        "toll_km": o.route.toll_km,
        "non_toll_km": o.route.non_toll_km,
        "toll_road_names": o.route.toll_road_names,
        "eta_hours": {
            "optimistic": o.route.eta_hours_optimistic,
            "likely": o.route.eta_hours_likely,
            "pessimistic": o.route.eta_hours_pessimistic,
        },
        "cost_rp": {
            "toll": o.cost.toll_cost_rp,
            "fuel": o.cost.fuel_cost_rp,
            "total": o.cost.total_cost_rp,
            "toll_breakdown": o.cost.toll_breakdown,
            "fuel_liters": o.cost.fuel_liters,
            "basis": o.cost.cost_basis,
        },
        "quality": {
            "pct_fresh_on_arrival": o.quality.pct_fresh,
            "remaining_shelf_life_h_after_arrival": o.quality.remaining_shelf_life_h,
            "spoil_risk": o.quality.spoil_risk,
            "is_sellable": o.quality.is_sellable,
            "basis": o.quality.basis,
            "basis_human": o.quality.basis_human,
            "risk_level": o.quality.risk_level,
            "status": o.quality.status,
            "status_thresholds": o.quality.status_thresholds,
            "segments": o.quality.segments,
        },
        "score": round(o.score, 4) if o.score is not None else None,
        "is_best": is_best,
        "is_pareto_optimal": is_pareto,
        "dominated_by_route_id": dominated_by,
        "dominated_reason": dominated_reason,
        "meets_deadline": o.meets_deadline,
        "shelf_life_deadline_h_since_departure": round(shelf_life_deadline_hours(o), 2),
    }


from optimizer import PREFERENCE_WEIGHTS

_PREF_EXPLAIN = {
    "fast": "Waktu tempuh diberi bobot terbesar. Yang dibandingkan adalah "
            "perkiraan jam tempuh (skenario wajar) — makin sedikit jam, makin "
            "tinggi kecepatan rata-rata (km/jam) rute itu.",
    "cheap": "Biaya total (tarif tol + BBM) diberi bobot terbesar.",
    "balanced": "Waktu tempuh, biaya, dan risiko busuk diberi bobot hampir sama rata.",
}


def scoring_explanation(preference: str) -> Dict[str, Any]:
    w = PREFERENCE_WEIGHTS.get(preference, PREFERENCE_WEIGHTS["balanced"])
    return {
        "preference": preference,
        "weights": {"eta": w[0], "cost": w[1], "risk": w[2]},
        "explanation": _PREF_EXPLAIN.get(preference, _PREF_EXPLAIN["balanced"]),
        "criteria": [
            {"key": "eta", "label": "Waktu tempuh",
             "unit": "jam (skenario wajar)", "weight": w[0]},
            {"key": "cost", "label": "Biaya total",
             "unit": "Rupiah (tol + BBM)", "weight": w[1]},
            {"key": "risk", "label": "Risiko busuk",
             "unit": "0–1 (dari model kesegaran M2)", "weight": w[2]},
        ],
        "note": "Skor gabungan: makin kecil makin baik. Tiap kriteria "
                "dinormalisasi min-max lebih dulu supaya Rupiah tidak "
                "mendominasi jam hanya karena skalanya lebih besar.",
    }


def to_dashboard_payload(result: RankedResult, req=None) -> Dict[str, Any]:

    scoring = scoring_explanation(getattr(req, "preference", "balanced")) if req else None

    if result.best is None:
        return {
            "best_route_id": None,
            "deadline_feasible": False,
            "alert": result.alert,
            "pareto_front_route_ids": [],
            "options": [],
            "scoring": scoring,
        }

    pareto_ids = {o.route.route_id for o in result.pareto}
    options_payload = []
    for o in result.all_options:
        is_pareto = o.route.route_id in pareto_ids
        dom_id, dom_reason = (
            (None, None) if is_pareto else _dominated_by(o, result.all_options)
        )
        options_payload.append(
            route_option_to_dict(
                o,
                is_pareto=is_pareto,
                is_best=(o is result.best),
                dominated_by=dom_id,
                dominated_reason=dom_reason,
            )
        )

    return {
        "best_route_id": result.best.route.route_id,
        "deadline_feasible": result.deadline_feasible,
        "alert": result.alert,
        "pareto_front_route_ids": sorted(pareto_ids),
        "options": options_payload,
        "scoring": scoring,
    }


if __name__ == "__main__":
    from datetime import datetime
    import pipeline
    from contracts import TripRequest

    pipeline.configure_cost(golongan="II_III")
    req = TripRequest(
        origin=(106.8272, -6.1751), destination=(107.6098, -6.9147),
        commodity="ikan_segar", departure_time=datetime(2026, 8, 20, 8, 0),
        vehicle="non_reefer", preference="balanced",
        deadline=datetime(2026, 8, 20, 10, 0),
        initial_condition="segar",
    )
    result = pipeline.run_pipeline(req)
    payload = to_dashboard_payload(result)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
