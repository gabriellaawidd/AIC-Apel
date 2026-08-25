


from typing import List, Dict

from contracts import TripRequest, TempProfile, QualityResult
from engine import compute_spoilage


def profile_to_segments(profile: TempProfile) -> List[Dict[str, float]]:


    n = len(profile.times_h)
    if n != len(profile.temps_c):
        raise ValueError(
            f"TempProfile rusak: times_h={n} titik tapi temps_c={len(profile.temps_c)}"
        )
    if n < 2:
        return []

    return [
        {
            "duration_hours": profile.times_h[i + 1] - profile.times_h[i],
            "temp_c": (profile.temps_c[i] + profile.temps_c[i + 1]) / 2.0,
        }
        for i in range(n - 1)
    ]


def predict_quality(req: TripRequest, profile: TempProfile) -> QualityResult:

    segmen = profile_to_segments(profile)
    hasil = compute_spoilage(req.commodity, segmen, kondisi_awal=req.initial_condition)

    basis = f"{hasil['basis']}; suhu={profile.source}"

    suhu_human = {
        "reefer_setpoint": "suhu kargo memakai setpoint truk berpendingin",
        "ambient_openmeteo": "suhu kargo mengikuti suhu udara sepanjang rute (prakiraan Open-Meteo)",
        "ambient_bmkg": "suhu kargo mengikuti suhu udara sepanjang rute (BMKG)",
    }.get(profile.source, f"sumber suhu: {profile.source}")
    basis_human = f"{hasil['basis_human']} Untuk perjalanan ini, {suhu_human}."

    return QualityResult(
        route_id=profile.route_id,
        pct_fresh=hasil["freshness_percent"],
        remaining_shelf_life_h=hasil["remaining_shelf_life_hours"],
        spoil_risk=hasil["spoilage_risk"],
        is_sellable=hasil["is_sellable"],
        basis=basis,
        basis_human=basis_human,
        risk_level=hasil["risk_level"],
        status=hasil["status"],
        status_thresholds=hasil["status_thresholds"],
        segments=hasil["segments"],
    )
