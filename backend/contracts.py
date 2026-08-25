from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Literal

Vehicle = Literal["reefer", "non_reefer"]
Preference = Literal["fast", "cheap", "balanced"]
InitialCondition = Literal["sangat_segar", "segar", "kurang_segar"]


@dataclass
class TripRequest:
    origin: tuple
    destination: tuple
    commodity: str
    departure_time: datetime
    vehicle: Vehicle = "non_reefer"
    preference: Preference = "balanced"
    deadline: Optional[datetime] = None
    initial_condition: InitialCondition = "segar"


@dataclass
class RouteCandidate:
    route_id: str
    name: str
    distance_km: float
    eta_hours_likely: float
    eta_hours_optimistic: float
    eta_hours_pessimistic: float
    uses_toll: bool = False
    toll_segments: List[str] = field(default_factory=list)
    geometry: List[list] = field(default_factory=list)
    assumptions: Dict[str, float] = field(default_factory=dict)

    summary: str = ""
    avg_speed_kmh: float = 0.0
    toll_road_names: List[str] = field(default_factory=list)
    toll_km: float = 0.0
    non_toll_km: float = 0.0


@dataclass
class TempProfile:
    route_id: str
    times_h: List[float]
    temps_c: List[float]
    source: str


@dataclass
class QualityResult:
    route_id: str
    pct_fresh: float
    remaining_shelf_life_h: float
    spoil_risk: float
    is_sellable: bool
    basis: str

    basis_human: str = ""
    risk_level: str = ""
    status: str = ""
    status_thresholds: dict = field(default_factory=dict)
    segments: List[dict] = field(default_factory=list)


@dataclass
class CostResult:
    route_id: str
    toll_cost_rp: float
    fuel_cost_rp: float
    total_cost_rp: float

    toll_breakdown: List[dict] = field(default_factory=list)
    fuel_liters: float = 0.0
    cost_basis: str = ""


@dataclass
class RouteOption:
    route: RouteCandidate
    quality: QualityResult
    cost: CostResult
    score: Optional[float] = None
    meets_deadline: bool = True


@dataclass
class RankedResult:
    best: Optional[RouteOption]
    pareto: List[RouteOption]
    all_options: List[RouteOption]
    deadline_feasible: bool
    alert: Optional[str] = None


def get_route_candidates(req: TripRequest) -> List[RouteCandidate]:
    raise NotImplementedError


def build_temp_profile(route: RouteCandidate, req: TripRequest) -> TempProfile:
    raise NotImplementedError


def predict_quality(req: TripRequest, profile: TempProfile) -> QualityResult:
    raise NotImplementedError


def evaluate_cost(route: RouteCandidate) -> CostResult:
    raise NotImplementedError


def rank_options(options: List[RouteOption], req: TripRequest) -> RankedResult:
    raise NotImplementedError


def stub_get_route_candidates(req: TripRequest) -> List[RouteCandidate]:
    return [
        RouteCandidate("r1", "Via Tol (cepat)", 150.0, 3.2, 2.9, 4.0,
                       uses_toll=True, toll_segments=["cipularang"],
                       assumptions={"f_time": 1.15, "f_weather": 1.0}),
        RouteCandidate("r2", "Non-tol (hemat)", 168.0, 5.1, 4.6, 6.4,
                       uses_toll=False, assumptions={"f_time": 1.25, "f_weather": 1.1}),
    ]


def stub_build_temp_profile(route: RouteCandidate, req: TripRequest) -> TempProfile:
    n = 6
    h = route.eta_hours_likely
    times = [h * i / (n - 1) for i in range(n)]
    if req.vehicle == "reefer":
        return TempProfile(route.route_id, times, [4.0] * n, "reefer_setpoint")
    return TempProfile(route.route_id, times, [30.0] * n, "ambient_openmeteo")


def stub_predict_quality(req: TripRequest, profile: TempProfile) -> QualityResult:
    avg_t = sum(profile.temps_c) / len(profile.temps_c)
    dur = profile.times_h[-1]
    loss = min(100.0, dur * max(0.0, avg_t + 10) * 0.35)
    pct = max(0.0, 100.0 - loss)
    return QualityResult(profile.route_id, round(pct, 1), round(dur * 2, 1),
                         round(1 - pct / 100, 3), pct >= 60, "STUB — belum RRS")


def stub_evaluate_cost(route: RouteCandidate) -> CostResult:
    toll = 42500.0 if route.uses_toll else 0.0
    fuel = route.distance_km * 1500.0
    return CostResult(route.route_id, toll, fuel, toll + fuel)


def stub_rank_options(options: List[RouteOption], req: TripRequest) -> RankedResult:
    w = {"fast": (0.6, 0.2, 0.2), "cheap": (0.2, 0.6, 0.2),
         "balanced": (0.35, 0.25, 0.40)}[req.preference]

    def norm(vals):
        lo, hi = min(vals), max(vals)
        return [0.0] * len(vals) if hi == lo else [(v - lo) / (hi - lo) for v in vals]

    t = norm([o.route.eta_hours_likely for o in options])
    c = norm([o.cost.total_cost_rp for o in options])
    r = norm([o.quality.spoil_risk for o in options])
    for i, o in enumerate(options):
        o.score = w[0] * t[i] + w[1] * c[i] + w[2] * r[i]
        if req.deadline:
            arrive = req.departure_time + timedelta(hours=o.route.eta_hours_pessimistic)
            o.meets_deadline = arrive <= req.deadline

    ranked = sorted(options, key=lambda o: o.score)
    feasible = [o for o in ranked if o.meets_deadline]
    def key(o): return (o.route.eta_hours_likely, o.cost.total_cost_rp, o.quality.spoil_risk)
    pareto = [a for a in ranked if not any(
        all(x <= y for x, y in zip(key(b), key(a))) and any(x < y for x, y in zip(key(b), key(a)))
        for b in ranked if b is not a)]

    return RankedResult(
        best=(feasible or ranked)[0],
        pareto=pareto,
        all_options=ranked,
        deadline_feasible=bool(feasible),
        alert=None if feasible else "Deadline tidak terkejar oleh rute manapun — pertimbangkan ganti moda.",
    )


IMPL = {
    "get_route_candidates": stub_get_route_candidates,
    "build_temp_profile":   stub_build_temp_profile,
    "predict_quality":      stub_predict_quality,
    "evaluate_cost":        stub_evaluate_cost,
    "rank_options":         stub_rank_options,
}


def run_pipeline(req: TripRequest) -> RankedResult:
    routes = IMPL["get_route_candidates"](req)
    options = []
    for rt in routes:
        prof = IMPL["build_temp_profile"](rt, req)
        qual = IMPL["predict_quality"](req, prof)
        cost = IMPL["evaluate_cost"](rt)
        options.append(RouteOption(route=rt, quality=qual, cost=cost))
    return IMPL["rank_options"](options, req)


if __name__ == "__main__":
    req = TripRequest(
        origin=(106.8272, -6.1751), destination=(107.6098, -6.9147),
        commodity="ikan_segar", departure_time=datetime(2026, 8, 10, 6, 0),
        vehicle="non_reefer", preference="balanced",
        deadline=datetime(2026, 8, 10, 12, 0),
    )
    res = run_pipeline(req)
    print("=== SMOKE TEST PIPELINE (stub) ===")
    for o in res.all_options:
        print(f"[{o.route.route_id}] {o.route.name:<22} "
              f"ETA {o.route.eta_hours_likely:>4.1f}j | "
              f"Rp{o.cost.total_cost_rp:>10,.0f} | "
              f"fresh {o.quality.pct_fresh:>5.1f}% | "
              f"skor {o.score:.3f} | deadline_ok={o.meets_deadline}")
    print(f"\nTERBAIK : {res.best.route.name}")
    print(f"PARETO  : {[o.route.route_id for o in res.pareto]}")
    if res.alert:
        print(f"ALERT   : {res.alert}")
