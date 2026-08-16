"""
review_gab_validation.py — Review uji validasi GAB  (owner: DAVIN, deliverable #5)
==================================================================================
PATCH 2026-08-16 (usulan QA — belum di-merge, silakan review).

Deliverable #5 DAVIN: "Memeriksa dan menyetujui hasil test_validation.py milik GAB."

Review = tiga lapis, bukan sekadar "tes hijau":
  1. Jalankan uji validasi GAB apa adanya (harus exit 0).
  2. Cek independen: konsumsi hasil spoilage GAB dari sudut M3 — apakah
     spoil_risk yang dipakai untuk ranking masuk akal & monoton.
  3. Verdict tertulis: SETUJU / SETUJU DENGAN CATATAN / TOLAK.

Jalankan:  python review_gab_validation.py
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent

from engine import compute_spoilage  # GAB


def lapis1_jalankan_uji_gab() -> bool:
    print("=" * 68)
    print("LAPIS 1 — Menjalankan test_validation.py milik GAB apa adanya")
    print("=" * 68)
    proc = subprocess.run(
        [sys.executable, str(HERE / "test_validation.py")],
        capture_output=True, text=True, cwd=str(HERE),
    )
    print(proc.stdout[-1200:] if proc.stdout else "(tidak ada output)")
    if proc.returncode != 0:
        print("HASIL LAPIS 1: GAGAL — uji GAB tidak lolos.")
        return False
    print("HASIL LAPIS 1: LOLOS — semua uji GAB hijau.")
    return True


def lapis2_cek_independen_m3() -> bool:
    """Cek dari sisi konsumen (M3): spoil_risk yang jadi input ranking harus waras."""
    print("\n" + "=" * 68)
    print("LAPIS 2 — Cek independen dari sisi M3 (input untuk ranking)")
    print("=" * 68)
    ok = True

    # (a) risiko harus naik monoton terhadap durasi & suhu — kalau tidak, ranking bisa terbalik
    print("\n(a) spoil_risk naik saat perjalanan lebih lama (ikan, 31C):")
    prev = -1.0
    for jam in (2, 4, 6, 8, 10):
        r = compute_spoilage("ikan_segar", [{"duration_hours": jam, "temp_c": 31.0}], "segar")
        risk = 1.0 - r["freshness_percent"] / 100.0  # proxy risiko yg dipakai M3
        naik = risk >= prev
        print(f"    {jam:>2} jam -> fresh {r['freshness_percent']:>5.1f}% "
              f"(risk~{risk:.2f}) {'OK' if naik else 'TURUN?!'}")
        ok &= naik
        prev = risk

    # (b) reefer harus selalu >= non-reefer utk durasi sama — dasar seluruh nilai jual produk
    print("\n(b) reefer (4C) harus lebih segar dari non-reefer (31C), durasi sama:")
    for jam in (4, 8):
        cold = compute_spoilage("ikan_segar", [{"duration_hours": jam, "temp_c": 4.0}], "segar")
        hot = compute_spoilage("ikan_segar", [{"duration_hours": jam, "temp_c": 31.0}], "segar")
        cond = cold["freshness_percent"] >= hot["freshness_percent"]
        print(f"    {jam} jam: reefer {cold['freshness_percent']:.1f}% vs "
              f"non-reefer {hot['freshness_percent']:.1f}%  {'OK' if cond else 'SALAH'}")
        ok &= cond

    # (c) is_sellable konsisten dengan pct_fresh (tidak ada barang busuk dinyatakan layak)
    print("\n(c) is_sellable konsisten dgn ambang (tidak ada busuk 'layak jual'):")
    r = compute_spoilage("bayam", [{"duration_hours": 20, "temp_c": 31.0}], "segar")
    cond = not (r["freshness_percent"] < 20 and r["is_sellable"])
    print(f"    bayam 20j@31C: fresh {r['freshness_percent']:.1f}%, "
          f"sellable={r['is_sellable']}  {'OK' if cond else 'SALAH'}")
    ok &= cond

    print("\nHASIL LAPIS 2:", "LOLOS — output spoilage aman dipakai untuk ranking M3."
          if ok else "GAGAL — ada output yang bisa membalik ranking.")
    return ok


def verdict(l1: bool, l2: bool) -> None:
    print("\n" + "=" * 68)
    print("VERDICT REVIEW (DAVIN atas M2 GAB)")
    print("=" * 68)
    if l1 and l2:
        print("STATUS: SETUJU DENGAN CATATAN")
        print("""
  - Uji validasi GAB lolos penuh, dan output spoilage waras dari sisi M3
    (monoton terhadap durasi/suhu, reefer > non-reefer, is_sellable konsisten).
  - Aman dipakai sebagai input spoil_risk untuk Pareto + ranking.

  CATATAN untuk diputuskan grup (bukan penghambat integrasi):
  1. Patokan FAO 10C = 4,00x, di bawah pita 5-6x. GAB sudah mendokumentasikan
     alasannya (Tmin=-10C bersumber vs hasil fit tanpa rujukan). Saya setuju
     memilih yang bersumber, tapi ini perlu disahkan bersama untuk slide/juri.
  2. Model bayam & kentang = Arrhenius. Konsisten & terkalibrasi, tapi tandai
     'mekanisme respirasi' di narasi Q&A supaya tidak bentrok dgn klaim tim.
""")
    elif l1 and not l2:
        print("STATUS: SETUJU DENGAN CATATAN BERAT — uji hijau tapi ada output")
        print("        yang bisa membalik ranking M3. Perlu diskusi dgn GAB dulu.")
    else:
        print("STATUS: TOLAK — uji validasi GAB belum lolos. Tidak bisa di-review.")


if __name__ == "__main__":
    l1 = lapis1_jalankan_uji_gab()
    l2 = lapis2_cek_independen_m3() if l1 else False
    verdict(l1, l2)
    sys.exit(0 if (l1 and l2) else 1)
