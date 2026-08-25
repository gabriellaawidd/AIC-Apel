


from datetime import timedelta
from typing import List
from contracts import RouteOption, RankedResult, TripRequest


PREFERENCE_WEIGHTS = {
    "fast":     (0.60, 0.20, 0.20),
    "cheap":    (0.20, 0.60, 0.20),
    "balanced": (0.34, 0.33, 0.33),
}


def _criteria(o: RouteOption):
    return (o.route.eta_hours_likely, o.cost.total_cost_rp, o.quality.spoil_risk)


def pareto_front(options: List[RouteOption]) -> List[RouteOption]:
    def dominated(a: RouteOption, b: RouteOption) -> bool:
        va, vb = _criteria(a), _criteria(b)
        return all(x <= y for x, y in zip(vb, va)) and any(x < y for x, y in zip(vb, va))

    return [a for a in options if not any(dominated(a, b) for b in options if b is not a)]


def _ranges(options: List[RouteOption]) -> list:
    cols = list(zip(*[_criteria(o) for o in options]))
    return [(min(c), max(c)) for c in cols]


def _score(o: RouteOption, weights, ranges) -> float:
    total = 0.0
    for val, (lo, hi), w in zip(_criteria(o), ranges, weights):
        norm = 0.0 if hi == lo else (val - lo) / (hi - lo)
        total += w * norm
    return total


def shelf_life_deadline_hours(o: RouteOption) -> float:


    return o.route.eta_hours_likely + o.quality.remaining_shelf_life_h


def _deadline_check(options: List[RouteOption], req: TripRequest) -> None:
    for o in options:
        meets_user_deadline = True
        if req.deadline:
            tiba = req.departure_time + timedelta(hours=o.route.eta_hours_pessimistic)
            meets_user_deadline = tiba <= req.deadline

        meets_shelf_life = o.route.eta_hours_pessimistic <= shelf_life_deadline_hours(o)

        o.meets_deadline = meets_user_deadline and meets_shelf_life


def rank_options(options: List[RouteOption], req: TripRequest) -> RankedResult:
    if not options:
        return RankedResult(best=None, pareto=[], all_options=[],
                            deadline_feasible=False, alert="Tidak ada rute kandidat.")

    weights = PREFERENCE_WEIGHTS.get(req.preference, PREFERENCE_WEIGHTS["balanced"])

    _deadline_check(options, req)

    ranges = _ranges(options)
    for o in options:
        o.score = _score(o, weights, ranges)

    all_sorted = sorted(options, key=lambda o: o.score)
    pareto = sorted(pareto_front(options), key=lambda o: o.score)

    feasible = [o for o in all_sorted if o.meets_deadline]
    deadline_feasible = bool(feasible)

    best = (feasible or all_sorted)[0]

    alert_parts: List[str] = []

    if req.deadline and not any(
        (req.departure_time + timedelta(hours=o.route.eta_hours_pessimistic)) <= req.deadline
        for o in options
    ):
        tercepat = min(options, key=lambda o: o.route.eta_hours_pessimistic)
        tiba = req.departure_time + timedelta(hours=tercepat.route.eta_hours_pessimistic)
        telat_jam = (tiba - req.deadline).total_seconds() / 3600.0
        alert_parts.append(
            f"Deadline pengiriman tidak terkejar oleh rute mana pun (skenario pesimis). "
            f"Rute tercepat ({tercepat.route.name}) tiba {tiba:%H:%M} — telat {telat_jam:.1f} jam. "
            f"Pertimbangkan ganti moda (reefer) atau majukan jam berangkat."
        )

    if not any(o.route.eta_hours_pessimistic <= shelf_life_deadline_hours(o) for o in options):
        tercepat = min(options, key=lambda o: o.route.eta_hours_pessimistic)
        sisa = shelf_life_deadline_hours(tercepat) - tercepat.route.eta_hours_pessimistic
        alert_parts.append(
            f"Skenario pesimis: barang berisiko sudah lewat umur simpan SEBELUM tiba "
            f"(sisa shelf-life M2 dari rute tercepat, {tercepat.route.name}, "
            f"{'kurang' if sisa < 0 else 'hanya tersisa'} {abs(sisa):.1f} jam dari margin aman). "
            f"Pertimbangkan reefer atau kondisi awal yang lebih segar."
        )

    if not alert_parts and req.deadline and best.quality.spoil_risk >= 0.7:
        alert_parts.append(
            f"Rute terbaik mengejar deadline, tapi risiko busuk tinggi "
            f"({best.quality.spoil_risk:.0%}). Pertimbangkan reefer."
        )

    alert = " | ".join(alert_parts) if alert_parts else None

    return RankedResult(
        best=best,
        pareto=pareto,
        all_options=all_sorted,
        deadline_feasible=deadline_feasible,
        alert=alert,
    )


if __name__ == "__main__":
    print("optimizer.py — jalankan demo_end_to_end.py untuk uji terintegrasi.")
