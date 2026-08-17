"""Parameter tetap (deterministik). Semua angka dari sini / literatur, bukan dari LLM."""

# --- Tabel shelf-life referensi per komoditas (MVP: ikan, kentang, bayam) ---
# SL_ref_hours : shelf-life (jam) pada suhu referensi T_ref (= suhu penyimpanan OPTIMAL).
# Tmin         : karakteristik suhu model RRS square-root (C).
# chill_sensitive / chill_threshold_c : komoditas yang RUSAK bila terlalu dingin
#                (chilling injury / cold-induced sweetening) — mis. kentang < 4 C.
# Sumber: FAO (ikan), USDA/UC-Davis & CIP (kentang), postharvest leafy greens (bayam).
COMMODITY_PARAMS = {
    "ikan": {
        "SL_ref_hours": 312, "T_ref": 0.0, "Tmin": -10.0,
        "chill_sensitive": False, "chill_threshold_c": None,
        "aliases": ["ikan", "ikan segar", "fish", "ikan_segar"],
    },
    "kentang": {
        # Optimal 7-10 C; DINGIN < 4 C memicu cold-sweetening/chilling injury.
        "SL_ref_hours": 2160, "T_ref": 8.0, "Tmin": -3.0,
        "chill_sensitive": True, "chill_threshold_c": 4.0,
        "aliases": ["kentang", "potato"],
    },
    "bayam": {
        # Leafy green sangat perishable; optimal ~0 C, respirasi naik tajam di atas 3 C.
        "SL_ref_hours": 300, "T_ref": 0.0, "Tmin": -5.5,
        "chill_sensitive": False, "chill_threshold_c": None,
        "aliases": ["bayam", "spinach", "spinacia", "sayur", "sayur daun"],
    },
}
DEFAULT_COMMODITY = "ikan"  # proxy fallback

# Penalti chilling injury: damage per (derajat di bawah threshold) per jam paparan.
CHILL_DAMAGE_K = 0.004

# --- Kondisi awal: menggeser titik mulai kerusakan (damage awal) ---
INITIAL_CONDITION_DAMAGE = {"sangat_segar": 0.0, "segar": 0.10, "kurang_segar": 0.25}

# --- Mode kargo ---
REEFER_SETPOINT_C = 2.0      # suhu setpoint reefer (dipakai jika cargo_mode = reefer)
AMBIENT_DEFAULT_C = 30.0     # fallback suhu ambien (tropis) jika API cuaca gagal

# --- Faktor kalibrasi ETA (dikalibrasi dari sampel API traffic, bukan model terlatih) ---
# f_time berdasarkan jam berangkat (0-23) -> pengali kemacetan
F_TIME_BY_HOUR = {
    **{h: 1.05 for h in range(0, 6)},    # dini hari lengang
    **{h: 1.45 for h in [6, 7, 8]},      # sibuk pagi
    **{h: 1.20 for h in [9, 10, 11]},
    **{h: 1.30 for h in [12, 13]},       # siang
    **{h: 1.20 for h in [14, 15, 16]},
    **{h: 1.55 for h in [17, 18, 19]},   # sibuk sore
    **{h: 1.15 for h in [20, 21]},
    **{h: 1.05 for h in [22, 23]},
}
def f_time(hour: int) -> float:
    return F_TIME_BY_HOUR.get(int(hour) % 24, 1.2)

def f_weather(precip_mm: float) -> float:
    """Curah hujan -> pengali. 0 mm=1.0, hujan lebat mendekati 1.3."""
    if precip_mm <= 0.1: return 1.0
    if precip_mm < 2.5:  return 1.10
    if precip_mm < 7.5:  return 1.20
    return 1.30

ETA_OPTIMISTIC_FACTOR = 1.05
ETA_PESSIMISTIC_FACTOR = 1.25

# --- Bobot preset priority untuk weighted scoring (eta, cost, risk) ---
PRIORITY_WEIGHTS = {
    "fast":     {"eta": 0.60, "cost": 0.10, "risk": 0.30},
    "cheap":    {"eta": 0.20, "cost": 0.60, "risk": 0.20},
    "balanced": {"eta": 0.34, "cost": 0.33, "risk": 0.33},
}

# --- Ambang tingkat risiko dari % fresh ---
def risk_level(pct_fresh: float) -> str:
    if pct_fresh >= 85: return "low"
    if pct_fresh >= 65: return "medium"
    return "high"
