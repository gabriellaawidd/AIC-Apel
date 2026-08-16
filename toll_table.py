"""
toll_table.py — Lookup tarif tol  (owner: DAVIN)
=================================================
PATCH 2026-08-16 (usulan QA — belum di-merge, silakan review).

Menggantikan lookup di cost_model.py lama dengan dua perbaikan penting:
  [1] Membaca dataset Jawa penuh (tarif_tol_jawa.csv, 858 baris) — koridor
      Jakarta-Bandung dst. sudah tercakup.
  [2] Menghormati kolom `sistem` (terbuka/tertutup). Di ruas sistem terbuka,
      tarif FLAT — tidak dijumlahkan per gerbang. Ini menutup bug penjumlahan
      yang ada di versi lama.

Encoding segmen (kontrak dgn RIO — WAJIB disepakati):
  RouteCandidate.toll_segments adalah List[str] (sesuai contracts.py).
  Setiap string berformat  "ruas::asal::tujuan".
  Contoh: "Cikampek-Padalarang::SS Dawuan::SS Padalarang"
  RIO menghasilkan satu entri PER RUAS yang dilewati, dengan gerbang
  masuk (asal) dan gerbang keluar (tujuan) di ruas itu — BUKAN satu entri
  per gerbang. Ini yang membuat sistem tertutup dihitung benar.
"""

import csv
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

SEGMENT_DELIM = "::"


@dataclass
class TollLookupResult:
    toll_cost: int
    unmatched: list   # daftar string segmen yang tarifnya tidak ketemu
    open_system_ruas: list  # ruas sistem terbuka yang kena (untuk transparansi)


class TollTable:
    """Tabel tarif tol dari tarif_tol_jawa.csv."""

    GOL_COL = {"I": "gol_I", "II_III": "gol_II_III", "IV_V": "gol_IV_V"}

    def __init__(self, csv_path: str):
        self.rows = []
        with open(csv_path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                self.rows.append(r)
        # index (ruas,asal,tujuan) -> row untuk lookup cepat
        self._idx = {}
        for r in self.rows:
            key = (self._norm(r["ruas"]), self._norm(r["asal"]), self._norm(r["tujuan"]))
            self._idx[key] = r

    @staticmethod
    def _norm(s: str) -> str:
        return (s or "").strip().lower()

    def lookup_one(self, ruas: str, asal: str, tujuan: str, golongan: str = "I") -> Optional[int]:
        col = self.GOL_COL[golongan]
        row = self._idx.get((self._norm(ruas), self._norm(asal), self._norm(tujuan)))
        if row is None:
            return None
        return int(row[col])

    def is_open_system(self, ruas: str) -> bool:
        rn = self._norm(ruas)
        for r in self.rows:
            if self._norm(r["ruas"]) == rn:
                return r.get("sistem", "tertutup") == "terbuka"
        return False

    def cost_for_segments(self, toll_segments: list, golongan: str = "I") -> TollLookupResult:
        """Jumlahkan tarif sepanjang rute, hormati sistem terbuka.

        toll_segments: List[str] berformat "ruas::asal::tujuan" (lihat header).
        Sistem terbuka dihitung SEKALI per ruas walau muncul beberapa kali.
        """
        total = 0
        unmatched = []
        open_hit = []
        charged_open_ruas = set()

        for seg in toll_segments:
            parts = seg.split(SEGMENT_DELIM)
            if len(parts) != 3:
                unmatched.append(f"{seg} (format salah, harus ruas::asal::tujuan)")
                continue
            ruas, asal, tujuan = (p.strip() for p in parts)

            if self.is_open_system(ruas):
                if self._norm(ruas) in charged_open_ruas:
                    continue  # sistem terbuka: sudah ditagih, jangan double
                charged_open_ruas.add(self._norm(ruas))
                open_hit.append(ruas)

            tarif = self.lookup_one(ruas, asal, tujuan, golongan)
            if tarif is None:
                unmatched.append(f"{ruas}: {asal} -> {tujuan}")
            else:
                total += tarif

        return TollLookupResult(toll_cost=total, unmatched=unmatched, open_system_ruas=open_hit)


def default_table() -> TollTable:
    """Muat CSV yang berdampingan dengan file ini."""
    here = Path(__file__).parent / "data" / "tarif_tol_jawa.csv"
    return TollTable(str(here))


if __name__ == "__main__":
    t = default_table()
    print(f"Tabel dimuat: {len(t.rows)} baris")
    demo = [
        "Cikampek-Padalarang::SS Dawuan::SS Padalarang",
        "Jakarta-Bogor-Ciawi::Jakarta::Ciawi",
    ]
    for gol in ("I", "II_III"):
        res = t.cost_for_segments(demo, golongan=gol)
        print(f"  gol {gol:<6} tol = Rp{res.toll_cost:,}  "
              f"terbuka={res.open_system_ruas}  unmatched={res.unmatched}")
