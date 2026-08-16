"""
pipeline.py — Titik masuk backend Cold Chain AI
================================================
Inilah satu-satunya modul yang perlu diimpor UI/agent (CATH).

Meng-`import pipeline` otomatis memasang implementasi asli keempat modul
ke IMPL kontrak (mengganti stub), lalu mengekspos `run_pipeline`.

Pakai dari kode CATH:

    import pipeline
    from contracts import TripRequest
    from datetime import datetime

    req = TripRequest(
        origin=(106.8272, -6.1751),      # (lon, lat) Jakarta
        destination=(107.6098, -6.9147), # (lon, lat) Bandung
        commodity="ikan_segar",          # ikan_segar | bayam | kentang
        departure_time=datetime(2026, 8, 20, 8, 0),
        vehicle="non_reefer",            # non_reefer | reefer
        preference="balanced",           # fast | cheap | balanced
        deadline=datetime(2026, 8, 20, 13, 0),
        initial_condition="segar",       # sangat_segar | segar | kurang_segar
    )
    result = pipeline.run_pipeline(req)   # -> contracts.RankedResult

`RankedResult` berisi: best, pareto[], all_options[], deadline_feasible, alert.
Tiap RouteOption punya .route (RouteCandidate), .quality (QualityResult),
.cost (CostResult), .score, .meets_deadline — semuanya dataclass yg mudah
di-serialize ke JSON (dataclasses.asdict).
"""

import contracts as C

# --- M1 RIO ---
from routing import get_route_candidates
from temp_profile import build_temp_profile
# --- M2 GAB ---
from quality import predict_quality
# --- M3 DAVIN ---
from cost import evaluate_cost, set_config, CostConfig
from optimizer import rank_options

# Pasang implementasi asli ke kontrak (ganti seluruh stub) saat modul diimpor.
C.IMPL["get_route_candidates"] = get_route_candidates
C.IMPL["build_temp_profile"] = build_temp_profile
C.IMPL["predict_quality"] = predict_quality
C.IMPL["evaluate_cost"] = evaluate_cost
C.IMPL["rank_options"] = rank_options

# Re-export supaya CATH cukup `from pipeline import ...`
run_pipeline = C.run_pipeline
TripRequest = C.TripRequest
RankedResult = C.RankedResult
RouteOption = C.RouteOption


def configure_cost(golongan: str = "II_III", km_per_liter: float = 7.0,
                   harga_bbm_per_liter: int = 6_800) -> None:
    """Setel parameter biaya statis skenario (golongan tol, konsumsi & harga BBM)."""
    set_config(CostConfig(golongan=golongan, km_per_liter=km_per_liter,
                          harga_bbm_per_liter=harga_bbm_per_liter))


def run(req: C.TripRequest, cost_cfg: CostConfig = None) -> C.RankedResult:
    """Bungkus run_pipeline + setel config biaya opsional (dipakai scenarios.py)."""
    if cost_cfg is not None:
        set_config(cost_cfg)
    return C.run_pipeline(req)


def print_result(res: C.RankedResult) -> None:
    """Cetak ringkas hasil ke terminal (untuk demo/CLI)."""
    for o in res.all_options:
        mark = "  <- TERBAIK" if o is res.best else ""
        dl = "" if o.meets_deadline else "  [LEWAT DEADLINE]"
        print(f"  [{o.route.route_id:<7}] {o.route.name:<32} "
              f"ETA {o.route.eta_hours_likely:>4.1f}j | fresh {o.quality.pct_fresh:>5.1f}% | "
              f"Rp{o.cost.total_cost_rp:>10,.0f} | risk {o.quality.spoil_risk:.2f} | "
              f"skor {o.score:.3f}{dl}{mark}")
    if res.alert:
        print(f"\n  ALERT: {res.alert}")
    if res.best:
        print(f"  basis M2: {res.best.quality.basis}")
