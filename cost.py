"""
cost.py — Biaya tol + BBM  (owner: DAVIN)
==========================================
PATCH 2026-08-16 (usulan QA — belum di-merge, silakan review).

Menggantikan cost_model.py lama. Perubahan terhadap versi DAVIN:
  [1] evaluate_cost(route) -> CostResult    (SESUAI contracts.py, dulu CostBreakdown)
  [2] route_id diteruskan                    (dulu hilang -> kunci join putus)
  [3] parameter BBM & golongan bersumber     (lihat CostConfig)
  [4] baca dataset Jawa + kolom sistem       (lewat toll_table.py)

Kenapa golongan & BBM jadi CONFIG modul, bukan argumen fungsi:
  Kontrak menetapkan `evaluate_cost(route: RouteCandidate) -> CostResult` —
  tanpa `req`. Jadi golongan kendaraan & harga BBM adalah PARAMETER STATIS
  skenario (persis yang diminta rulebook: "parameter statis saat demo").
  Set sekali via set_config() sebelum menjalankan pipeline.
"""

from dataclasses import dataclass
from contracts import RouteCandidate, CostResult
from toll_table import TollTable, default_table


# ============================================================
# [3] Konfigurasi biaya — semua bersumber (Agustus 2026)
# ============================================================
@dataclass
class CostConfig:
    golongan: str = "II_III"          # CDD 2 gandar (Kepmen PU 370/KPTS/M/2007).
                                      # pakai "I" hanya kalau armada pick up / truk kecil.
    km_per_liter: float = 7.0         # truk bak terbuka bermuatan; rentang sumber 6-9 km/L
    harga_bbm_per_liter: int = 6_800  # Biosolar subsidi, nasional, per Agustus 2026
                                      # (Perpres 191/2014: angkutan barang plat kuning roda 6 berhak)

    def basis(self) -> str:
        gol_label = {"I": "Gol I", "II_III": "Gol II/III", "IV_V": "Gol IV/V"}[self.golongan]
        return (f"{gol_label}; {self.km_per_liter} km/L; "
                f"Solar Rp{self.harga_bbm_per_liter:,}/L (subsidi)")


_CONFIG = CostConfig()
_TABLE: TollTable | None = None


def set_config(cfg: CostConfig) -> None:
    global _CONFIG
    _CONFIG = cfg


def get_config() -> CostConfig:
    return _CONFIG


def _table() -> TollTable:
    global _TABLE
    if _TABLE is None:
        _TABLE = default_table()
    return _TABLE


def estimasi_biaya_bbm(distance_km: float, cfg: CostConfig = None) -> int:
    cfg = cfg or _CONFIG
    liter = distance_km / cfg.km_per_liter
    return round(liter * cfg.harga_bbm_per_liter)


def evaluate_cost(route: RouteCandidate) -> CostResult:
    """Kontrak: gabungkan tarif tol (BPJT) + estimasi BBM per rute.

    route.toll_segments : List[str] "ruas::asal::tujuan" (lihat toll_table.py).
    Golongan & harga BBM dari config modul (parameter statis skenario).
    """
    cfg = _CONFIG
    if route.uses_toll and route.toll_segments:
        res = _table().cost_for_segments(route.toll_segments, golongan=cfg.golongan)
        toll = float(res.toll_cost)
        # Segmen yang tak ketemu tidak didiamkan jadi Rp0 — dicatat di assumptions rute.
        if res.unmatched:
            route.assumptions["toll_unmatched"] = float(len(res.unmatched))
    else:
        toll = 0.0

    fuel = float(estimasi_biaya_bbm(route.distance_km, cfg))
    return CostResult(
        route_id=route.route_id,
        toll_cost_rp=toll,
        fuel_cost_rp=fuel,
        total_cost_rp=toll + fuel,
    )


if __name__ == "__main__":
    # Uji cepat dgn RouteCandidate ala kontrak
    r = RouteCandidate(
        route_id="jkt-bdg-tol", name="Via Cipularang", distance_km=151.0,
        eta_hours_likely=2.6, eta_hours_optimistic=2.3, eta_hours_pessimistic=3.4,
        uses_toll=True,
        toll_segments=[
            "Jakarta-Cikampek dan Jakarta -Cikampek II Elevated ::Cikampek (Kalihurip)::Cikampek",
            "Cikampek-Padalarang::SS Dawuan::SS Padalarang",
        ],
    )
    for gol in ("I", "II_III", "IV_V"):
        set_config(CostConfig(golongan=gol))
        c = evaluate_cost(r)
        print(f"gol {gol:<6} tol=Rp{c.toll_cost_rp:>10,.0f} | "
              f"bbm=Rp{c.fuel_cost_rp:>10,.0f} | total=Rp{c.total_cost_rp:>10,.0f}")
    print("basis:", get_config().basis())
