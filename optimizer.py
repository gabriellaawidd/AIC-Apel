"""
optimizer.py — Pareto front + weighted scoring + alert deadline  (owner: DAVIN)
================================================================================
PATCH 2026-08-16 (usulan QA — belum di-merge, silakan review).

Menggantikan pareto_optimizer.py lama. Perubahan terhadap versi DAVIN:
  [1] rank_options(options, req) -> RankedResult   (SESUAI contracts.py)
  [2] ALERT DEADLINE ditambahkan                    (deliverable #3 yg hilang)
  [3] kelas internal diberi nama _ScoredRoute       (dulu `RouteCandidate`,
      bertabrakan nama dgn contracts.RouteCandidate — bug diam saat integrasi)
  [4] all_options TERISI                            (dulu rute non-Pareto dibuang;
      CATH butuh ini untuk menjelaskan kenapa pemenang menang)
  [5] preference fast/cheap/balanced dari req       (dulu dict bobot mentah)

Dipertahankan dari versi DAVIN (keputusan yang benar):
  - Bukan OR-Tools VRP.
  - Normalisasi min-max sebelum scoring (kalau tidak, cost dalam Rupiah
    mendominasi eta dalam jam hanya karena skala).
"""

from datetime import timedelta
from typing import List
from contracts import RouteOption, RankedResult, TripRequest


# [5] preferensi -> bobot (eta, cost, risk). Semua "makin kecil makin baik".
PREFERENCE_WEIGHTS = {
    "fast":     (0.60, 0.20, 0.20),
    "cheap":    (0.20, 0.60, 0.20),
    "balanced": (0.34, 0.33, 0.33),
}


def _criteria(o: RouteOption):
    """Tiga kriteria yang dinilai, semua makin kecil makin baik."""
    return (o.route.eta_hours_likely, o.cost.total_cost_rp, o.quality.spoil_risk)


def pareto_front(options: List[RouteOption]) -> List[RouteOption]:
    """Buang rute yang didominasi total oleh rute lain pada (eta, cost, risk)."""
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


def _deadline_check(options: List[RouteOption], req: TripRequest) -> None:
    """[2] Isi meets_deadline per rute berdasarkan ETA PESIMIS (konservatif)."""
    if not req.deadline:
        for o in options:
            o.meets_deadline = True
        return
    for o in options:
        tiba = req.departure_time + timedelta(hours=o.route.eta_hours_pessimistic)
        o.meets_deadline = tiba <= req.deadline


def rank_options(options: List[RouteOption], req: TripRequest) -> RankedResult:
    """Kontrak: Pareto front + weighted scoring sesuai preferensi + alert deadline."""
    if not options:
        return RankedResult(best=None, pareto=[], all_options=[],
                            deadline_feasible=False, alert="Tidak ada rute kandidat.")

    weights = PREFERENCE_WEIGHTS.get(req.preference, PREFERENCE_WEIGHTS["balanced"])

    # [2] cek deadline dulu supaya skor & alert konsisten
    _deadline_check(options, req)

    # skor dihitung pada SEMUA opsi (range global) supaya all_options bisa diurutkan
    ranges = _ranges(options)
    for o in options:
        o.score = _score(o, weights, ranges)

    all_sorted = sorted(options, key=lambda o: o.score)
    pareto = sorted(pareto_front(options), key=lambda o: o.score)  # [4] tetap simpan semua

    feasible = [o for o in all_sorted if o.meets_deadline]
    deadline_feasible = bool(feasible)

    # [2] pemenang: rute skor terbaik yang MASIH mengejar deadline; kalau tak ada, skor terbaik
    best = (feasible or all_sorted)[0]

    # [2] ALERT DEADLINE — output yang dijanjikan ke juri
    alert = None
    if req.deadline and not deadline_feasible:
        tercepat = min(options, key=lambda o: o.route.eta_hours_pessimistic)
        tiba = req.departure_time + timedelta(hours=tercepat.route.eta_hours_pessimistic)
        telat_jam = (tiba - req.deadline).total_seconds() / 3600.0
        alert = (f"Deadline tidak terkejar oleh rute mana pun. "
                 f"Rute tercepat ({tercepat.route.name}) tiba "
                 f"{tiba:%H:%M} — telat {telat_jam:.1f} jam. "
                 f"Pertimbangkan ganti moda (reefer) atau majukan jam berangkat.")
    elif req.deadline and best.quality.spoil_risk >= 0.7:
        # rute terkejar deadline tapi barang berisiko busuk -> tetap peringatkan
        alert = (f"Rute terbaik mengejar deadline, tapi risiko busuk tinggi "
                 f"({best.quality.spoil_risk:.0%}). Pertimbangkan reefer.")

    return RankedResult(
        best=best,
        pareto=pareto,
        all_options=all_sorted,
        deadline_feasible=deadline_feasible,
        alert=alert,
    )


if __name__ == "__main__":
    print("optimizer.py — jalankan demo_end_to_end.py untuk uji terintegrasi.")
