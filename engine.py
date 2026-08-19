# engine.py
import numpy as np
from typing import List, Dict

from models import (
    CommodityModel, COMMODITY_DB, INITIAL_CONDITION_MAP, 
    GAS_CONSTANT, RISK_LEVEL_THRESHOLDS, RISK_MIDPOINT_USED, RISK_STEEPNESS
)

def to_kelvin(temp_c: float) -> float:
    return temp_c + 273.15

def _degradation_rate_arrhenius(temp_c: float, params: CommodityModel) -> float:
    k_ref = 1.0 / params.shelf_life_ref
    temp_k = to_kelvin(temp_c)
    ref_k = to_kelvin(params.ref_temp_c)
    return k_ref * np.exp(-(params.activation_energy / GAS_CONSTANT) * (1.0 / temp_k - 1.0 / ref_k))

def _degradation_rate_rrs_tropical(temp_c: float, params: CommodityModel) -> float:
    rrs = np.exp(params.rrs_coefficient * (temp_c - params.ref_temp_c))
    return rrs / params.shelf_life_ref

def degradation_rate(temp_c: float, params: CommodityModel) -> float:
    if params.model_type == "rrs_tropical":
        return _degradation_rate_rrs_tropical(temp_c, params)
    elif params.model_type == "arrhenius":
        return _degradation_rate_arrhenius(temp_c, params)
    raise ValueError(f"model_type tidak dikenal: {params.model_type}")

def spoilage_risk(quality_used: float) -> float:
    return 1.0 / (1.0 + np.exp(-RISK_STEEPNESS * (quality_used - RISK_MIDPOINT_USED)))

def risk_level_from_score(risk_score: float) -> str:
    low, high = RISK_LEVEL_THRESHOLDS
    if risk_score < low: return "low"
    if risk_score < high: return "medium"
    return "high"

def compute_spoilage(komoditas: str, segmen: List[Dict[str, float]], kondisi_awal: str = "sangat_segar") -> dict:
    if komoditas not in COMMODITY_DB:
        raise ValueError(f"Komoditas tidak dikenal: {komoditas}")
    if kondisi_awal not in INITIAL_CONDITION_MAP:
        raise ValueError(f"Kondisi awal tidak dikenal: {kondisi_awal}")

    params = COMMODITY_DB[komoditas]
    temperature_profile = [(s["duration_hours"], s["temp_c"]) for s in segmen]
    initial_quality = INITIAL_CONDITION_MAP[kondisi_awal]

    quality_used = sum(
        (duration_hours / 24.0) * degradation_rate(temp_c, params)
        for duration_hours, temp_c in temperature_profile
    )

    quality_remaining = max(0.0, initial_quality - quality_used)
    freshness_percent = quality_remaining * 100.0

    final_temp_c = temperature_profile[-1][1] if temperature_profile else params.ref_temp_c
    final_rate = degradation_rate(final_temp_c, params)
    remaining_shelf_life_days = quality_remaining / final_rate if final_rate > 0 else float("inf")

    risk = spoilage_risk(1.0 - quality_remaining)

    return {
        "commodity": params.label,
        "model_type_used": params.model_type,
        "initial_quality_used": round(float(initial_quality), 3),
        "freshness_percent": round(freshness_percent, 1),
        "remaining_shelf_life_days": round(remaining_shelf_life_days, 2),
        "quality_used_fraction": round(float(quality_used), 3),
        "is_sellable": quality_remaining > 0.0,
        "spoilage_risk": round(float(risk), 3),
        "risk_level": risk_level_from_score(risk),
    }