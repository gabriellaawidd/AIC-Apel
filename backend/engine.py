
import math
from typing import List, Dict

from models import (
    CommodityModel, resolve_commodity, INITIAL_CONDITION_MAP,
    GAS_CONSTANT, RISK_MIDPOINT, RISK_STEEPNESS, RISK_LEVEL_THRESHOLDS,
)


def to_kelvin(temp_c: float) -> float:
    return temp_c + 273.15


def _degradation_rate_rrs_square_root(temp_c: float, params: CommodityModel) -> float:
    tmin = params.tmin_c
    if temp_c <= tmin:
        return 0.0
    num = (temp_c - tmin) ** 2
    den = (params.ref_temp_c - tmin) ** 2
    return (num / den) / params.shelf_life_ref


def _degradation_rate_arrhenius(temp_c: float, params: CommodityModel) -> float:
    k_ref = 1.0 / params.shelf_life_ref
    temp_k = to_kelvin(temp_c)
    ref_k = to_kelvin(params.ref_temp_c)
    return k_ref * math.exp(
        -(params.activation_energy / GAS_CONSTANT) * (1.0 / temp_k - 1.0 / ref_k)
    )


def degradation_rate(temp_c: float, params: CommodityModel) -> float:
    if params.model_type == "rrs_square_root":
        return _degradation_rate_rrs_square_root(temp_c, params)
    if params.model_type == "arrhenius":
        return _degradation_rate_arrhenius(temp_c, params)
    raise ValueError(f"model_type tidak dikenal: {params.model_type}")


def spoilage_risk(spent_fraction: float) -> float:
    x = min(max(spent_fraction, 0.0), 1.0)
    return 1.0 / (1.0 + math.exp(-RISK_STEEPNESS * (x - RISK_MIDPOINT)))


def risk_level_from_score(risk_score: float) -> str:
    low, high = RISK_LEVEL_THRESHOLDS
    if risk_score < low:
        return "low"
    if risk_score < high:
        return "medium"
    return "high"


STATUS_MARGIN_PCT = 15.0


def freshness_status(pct_fresh: float, sellable_min_pct: float) -> str:
    if pct_fresh < sellable_min_pct:
        return "berisiko"
    if pct_fresh < sellable_min_pct + STATUS_MARGIN_PCT:
        return "waspada"
    return "aman"


def build_basis(params: CommodityModel) -> str:

    if params.model_type == "rrs_square_root":
        inti = (f"RRS square-root (Ratkowsky), Tmin={params.tmin_c:.1f}C, "
                f"SL_ref={params.shelf_life_ref:.0f}d@{params.ref_temp_c:.0f}C")
    else:
        inti = (f"Arrhenius, Ea={params.activation_energy/1000:.0f}kJ/mol, "
                f"SL_ref={params.shelf_life_ref:.0f}d@{params.ref_temp_c:.0f}C")

    basis = f"{inti}; mekanisme={params.mechanism}; sumber={params.sources[0].label}"
    if params.needs_approval:
        basis += " [METODE BELUM DISAHKAN GRUP]"
    return basis


_MECHANISM_HUMAN = {
    "mikrobial": "pembusukan oleh bakteri",
    "respirasi": "respirasi jaringan (sayur/umbi masih 'bernapas' setelah panen)",
}


def build_basis_human(params: CommodityModel) -> str:

    mek = _MECHANISM_HUMAN.get(params.mechanism, params.mechanism)
    hari = params.shelf_life_ref
    lama = f"{hari:.0f} hari" if hari >= 1 else f"{hari * 24:.0f} jam"
    return (
        f"Kesegaran {params.label.lower()} dihitung dari laju {mek}, "
        f"yang naik cepat mengikuti suhu. Acuannya: tahan sekitar {lama} "
        f"bila disimpan pada {params.ref_temp_c:.0f}°C."
    )


def compute_spoilage(komoditas: str,
                     segmen: List[Dict[str, float]],
                     kondisi_awal: str = "sangat_segar") -> dict:


    params = resolve_commodity(komoditas)
    if kondisi_awal not in INITIAL_CONDITION_MAP:
        raise ValueError(
            f"Kondisi awal tidak dikenal: {kondisi_awal!r}. "
            f"Tersedia: {sorted(INITIAL_CONDITION_MAP)}"
        )

    initial_quality = INITIAL_CONDITION_MAP[kondisi_awal]

    segment_trace = []
    used_so_far = 0.0
    elapsed_h = 0.0
    pct_prev = initial_quality * 100.0
    for s in segmen:
        dur = float(s["duration_hours"])
        temp = float(s["temp_c"])
        used_so_far += (dur / 24.0) * degradation_rate(temp, params)
        elapsed_h += dur

        sisa = max(0.0, initial_quality - used_so_far)
        spent = used_so_far / initial_quality if initial_quality > 0 else 1.0
        risk_seg = spoilage_risk(spent)
        segment_trace.append({
            "from_h": round(elapsed_h - dur, 2),
            "to_h": round(elapsed_h, 2),
            "temp_c": round(temp, 1),
            "pct_fresh_start": round(pct_prev, 1),
            "pct_fresh_end": round(sisa * 100.0, 1),
            "pct_drop": round(pct_prev - sisa * 100.0, 1),
            "spoil_risk_end": round(float(risk_seg), 3),
            "risk_level": risk_level_from_score(risk_seg),
            "status": freshness_status(sisa * 100.0, params.sellable_min_pct),
        })
        pct_prev = sisa * 100.0

    quality_used = used_so_far
    quality_remaining = max(0.0, initial_quality - quality_used)
    freshness_percent = quality_remaining * 100.0

    final_temp_c = segmen[-1]["temp_c"] if segmen else params.ref_temp_c
    final_rate = degradation_rate(final_temp_c, params)
    remaining_days = quality_remaining / final_rate if final_rate > 0 else float("inf")

    spent_fraction = quality_used / initial_quality if initial_quality > 0 else 1.0
    risk = spoilage_risk(spent_fraction)

    return {
        "commodity": params.label,
        "model_type_used": params.model_type,
        "mechanism": params.mechanism,
        "basis": build_basis(params),
        "basis_human": build_basis_human(params),
        "needs_approval": bool(params.needs_approval),
        "segments": segment_trace,
        "initial_quality_used": round(float(initial_quality), 3),
        "freshness_percent": round(float(freshness_percent), 1),
        "remaining_shelf_life_hours": round(float(remaining_days * 24.0), 2),
        "quality_used_fraction": round(float(quality_used), 3),
        "spent_fraction": round(float(spent_fraction), 3),
        "is_sellable": bool(freshness_percent >= params.sellable_min_pct),
        "sellable_min_pct": params.sellable_min_pct,
        "spoilage_risk": round(float(risk), 3),
        "risk_level": risk_level_from_score(risk),
        "status": freshness_status(freshness_percent, params.sellable_min_pct),
        "status_thresholds": {
            "berisiko_di_bawah": params.sellable_min_pct,
            "waspada_di_bawah": params.sellable_min_pct + STATUS_MARGIN_PCT,
        },
    }
