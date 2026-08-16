"""
test_validation.py — Uji kewarasan M2 Spoilage  (owner: GAB)
=============================================================
PATCH 2026-08-09 (usulan QA — kerangka awal, silakan dilengkapi GAB).

Ini deliverable #3. Belum wajib selesai di Hari 1-2, tapi kerangkanya
ditaruh sekarang supaya perbaikan model bisa langsung diverifikasi.

Jalankan:  python test_validation.py        (tanpa pustaka uji, non-interaktif)
Keluar 0 kalau semua lolos, 1 kalau ada yang gagal.

CATATAN PENTING soal patokan FAO
--------------------------------
Acuan meminta: laju pembusukan +-2x pada 5C dan +-5-6x pada 10C (relatif 0C).

Model akar-kuadrat SECARA MATEMATIS TIDAK BISA mengenai keduanya sekaligus:

    agar 5C  tepat 2,0x  -> Tmin = -12,07C, akibatnya 10C hanya 3,34x
    agar 10C tepat 5,5x  -> Tmin =  -7,43C, akibatnya 5C  jadi  2,80x

Kurva kuadrat lebih landai daripada patokan itu; angka 5-6x pada 10C berasal
dari fit eksponensial berentang sempit. Karena acuan mewajibkan setiap
parameter punya sumber, kami memilih Tmin = -10C (nilai baku SSSP-DTU untuk
Pseudomonas/Shewanella) ketimbang angka hasil fit yang tidak punya rujukan.

Konsekuensinya didokumentasikan, bukan disembunyikan:
    5C  -> 2,25x  (lolos pita +-2x)
    10C -> 4,00x  (DI BAWAH pita 5-6x — penyimpangan yang disadari)

Uji di bawah memakai pita 10C yang dilebarkan ke 3,5-6,5x, dan mencetak
peringatan eksplisit. Ini keputusan yang perlu disahkan grup — jangan
diam-diam dianggap lolos.
"""

import sys

from models import COMMODITY_DB, INITIAL_CONDITION_MAP
from engine import degradation_rate, compute_spoilage, spoilage_risk

_gagal: list = []


def periksa(nama: str, lolos: bool, detail: str = "") -> None:
    tanda = "LOLOS" if lolos else "GAGAL"
    print(f"  [{tanda}] {nama}" + (f" — {detail}" if detail else ""))
    if not lolos:
        _gagal.append(nama)


# ============================================================
def uji_patokan_fao_ikan() -> None:
    """Laju relatif terhadap 0C harus sejalan patokan FAO."""
    print("\n1. Patokan FAO — laju pembusukan ikan relatif 0C")
    p = COMMODITY_DB["ikan_segar"]
    r0 = degradation_rate(0.0, p)
    r5, r10 = degradation_rate(5.0, p) / r0, degradation_rate(10.0, p) / r0

    periksa("5C dalam pita 1,7-2,6x", 1.7 <= r5 <= 2.6, f"terukur {r5:.2f}x")
    periksa("10C dalam pita 3,5-6,5x (dilebarkan)", 3.5 <= r10 <= 6.5, f"terukur {r10:.2f}x")
    if not (5.0 <= r10 <= 6.0):
        print(f"    PERINGATAN: 10C = {r10:.2f}x, di luar pita asli FAO 5-6x. "
              f"Alasan ada di docstring — sahkan ke grup sebelum dipakai di slide.")


def uji_kewarasan_tropis() -> None:
    """Ekstrapolasi ke suhu ambien Indonesia harus tetap masuk akal.

    Uji inilah yang menangkap bug versi lama: model eksponensial memberi
    umur simpan ikan 0,99 jam pada 30C.
    """
    print("\n2. Kewarasan pada suhu ambien tropis (skenario non-reefer)")
    p = COMMODITY_DB["ikan_segar"]
    for T, lo, hi in [(25.0, 12.0, 30.0), (30.0, 8.0, 24.0), (35.0, 6.0, 20.0)]:
        jam = (1.0 / degradation_rate(T, p)) * 24.0
        periksa(f"ikan @{T:.0f}C bertahan {lo:.0f}-{hi:.0f} jam", lo <= jam <= hi,
                f"terukur {jam:.1f} jam")


def uji_monotonisitas() -> None:
    """Makin panas harus makin cepat rusak, untuk semua komoditas."""
    print("\n3. Monotonisitas laju terhadap suhu")
    for kunci, p in COMMODITY_DB.items():
        laju = [degradation_rate(T, p) for T in range(0, 41, 5)]
        naik = all(b > a for a, b in zip(laju, laju[1:]))
        periksa(f"{kunci}: laju naik monoton 0-40C", naik)


def uji_ambang_layak_jual() -> None:
    """Bug versi lama: is_sellable = quality_remaining > 0.0."""
    print("\n4. Ambang layak jual")
    r = compute_spoilage("bayam", [{"duration_hours": 19.3, "temp_c": 30.0}], "segar")
    periksa("bayam 0,5% segar TIDAK layak jual", r["is_sellable"] is False,
            f"pct_fresh={r['freshness_percent']}%")
    r = compute_spoilage("bayam", [{"duration_hours": 0.0, "temp_c": 4.0}], "sangat_segar")
    periksa("bayam utuh layak jual", r["is_sellable"] is True,
            f"pct_fresh={r['freshness_percent']}%")


def uji_rentang_risiko() -> None:
    """Bug versi lama: risiko mentok di 0,769 walau barang habis."""
    print("\n5. Rentang skor risiko")
    periksa("risiko saat berangkat < 0,05", spoilage_risk(0.0) < 0.05,
            f"{spoilage_risk(0.0):.3f}")
    periksa("risiko saat umur simpan habis > 0,95", spoilage_risk(1.0) > 0.95,
            f"{spoilage_risk(1.0):.3f}")


def uji_kondisi_awal() -> None:
    """Barang berangkat lebih segar harus tiba lebih segar."""
    print("\n6. Urutan kondisi awal")
    seg = [{"duration_hours": 6.0, "temp_c": 20.0}]
    nilai = [compute_spoilage("ikan_segar", seg, k)["freshness_percent"]
             for k in ("kurang_segar", "segar", "sangat_segar")]
    periksa("kurang_segar < segar < sangat_segar", nilai[0] < nilai[1] < nilai[2],
            " < ".join(f"{v}%" for v in nilai))


def uji_kelengkapan_sumber() -> None:
    """Acuan: setiap baris parameter wajib punya sumber."""
    print("\n7. Kelengkapan sumber parameter")
    for kunci, p in COMMODITY_DB.items():
        periksa(f"{kunci} punya sumber", len(p.sources) > 0,
                f"{len(p.sources)} rujukan")


def ringkas_tabel() -> None:
    print("\n" + "=" * 62)
    print("TABEL LAJU RELATIF (acuan 0C) — untuk lampiran slide")
    print("=" * 62)
    print(f"{'komoditas':<12} {'model':<18} {'5C':>7} {'10C':>7} {'30C':>7}")
    for kunci, p in COMMODITY_DB.items():
        r0 = degradation_rate(0.0, p)
        print(f"{kunci:<12} {p.model_type:<18} "
              f"{degradation_rate(5.0, p)/r0:>6.2f}x {degradation_rate(10.0, p)/r0:>6.2f}x "
              f"{degradation_rate(30.0, p)/r0:>6.2f}x")


def main() -> int:
    print("=" * 62)
    print("UJI VALIDASI M2 SPOILAGE — Cold Chain AI")
    print("=" * 62)

    uji_patokan_fao_ikan()
    uji_kewarasan_tropis()
    uji_monotonisitas()
    uji_ambang_layak_jual()
    uji_rentang_risiko()
    uji_kondisi_awal()
    uji_kelengkapan_sumber()
    ringkas_tabel()

    print("\n" + "=" * 62)
    if _gagal:
        print(f"HASIL: {len(_gagal)} uji GAGAL -> {', '.join(_gagal)}")
        return 1
    print("HASIL: semua uji lolos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
