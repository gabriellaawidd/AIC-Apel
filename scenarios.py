"""
scenarios.py — Analisis what-if  (owner: DAVIN, deliverable #4)
===============================================================
PATCH 2026-08-16 (usulan QA — belum di-merge, silakan review).

Menjawab deliverable #4: what-if reefer vs non-reefer, dan variasi jam
berangkat. Semua memakai pipeline terintegrasi (GAB spoilage + DAVIN cost).

Jalankan:  python scenarios.py
Tanpa argumen, non-interaktif, cocok untuk direkam di video proof of work.
"""

from datetime import datetime, timedelta

import contracts as C
from cost import CostConfig
from pipeline import run, print_result

BASE_KW = dict(
    origin=(106.83, -6.18), destination=(107.61, -6.91),
    commodity="ikan_segar", preference="balanced", initial_condition="segar",
)
CFG = CostConfig(golongan="II_III")


def _req(vehicle, departure, deadline=None):
    return C.TripRequest(vehicle=vehicle, departure_time=departure,
                         deadline=deadline, **BASE_KW)


def skenario_reefer_vs_non():
    """What-if #1: kendaraan reefer vs non-reefer, kondisi lain identik."""
    print("=" * 70)
    print("SKENARIO 1 — Reefer vs Non-reefer (berangkat 06:00, deadline 12:00)")
    print("=" * 70)
    dep = datetime(2026, 8, 20, 6, 0)
    dl = datetime(2026, 8, 20, 12, 0)
    for veh in ("non_reefer", "reefer"):
        print(f"\n[{veh}]")
        res = run(_req(veh, dep, dl), CFG)
        print_result(res)
        b = res.best
        print(f"  >> pilih {b.route.name}: fresh {b.quality.pct_fresh:.0f}%, "
              f"Rp{b.cost.total_cost_rp:,.0f}")
    print("\n  Insight: non-reefer lebih murah tapi kesegaran anjlok di ambien 31C; "
          "reefer menjaga kualitas dengan biaya BBM/sewa lebih tinggi.")


def skenario_jam_berangkat():
    """What-if #2: variasi jam berangkat terhadap keterkejaran deadline."""
    print("\n" + "=" * 70)
    print("SKENARIO 2 — Variasi jam berangkat (non-reefer, deadline tetap 12:00)")
    print("=" * 70)
    dl = datetime(2026, 8, 20, 12, 0)
    for jam in (5, 7, 9, 10):
        dep = datetime(2026, 8, 20, jam, 0)
        res = run(_req("non_reefer", dep, dl), CFG)
        status = "terkejar" if res.deadline_feasible else "TIDAK terkejar"
        b = res.best
        print(f"\n  Berangkat {jam:02d}:00 -> deadline {status}. "
              f"Terbaik: {b.route.name} (fresh {b.quality.pct_fresh:.0f}%)")
        if res.alert:
            print(f"    ALERT: {res.alert}")
    print("\n  Insight: makin siang berangkat, makin sempit ruang mengejar deadline; "
          "alert menyala otomatis saat tak ada rute yang cukup.")


def skenario_preferensi():
    """What-if #3: preferensi pengguna fast/cheap/balanced mengubah pilihan."""
    print("\n" + "=" * 70)
    print("SKENARIO 3 — Preferensi pengguna (non-reefer, berangkat 06:00)")
    print("=" * 70)
    dep = datetime(2026, 8, 20, 6, 0)
    dl = datetime(2026, 8, 20, 14, 0)
    for pref in ("fast", "cheap", "balanced"):
        req = C.TripRequest(vehicle="non_reefer", departure_time=dep, deadline=dl,
                            **{**BASE_KW, "preference": pref})
        res = run(req, CFG)
        b = res.best
        print(f"  preferensi '{pref:<8}' -> {b.route.name:<32} "
              f"(ETA {b.route.eta_hours_likely:.1f}j, Rp{b.cost.total_cost_rp:,.0f}, "
              f"fresh {b.quality.pct_fresh:.0f}%)")
    print("\n  Insight: bobot preferensi mengubah rekomendasi tanpa mengubah data — "
          "inilah slider cepat/hemat/aman untuk UI CATH.")


if __name__ == "__main__":
    skenario_reefer_vs_non()
    skenario_jam_berangkat()
    skenario_preferensi()
