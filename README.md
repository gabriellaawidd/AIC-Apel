# Cold Chain AI — Backend (M1 · M2 · M3)

Decision-support backend for shipping perishable goods across Indonesia (Smart Logistics).
It answers **"will the cargo still be sellable on arrival?"** — not just ETA — by combining
routing + weather (M1), a food-spoilage model (M2), and a cost/trade-off optimizer (M3).

This repo contains the **three backend models + the shared contract**. The UI/agent is built
separately (by CATH) on top of the `pipeline.run_pipeline()` interface.

> **Status:** the modules here are an integration that has been **verified to run end-to-end**,
> but they have **not yet been reviewed by each module's owner** (GAB, RIO, DAVIN). Treat this
> as a stable baseline to start building the UI on, not a final version. Per-module details and
> open decisions live in the project's `reports/` folder.

---

## Architecture

```
TripRequest (user input)
      │
      ▼
  M1  RIO   ── routing.py       → 3–5 RouteCandidate (toll & non-toll) + ETA band + toll_segments
            └─ temp_profile.py  → TempProfile per route (reefer setpoint / ambient Open-Meteo)
      │
      ▼
  M2  GAB   ── quality.py       → QualityResult (% fresh, spoilage risk, sellable)
            └─ engine.py, models.py   (RRS square-root + Arrhenius, per spoilage mechanism)
      │
      ▼
  M3  DAVIN ── cost.py          → CostResult (BPJT toll + fuel)
            ├─ optimizer.py     → RankedResult (Pareto + preference score + deadline alert)
            └─ toll_table.py    → tariff lookup (data/tarif_tol_jawa.csv, 858 Java segments)
      │
      ▼
  RankedResult  →  UI / agent (CATH)
```

`contracts.py` (owner: CATH) is the **frozen interface** — every module plugs into it.
The pipeline is deterministic: order is fixed in code (route → temperature → spoilage → cost →
ranking), not decided by an LLM.

## File-to-owner map

| Module | Files | Owner |
|---|---|---|
| Contract | `contracts.py` | CATH |
| M1 routing & ETA | `routing.py`, `temp_profile.py` | RIO |
| M2 spoilage | `quality.py`, `engine.py`, `models.py`, `test_validation.py` | GAB |
| M3 optimizer | `cost.py`, `optimizer.py`, `toll_table.py`, `scenarios.py`, `review_gab_validation.py` | DAVIN |
| Glue | `pipeline.py`, `demo.py` | shared |
| Data | `data/tarif_tol_jawa.csv` | DAVIN (source: BPJT) |

## Running it

### Local (Python 3.11+)

```bash
python -m venv venv && source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
python demo.py            # full-chain demo, Jakarta→Bandung (reefer vs non-reefer)
```

### Docker

```bash
docker compose up --build
```

Runs `demo.py` inside the container as proof of local reproducibility. CATH swaps the
`command` in `docker-compose.yml` for their UI service when ready.

### Other commands

```bash
python scenarios.py             # what-if: reefer/non-reefer, departure time, preference
python test_validation.py       # sanity checks for the spoilage model (M2) — FAO benchmark, etc.
python review_gab_validation.py # cross-module review of M2 from M3's perspective
```

## Using it from UI/agent code (CATH)

```python
import pipeline
from contracts import TripRequest
from datetime import datetime

pipeline.configure_cost(golongan="II_III")   # CDD truck; use "I" for pickup / small truck

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
Each `RouteOption`: `.route`, `.quality`, `.cost`, `.score`, `.meets_deadline` — all
dataclasses, so `dataclasses.asdict(...)` → JSON works directly for the frontend.

## Network dependencies & demo resilience

`routing.py` and `temp_profile.py` call **OSRM** (routing) and **Open-Meteo** (weather) live.
Both are free and keyless. The public OSRM demo server is rate-limited (~1 req/sec), so there is
a **fallback fixture**: if the server is unreachable, the pipeline still returns ≥3 Jakarta–Bandung
candidates — the demo and the organizers' cross-check won't fail just because of the network.

## Binding principles (do not violate)

- **Physics-first, no trained ML.** Every number comes from an API or a transparent formula.
- **No IoT.** Cargo temperature is a scenario assumption (reefer setpoint / ambient), flagged in `source`.
- **The LLM narrates numbers, never invents them.** All values come from Python functions.
- **One spoilage model** (M2/GAB). No other module computes freshness on its own.
- **`contracts.py` is law.** Any change is announced to the group.

## Not yet final (for CATH's awareness)

- Static scenario parameters: toll class, fuel consumption & price (`pipeline.configure_cost`).
- Toll corridor map currently covers Jakarta–Bandung (`routing.CORRIDOR_TOLL`).
- ETA factors (`f_time` / `f_weather`) are still placeholders pending calibration.
- RIO's legacy modules (`main.py` FastAPI + MapKit frontend) are NOT included; UI ownership is
  still under discussion. This backend is the model layer, cleanly separated from the UI.
```
