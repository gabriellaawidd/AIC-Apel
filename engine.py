"""
engine.py — Mesin perhitungan spoilage  (owner: GAB / M2)
=========================================================
Model RRS square-root (Ratkowsky) + Arrhenius per mekanisme pembusukan.
Dipakai lewat quality.predict_quality() sesuai contracts.py.
"""

import math
from typing import List, Dict

from models import (
    CommodityModel, resolve_commodity, INITIAL_CONDITION_MAP,
    GAS_CONSTANT, RISK_MIDPOINT, RISK_STEEPNESS, RISK_LEVEL_THRESHOLDS,
)


def to_kelvin(temp_c: float) -> float:
    return temp_c + 273.15


# ============================================================
# Laju pembusukan — RRS square-root (mikrobial) vs Arrhenius (respirasi)
# RRS: sqrt(k) = b(T - Tmin)  ->  k ∝ (T - Tmin)^2, dikalibrasi lewat SL_ref.
# ============================================================
def _degradation_rate_rrs_square_root(temp_c: float, params: CommodityModel) -> float:
    """Laju kerusakan per hari, model akar-kuadrat (pembusukan mikrobial)."""
    tmin = params.tmin_c
    if temp_c <= tmin:
        return 0.0                      # di bawah Tmin: pertumbuhan mikroba berhenti
    num = (temp_c - tmin) ** 2
    den = (params.ref_temp_c - tmin) ** 2
    return (num / den) / params.shelf_life_ref


def _degradation_rate_arrhenius(temp_c: float, params: CommodityModel) -> float:
    """Laju kerusakan per hari, model Arrhenius (pembusukan respirasi)."""
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


# ============================================================
# Kurva risiko — argumen = fraksi umur simpan terpakai (0 utuh .. 1 habis),
# midpoint 0,5 -> risiko 0,018 saat berangkat, 0,982 saat habis.
# ============================================================
def spoilage_risk(spent_fraction: float) -> float:
    """spent_fraction = quality_used / initial_quality."""
    x = min(max(spent_fraction, 0.0), 1.0)
    return 1.0 / (1.0 + math.exp(-RISK_STEEPNESS * (x - RISK_MIDPOINT)))


def risk_level_from_score(risk_score: float) -> str:
    low, high = RISK_LEVEL_THRESHOLDS
    if risk_score < low:
        return "low"
    if risk_score < high:
        return "medium"
    return "high"


def build_basis(params: CommodityModel) -> str:
    """String `basis` yang dituntut QualityResult — jujur soal metode & sumber."""
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


def compute_spoilage(komoditas: str,
                     segmen: List[Dict[str, float]],
                     kondisi_awal: str = "sangat_segar") -> dict:
    """Akumulasi kerusakan aditif sepanjang perjalanan.

    segmen: [{"duration_hours": float, "temp_c": float}, ...]
    """
    params = resolve_commodity(komoditas)
    if kondisi_awal not in INITIAL_CONDITION_MAP:
        raise ValueError(
            f"Kondisi awal tidak dikenal: {kondisi_awal!r}. "
            f"Tersedia: {sorted(INITIAL_CONDITION_MAP)}"
        )

    initial_quality = INITIAL_CONDITION_MAP[kondisi_awal]

    quality_used = sum(
        (s["duration_hours"] / 24.0) * degradation_rate(s["temp_c"], params)
        for s in segmen
    )

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
        "initial_quality_used": round(float(initial_quality), 3),
        "freshness_percent": round(float(freshness_percent), 1),
        "remaining_shelf_life_hours": round(float(remaining_days * 24.0), 2),
        "quality_used_fraction": round(float(quality_used), 3),
        "spent_fraction": round(float(spent_fraction), 3),
        "is_sellable": bool(freshness_percent >= params.sellable_min_pct),
        "sellable_min_pct": params.sellable_min_pct,
        "spoilage_risk": round(float(risk), 3),
        "risk_level": risk_level_from_score(risk),
    }
