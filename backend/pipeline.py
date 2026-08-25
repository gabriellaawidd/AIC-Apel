


import contracts as C

from routing import get_route_candidates
from temp_profile import build_temp_profile
from quality import predict_quality
from cost import evaluate_cost, set_config, CostConfig
from optimizer import rank_options

C.IMPL["get_route_candidates"] = get_route_candidates
C.IMPL["build_temp_profile"] = build_temp_profile
C.IMPL["predict_quality"] = predict_quality
C.IMPL["evaluate_cost"] = evaluate_cost
C.IMPL["rank_options"] = rank_options

run_pipeline = C.run_pipeline
TripRequest = C.TripRequest
RankedResult = C.RankedResult
RouteOption = C.RouteOption


def configure_cost(golongan: str = "II_III", km_per_liter: float = 7.0,
                   harga_bbm_per_liter: int = 6_800) -> None:
    set_config(CostConfig(golongan=golongan, km_per_liter=km_per_liter,
                          harga_bbm_per_liter=harga_bbm_per_liter))


def run(req: C.TripRequest, cost_cfg: CostConfig = None) -> C.RankedResult:
    if cost_cfg is not None:
        set_config(cost_cfg)
    return C.run_pipeline(req)


def print_result(res: C.RankedResult) -> None:
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
