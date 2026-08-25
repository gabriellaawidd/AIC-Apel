


from dataclasses import dataclass
from contracts import RouteCandidate, CostResult
from toll_table import TollTable, default_table
from typing import Optional

@dataclass
class CostConfig:
    golongan: str = "II_III"
    km_per_liter: float = 7.0
    harga_bbm_per_liter: int = 6_800

    def basis(self) -> str:
        gol_label = {"I": "Gol I", "II_III": "Gol II/III", "IV_V": "Gol IV/V"}[self.golongan]
        return (f"{gol_label}; {self.km_per_liter} km/L; "
                f"Solar Rp{self.harga_bbm_per_liter:,}/L (subsidi)")


_CONFIG = CostConfig()
_TABLE: Optional[TollTable] = None


def set_config(cfg: CostConfig) -> None:
    global _CONFIG
    _CONFIG = cfg


def get_config() -> CostConfig:
    return _CONFIG


def _table() -> TollTable:
    global _TABLE
    if _TABLE is None:
        _TABLE = default_table()
    return _TABLE


def estimasi_biaya_bbm(distance_km: float, cfg: CostConfig = None) -> int:
    cfg = cfg or _CONFIG
    liter = distance_km / cfg.km_per_liter
    return round(liter * cfg.harga_bbm_per_liter)


def evaluate_cost(route: RouteCandidate) -> CostResult:


    cfg = _CONFIG
    breakdown = []

    if route.uses_toll:
        ruas_km = getattr(route, "ruas_km", None) or {}
        exact_gates = getattr(route, "exact_gates", None) or {}
        breakdown = _table().breakdown_for_usage(
            ruas_km, golongan=cfg.golongan, exact_gates=exact_gates)
        toll = float(sum(b["tarif_rp"] for b in breakdown))
        if not breakdown:
            route.assumptions["toll_unmatched"] = 1.0
    else:
        toll = 0.0

    liter = route.distance_km / cfg.km_per_liter
    fuel = float(round(liter * cfg.harga_bbm_per_liter))
    return CostResult(
        route_id=route.route_id,
        toll_cost_rp=toll,
        fuel_cost_rp=fuel,
        total_cost_rp=toll + fuel,
        toll_breakdown=breakdown,
        fuel_liters=round(liter, 1),
        cost_basis=cfg.basis(),
    )


if __name__ == "__main__":
    r = RouteCandidate(
        route_id="jkt-bdg-tol", name="Via Cipularang", distance_km=151.0,
        eta_hours_likely=2.6, eta_hours_optimistic=2.3, eta_hours_pessimistic=3.4,
        uses_toll=True,
        toll_segments=[
            "Jakarta-Cikampek dan Jakarta -Cikampek II Elevated ::Cikampek (Kalihurip)::Cikampek",
            "Cikampek-Padalarang::SS Dawuan::SS Padalarang",
        ],
    )
    for gol in ("I", "II_III", "IV_V"):
        set_config(CostConfig(golongan=gol))
        c = evaluate_cost(r)
        print(f"gol {gol:<6} tol=Rp{c.toll_cost_rp:>10,.0f} | "
              f"bbm=Rp{c.fuel_cost_rp:>10,.0f} | total=Rp{c.total_cost_rp:>10,.0f}")
    print("basis:", get_config().basis())
