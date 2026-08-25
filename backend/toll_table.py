


import csv
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

SEGMENT_DELIM = "::"


@dataclass
class TollLookupResult:
    toll_cost: int
    unmatched: list
    open_system_ruas: list


class TollTable:

    GOL_COL = {"I": "gol_I", "II_III": "gol_II_III", "IV_V": "gol_IV_V"}

    def __init__(self, csv_path: str):
        self.rows = []
        with open(csv_path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                self.rows.append(r)
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
                    continue
                charged_open_ruas.add(self._norm(ruas))
                open_hit.append(ruas)

            tarif = self.lookup_one(ruas, asal, tujuan, golongan)
            if tarif is None:
                unmatched.append(f"{ruas}: {asal} -> {tujuan}")
            else:
                total += tarif

        return TollLookupResult(toll_cost=total, unmatched=unmatched, open_system_ruas=open_hit)

    def max_row_for_ruas(self, ruas: str) -> Optional[dict]:
        rn = self._norm(ruas)
        cands = [r for r in self.rows if self._norm(r["ruas"]) == rn]
        if not cands:
            return None
        return max(cands, key=lambda r: int(r[self.GOL_COL["II_III"]]))

    def breakdown_for_segments(self, toll_segments: list, golongan: str = "I") -> list:

        out = []
        charged_open = set()
        for seg in toll_segments:
            parts = [p.strip() for p in seg.split(SEGMENT_DELIM)]
            if len(parts) != 3:
                continue
            ruas, asal, tujuan = parts
            if self.is_open_system(ruas):
                if self._norm(ruas) in charged_open:
                    continue
                charged_open.add(self._norm(ruas))
            tarif = self.lookup_one(ruas, asal, tujuan, golongan)
            out.append({
                "ruas": ruas,
                "gerbang_masuk": asal,
                "gerbang_keluar": tujuan,
                "golongan": golongan,
                "tarif_rp": float(tarif) if tarif is not None else 0.0,
                "sistem": "terbuka" if self.is_open_system(ruas) else "tertutup",
                "km_di_ruas": None,
                "perkiraan": tarif is None,
                "catatan": "" if tarif is not None else "tarif gerbang ini tidak ada di data BPJT",
            })
        return out

    def breakdown_for_usage(self, ruas_km: dict, golongan: str = "I",
                            exact_gates: dict = None) -> list:


        from toll_detect import ruas_length_km

        exact_gates = exact_gates or {}
        out = []
        for ruas, km in sorted(ruas_km.items(), key=lambda kv: -kv[1]):
            gates = exact_gates.get(ruas)
            if gates:
                tarif = self.lookup_one(ruas, gates[0], gates[1], golongan)
                if tarif is not None:
                    out.append({
                        "ruas": ruas,
                        "gerbang_masuk": gates[0], "gerbang_keluar": gates[1],
                        "golongan": golongan, "tarif_rp": float(tarif),
                        "sistem": "terbuka" if self.is_open_system(ruas) else "tertutup",
                        "km_di_ruas": km, "perkiraan": False,
                        "catatan": "tarif gerbang tervalidasi",
                    })
                    continue

            row = self.max_row_for_ruas(ruas)
            if row is None:
                out.append({
                    "ruas": ruas, "gerbang_masuk": "—", "gerbang_keluar": "—",
                    "golongan": golongan, "tarif_rp": 0.0, "sistem": "?",
                    "km_di_ruas": km, "perkiraan": True,
                    "catatan": "ruas tidak ada di data tarif BPJT — belum dihitung",
                })
                continue

            tarif_penuh = float(row[self.GOL_COL[golongan]])
            panjang = ruas_length_km(ruas)
            terbuka = row.get("sistem", "tertutup") == "terbuka"

            if terbuka:
                tarif = tarif_penuh
                catatan = "sistem terbuka — tarif flat, tidak dihitung per km"
            elif panjang:
                rasio = min(1.0, km / panjang)
                tarif = round(tarif_penuh * rasio)
                catatan = (f"perkiraan {rasio:.0%} dari tarif ruas penuh "
                           f"({km:.0f} km dari {panjang:.0f} km)")
            else:
                tarif = tarif_penuh
                catatan = "panjang ruas tidak diketahui — dipakai tarif ruas penuh"

            out.append({
                "ruas": ruas,
                "gerbang_masuk": row["asal"],
                "gerbang_keluar": row["tujuan"],
                "golongan": golongan,
                "tarif_rp": float(tarif),
                "sistem": "terbuka" if terbuka else "tertutup",
                "km_di_ruas": km,
                "perkiraan": True,
                "catatan": catatan,
            })
        return out


def default_table() -> TollTable:
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
