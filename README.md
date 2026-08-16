# Cold Chain AI — Backend (M1 · M2 · M3)

Backend pendukung keputusan pengiriman komoditas mudah rusak di Indonesia (Smart Logistics).
Menjawab pertanyaan **"apakah barang masih layak jual saat tiba?"** — bukan sekadar ETA —
dengan menyatukan rute + cuaca (M1), model pembusukan (M2), dan optimizer biaya/trade-off (M3).

Repo ini berisi **tiga model backend + kontrak antarmodul**. UI/agent dibangun terpisah
(oleh CATH) di atas antarmuka `pipeline.run_pipeline()`.

> **Status:** modul di repo ini adalah hasil integrasi yang sudah **diverifikasi jalan
> end-to-end**, tetapi **belum di-review pemilik masing-masing modul** (GAB, RIO, DAVIN).
> Perlakukan sebagai baseline yang stabil untuk mulai membangun UI, bukan versi final.
> Detail per modul & keputusan yang masih menggantung ada di folder `reports/` proyek.

---

## Arsitektur

```
TripRequest (input pengguna)
      │
      ▼
  M1  RIO   ── routing.py       → 3–5 RouteCandidate (tol & non-tol) + pita ETA + toll_segments
            └─ temp_profile.py  → TempProfile per rute (reefer setpoint / ambien Open-Meteo)
      │
      ▼
  M2  GAB   ── quality.py       → QualityResult (% fresh, risiko, layak jual)
            └─ engine.py, models.py   (RRS square-root + Arrhenius per mekanisme)
      │
      ▼
  M3  DAVIN ── cost.py          → CostResult (tol BPJT + BBM)
            ├─ optimizer.py     → RankedResult (Pareto + skor preferensi + alert deadline)
            └─ toll_table.py    → lookup tarif (data/tarif_tol_jawa.csv, 858 ruas Jawa)
      │
      ▼
  RankedResult  →  UI / agent (CATH)
```

`contracts.py` (owner: CATH) adalah **antarmuka beku** — semua modul menempel ke sini.
Pipeline deterministik: urutan ditetapkan kode (rute → suhu → spoilage → biaya → ranking),
bukan oleh LLM.

## Pemetaan file ke pemilik

| Modul | File | Pemilik |
|---|---|---|
| Kontrak | `contracts.py` | CATH |
| M1 rute & ETA | `routing.py`, `temp_profile.py` | RIO |
| M2 spoilage | `quality.py`, `engine.py`, `models.py`, `test_validation.py` | GAB |
| M3 optimizer | `cost.py`, `optimizer.py`, `toll_table.py`, `scenarios.py`, `review_gab_validation.py` | DAVIN |
| Perekat | `pipeline.py`, `demo.py` | bersama |
| Data | `data/tarif_tol_jawa.csv` | DAVIN (sumber BPJT) |

## Menjalankan

### Lokal (Python 3.11+)

```bash
python -m venv venv && source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
python demo.py            # demo rantai penuh Jakarta→Bandung (reefer vs non-reefer)
```

### Docker

```bash
docker compose up --build
```

Menjalankan `demo.py` di dalam kontainer sebagai bukti reprodusibilitas lokal.
CATH mengganti `command` di `docker-compose.yml` dengan service UI-nya saat siap.

### Perintah lain

```bash
python scenarios.py             # what-if: reefer/non-reefer, jam berangkat, preferensi
python test_validation.py       # uji kewarasan model spoilage (M2) — patokan FAO dsb.
python review_gab_validation.py # review lintas-modul M3 atas M2
```

## Memakai dari kode UI/agent (CATH)

```python
import pipeline
from contracts import TripRequest
from datetime import datetime

pipeline.configure_cost(golongan="II_III")   # armada CDD; "I" utk pick up/truk kecil

req = TripRequest(
    origin=(106.8272, -6.1751),       # (lon, lat) Jakarta
    destination=(107.6098, -6.9147),  # (lon, lat) Bandung
    commodity="ikan_segar",           # ikan_segar | bayam | kentang
    departure_time=datetime(2026, 8, 20, 8, 0),
    vehicle="non_reefer",             # non_reefer | reefer
    preference="balanced",            # fast | cheap | balanced
    deadline=datetime(2026, 8, 20, 13, 0),
    initial_condition="segar",        # sangat_segar | segar | kurang_segar
)

result = pipeline.run_pipeline(req)   # -> contracts.RankedResult
```

`RankedResult`: `.best`, `.pareto[]`, `.all_options[]`, `.deadline_feasible`, `.alert`.
Tiap `RouteOption`: `.route`, `.quality`, `.cost`, `.score`, `.meets_deadline` — semua
dataclass, langsung bisa `dataclasses.asdict(...)` → JSON untuk frontend.

## Ketergantungan jaringan & ketahanan demo

`routing.py` dan `temp_profile.py` memanggil **OSRM** (rute) dan **Open-Meteo** (cuaca) live.
Keduanya gratis tanpa kunci. OSRM demo publik rate-limited (~1 req/detik), jadi ada
**fallback fixture**: kalau server tak terjangkau, pipeline tetap menghasilkan ≥3 kandidat
Jakarta–Bandung — demo & cross-check tidak akan gagal hanya karena jaringan.

## Prinsip yang mengikat (jangan dilanggar)

- **Physics-first, tanpa ML terlatih.** Setiap angka dari API atau rumus transparan.
- **Tanpa IoT.** Suhu kargo = asumsi skenario (reefer setpoint / ambien), ditandai di `source`.
- **LLM menarasikan angka, tidak mengarang.** Semua nilai dari fungsi Python.
- **Satu model spoilage** (M2/GAB). Modul lain tidak menghitung kesegaran sendiri.
- **`contracts.py` adalah hukum.** Perubahan diumumkan ke grup.

## Yang belum final (untuk kesadaran CATH)

- Parameter statis skenario: golongan tol, konsumsi & harga BBM (`pipeline.configure_cost`).
- Peta koridor tol saat ini Jakarta–Bandung (`routing.CORRIDOR_TOLL`).
- Faktor ETA (`f_time`/`f_weather`) masih placeholder, menunggu kalibrasi.
- Modul warisan RIO (`main.py` FastAPI + frontend MapKit) TIDAK disertakan; kepemilikan UI
  masih dibicarakan. Backend ini adalah lapisan model yang sudah dipisah bersih dari UI.
