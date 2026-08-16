"""
quality.py — Adapter kontrak untuk M2 Spoilage  (owner: GAB)
=============================================================
PATCH 2026-08-09 (usulan QA — belum di-merge, silakan review).

[2] Ini file BARU. Isinya satu-satunya fungsi yang boleh dipanggil modul lain:

        predict_quality(req: TripRequest, profile: TempProfile) -> QualityResult

Kenapa dipisah dari engine.py: `engine.compute_spoilage` enak dipakai untuk
eksperimen dan uji, tapi bentuknya bukan bentuk kontrak. Daripada mengubah
engine sampai canggung, adapter tipis ini yang menjembatani. Engine tetap
bebas dipakai GAB untuk eksplorasi.

Yang diperbaiki di sini (semua dari Temuan 5 laporan QA):
  - `route_id` diteruskan            -> kunci join ke DAVIN & CATH
  - satuan jam, bukan hari           -> remaining_shelf_life_h
  - field `basis` diisi
  - nama field disamakan             -> pct_fresh, spoil_risk
  - TempProfile (waktu KUMULATIF) dikonversi ke segmen (DURASI per potong)
"""

from typing import List, Dict

from contracts import TripRequest, TempProfile, QualityResult
from engine import compute_spoilage


def profile_to_segments(profile: TempProfile) -> List[Dict[str, float]]:
    """TempProfile -> daftar segmen untuk engine.

    PENTING — ini sumber salah tafsir paling berbahaya antara RIO dan GAB:

        TempProfile.times_h  = waktu KUMULATIF sejak berangkat  [0, 1.6, 3.2, ...]
        engine  butuh        = DURASI tiap potong               [1.6, 1.6, ...]

    Kalau times_h dipakai langsung sebagai durasi, hasilnya tetap "masuk akal"
    di layar tapi salah beberapa kali lipat, tanpa error apa pun.

    Suhu tiap potong dipakai rata-rata kedua ujungnya (aturan trapesium),
    lebih tepat daripada mengambil suhu ujung kiri saja.
    """
    n = len(profile.times_h)
    if n != len(profile.temps_c):
        raise ValueError(
            f"TempProfile rusak: times_h={n} titik tapi temps_c={len(profile.temps_c)}"
        )
    if n < 2:
        return []

    return [
        {
            "duration_hours": profile.times_h[i + 1] - profile.times_h[i],
            "temp_c": (profile.temps_c[i] + profile.temps_c[i + 1]) / 2.0,
        }
        for i in range(n - 1)
    ]


def predict_quality(req: TripRequest, profile: TempProfile) -> QualityResult:
    """Mesin spoilage: akumulasi kerusakan aditif -> % fresh.

    Tanda tangan & tipe kembalian mengikuti contracts.py — jangan diubah
    tanpa mengumumkan ke grup.
    """
    segmen = profile_to_segments(profile)
    hasil = compute_spoilage(req.commodity, segmen, kondisi_awal=req.initial_condition)

    # Sumber suhu ikut dicatat supaya asumsi transparan di dashboard.
    basis = f"{hasil['basis']}; suhu={profile.source}"

    return QualityResult(
        route_id=profile.route_id,
        pct_fresh=hasil["freshness_percent"],
        remaining_shelf_life_h=hasil["remaining_shelf_life_hours"],
        spoil_risk=hasil["spoilage_risk"],
        is_sellable=hasil["is_sellable"],
        basis=basis,
    )
