from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(usecwd=True))
except Exception:
    pass

import logging
import sys as _sys

log = logging.getLogger("coldchain")
if not log.handlers:
    _h = logging.StreamHandler(_sys.stdout)
    _h.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-4s  %(message)s", "%H:%M:%S"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)
    log.propagate = False

import dashboard_export
import geocode
import pipeline
import routing
from contracts import TripRequest
from locations import LOCATIONS
from models import COMMODITY_DB

app = FastAPI(
    title="Cold Chain AI API",
    description="Decision-support backend (M1 routing + M2 spoilage + M3 cost/ranking) "
                "untuk pengiriman kargo mudah rusak — lapisan HTTP untuk frontend React.",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Place(BaseModel):
    label: str
    lon: float
    lat: float
    address: str = ""
    key: str = ""


class PlanRequest(BaseModel):
    origin_key: Optional[str] = Field(None, description="Kunci preset, mis. 'jakarta'")
    destination_key: Optional[str] = None
    origin: Optional[Place] = None
    destination: Optional[Place] = None

    commodity: str = Field(..., description="ikan_segar | bayam | kentang")
    departure_time: datetime
    vehicle: Literal["reefer", "non_reefer"] = "non_reefer"
    preference: Literal["fast", "cheap", "balanced"] = "balanced"
    deadline: Optional[datetime] = None
    initial_condition: Literal["sangat_segar", "segar", "kurang_segar"] = "segar"
    golongan: Literal["I", "II_III", "IV_V"] = "II_III"

    @model_validator(mode="after")
    def _need_endpoints(self):
        if not (self.origin or self.origin_key):
            raise ValueError("Isi `origin` (hasil /api/geocode) atau `origin_key` (preset).")
        if not (self.destination or self.destination_key):
            raise ValueError("Isi `destination` atau `destination_key`.")
        return self


def _resolve_place(place: Optional[Place], key: Optional[str], sisi: str) -> Dict[str, Any]:
    if place is not None:
        return {"key": place.key or f"free:{place.lat:.5f},{place.lon:.5f}",
                "label": place.label, "lon": place.lon, "lat": place.lat,
                "address": place.address}
    loc = LOCATIONS.get(key)
    if loc is None:
        raise HTTPException(
            status_code=400,
            detail=f"Lokasi {sisi} tidak dikenal: {key!r}. Tersedia: {sorted(LOCATIONS)}",
        )
    return {"key": key, "label": loc["label"], "lon": loc["lon"], "lat": loc["lat"],
            "address": loc["label"]}


def _too_close(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return abs(a["lon"] - b["lon"]) < 1e-4 and abs(a["lat"] - b["lat"]) < 1e-4


def _augment_with_geometry(payload: dict, result) -> dict:

    by_id = {o.route.route_id: o for o in result.all_options}
    for opt in payload.get("options", []):
        src = by_id.get(opt["route_id"])
        if src is None:
            continue
        opt["geometry"] = src.route.geometry
        opt["assumptions"] = src.route.assumptions
        opt["toll_segments"] = src.route.toll_segments
    return payload


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/meta")
def meta():
    return {
        "commodities": [
            {
                "key": key,
                "label": m.label,
                "shelf_life_ref_days": m.shelf_life_ref,
                "sellable_min_pct": m.sellable_min_pct,
                "mechanism": m.mechanism,
                "needs_approval": m.needs_approval,
            }
            for key, m in COMMODITY_DB.items()
        ],
        "vehicles": [
            {"key": "non_reefer", "label": "Truk biasa (non-reefer)"},
            {"key": "reefer", "label": "Truk berpendingin (reefer)"},
        ],
        "preferences": [
            {"key": "fast", "label": "Prioritaskan Kecepatan",
             "hint": "Bobot terbesar pada waktu tempuh (jam) — rute dengan km/jam tertinggi menang."},
            {"key": "cheap", "label": "Prioritaskan Biaya",
             "hint": "Bobot terbesar pada biaya total (tarif tol + BBM)."},
            {"key": "balanced", "label": "Seimbang",
             "hint": "Waktu, biaya, dan risiko busuk dibobot hampir sama rata."},
        ],
        "initial_conditions": [
            {"key": "sangat_segar", "label": "Sangat segar"},
            {"key": "segar", "label": "Segar"},
            {"key": "kurang_segar", "label": "Kurang segar"},
        ],
        "locations": [
            {"key": key, "label": loc["label"], "lon": loc["lon"], "lat": loc["lat"]}
            for key, loc in LOCATIONS.items()
        ],
        "geocoding": {
            "enabled": True,
            "endpoint": "/api/geocode",
            "provider": "OpenStreetMap Nominatim",
            "mapkit_endpoint": "/api/mapkit-token",
            "mapkit_enabled": bool(os.environ.get("MAPKIT_JS_TOKEN", "")),
        },
    }


def _klaim_mapkit(token: str) -> dict:
    """Baca klaim `origin` dan `exp` dari token MapKit — TANPA memverifikasi tanda tangan.

    Tujuannya semata diagnosis. MapKit menolak halaman yang origin-nya tidak
    cocok dengan klaim `origin` di token, dan penolakan itu datang asinkron
    tanpa pesan yang jelas di UI. Dengan mengirim klaimnya ke frontend, pesan
    kegagalannya bisa menyebut sebab yang sebenarnya.
    """
    import base64, json, time

    try:
        bagian = token.split(".")[1]
        bagian += "=" * (-len(bagian) % 4)
        p = json.loads(base64.urlsafe_b64decode(bagian))
    except Exception:
        return {}
    exp = p.get("exp")
    return {
        "origin": p.get("origin"),
        "expired": bool(exp and exp < time.time()),
    }


@app.get("/api/mapkit-token")
def mapkit_token():


    token = os.environ.get("MAPKIT_JS_TOKEN", "")
    if not token:
        return {
            "enabled": False,
            "reason": "MAPKIT_JS_TOKEN belum diset. Frontend otomatis memakai "
                      "pencarian OpenStreetMap (/api/geocode) sebagai gantinya.",
        }
    return {"enabled": True, "token": token, **_klaim_mapkit(token)}


@app.get("/api/geocode")
def geocode_search(q: str = Query(..., min_length=3, description="Nama tempat/alamat"),
                   limit: int = Query(6, ge=1, le=10)):
    hits = geocode.search(q, limit=limit)
    if not hits:
        ql = q.strip().lower()
        hits = [
            {"key": key, "label": loc["label"], "address": loc["label"],
             "lon": loc["lon"], "lat": loc["lat"], "kind": "preset"}
            for key, loc in LOCATIONS.items() if ql in loc["label"].lower()
        ]
        return {
            "results": hits,
            "source": "preset_fallback",
            "error": geocode.galat_terakhir(),
        }
    return {"results": hits, "source": geocode.penyedia_terakhir(), "error": geocode.galat_terakhir()}


@app.post("/api/plan")
def plan(req: PlanRequest):
    origin = _resolve_place(req.origin, req.origin_key, "asal")
    destination = _resolve_place(req.destination, req.destination_key, "tujuan")

    if _too_close(origin, destination):
        raise HTTPException(status_code=400, detail="Asal dan tujuan tidak boleh sama.")

    log.info("→ /api/plan  %s → %s  | %s | %s | prioritas=%s | gol=%s",
             origin.get("label", origin.get("lon")), destination.get("label", destination.get("lon")),
             req.commodity, req.vehicle, req.preference, req.golongan)

    pipeline.configure_cost(golongan=req.golongan)

    trip = TripRequest(
        origin=(origin["lon"], origin["lat"]),
        destination=(destination["lon"], destination["lat"]),
        commodity=req.commodity,
        departure_time=req.departure_time,
        vehicle=req.vehicle,
        preference=req.preference,
        deadline=req.deadline,
        initial_condition=req.initial_condition,
    )

    log.info("  M1/M2/M3 pipeline dijalankan (rute → suhu → spoilage → biaya → ranking)…")
    try:
        result = pipeline.run_pipeline(trip)
    except ValueError as e:
        log.warning("  pipeline gagal: %s", e)
        raise HTTPException(status_code=400, detail=str(e)) from e

    if result.best:
        b = result.best
        log.info("  ✓ %d rute | terbaik=%s | fresh=%.1f%% | Rp%s | ETA≈%.1fj",
                 len(result.all_options), b.route.route_id, b.quality.pct_fresh,
                 f"{b.cost.total_cost_rp:,.0f}", b.route.eta_hours_likely)
    log.info("← /api/plan selesai")

    payload = dashboard_export.to_dashboard_payload(result, req=trip)
    payload = _augment_with_geometry(payload, result)
    payload["request_echo"] = {
        "origin": origin,
        "destination": destination,
        "commodity": req.commodity,
        "vehicle": req.vehicle,
        "preference": req.preference,
        "departure_time": req.departure_time.isoformat(),
        "deadline": req.deadline.isoformat() if req.deadline else None,
        "initial_condition": req.initial_condition,
        "golongan": req.golongan,
        "toll_corridor_validated": routing._validated_corridor(trip) is not None,
    }
    return payload


_LLM_RAG_DIR = Path(__file__).resolve().parent.parent / "llm-rag"
if str(_LLM_RAG_DIR) not in sys.path:
    sys.path.insert(0, str(_LLM_RAG_DIR))


class ExplainRequest(BaseModel):

    payload: Dict[str, Any]
    use_llm: bool = True


@app.post("/api/explain")
def explain(req: ExplainRequest):
    log.info("→ /api/explain  use_llm=%s  (lapisan AI: parse + narasi Gemini + RAG)", req.use_llm)
    try:
        from coldchain.explain import explain_payload
    except Exception as e:
        log.warning("  modul llm-rag gagal dimuat: %s", e)
        raise HTTPException(
            status_code=503,
            detail=f"Modul penjelasan (llm-rag) tidak bisa dimuat: {e}",
        ) from e
    result = explain_payload(req.payload, use_llm=req.use_llm)
    log.info("← /api/explain  llm_used=%s (Gemini)  | %d rute dijelaskan",
             result.get("llm_used"), len(result.get("routes", [])))
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
