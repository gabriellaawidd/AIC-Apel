"""Lapisan LLM (hanya di ujung: parsing & narasi) — backend GEMINI.

Prinsip: LLM tidak pernah menghasilkan angka. `parse_request` mengubah teks ->
parameter (via function calling Gemini bila API tersedia), `narrate` menarasikan
ctx dengan instruksi eksplisit mengutip angka apa adanya.

Jika GEMINI_API_KEY (atau GOOGLE_API_KEY) tersedia -> pakai function calling asli.
Jika tidak -> fallback deterministik (rule-based parser + template narrator)
supaya demo tetap jalan offline.

Setup:
    pip install google-genai
    export GEMINI_API_KEY=...
    export CC_MODEL=gemini-2.5-flash   # opsional (default), bisa gemini-3.6-flash
"""
from __future__ import annotations
import os
import re
import json
from datetime import datetime
from typing import Dict, Any

DEFAULT_MODEL = "gemini-2.5-flash"

# --- Skema parameter untuk function calling parse_request (OpenAPI-style) ---
PARSE_PARAMS = {
    "type": "object",
    "properties": {
        "commodity": {"type": "string", "description": "Komoditas, mis. ikan segar, udang, sayur daun"},
        "origin": {"type": "object", "properties": {"name": {"type": "string"}}},
        "destination": {"type": "object", "properties": {"name": {"type": "string"}}},
        "departure_time": {"type": "string", "description": "ISO 8601"},
        "initial_condition": {"type": "string", "enum": ["sangat_segar", "segar", "kurang_segar"]},
        "cargo_mode": {"type": "string", "enum": ["reefer", "non_reefer"]},
        "priority": {"type": "string", "enum": ["fast", "cheap", "balanced"]},
    },
    "required": ["commodity", "origin", "destination"],
}


def _model() -> str:
    return os.environ.get("CC_MODEL", DEFAULT_MODEL)


def _has_api() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


def _to_py(obj):
    """Konversi struktur hasil Gemini (Map/List composite) ke dict/list Python murni."""
    if isinstance(obj, dict):
        return {k: _to_py(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_py(v) for v in obj]
    if hasattr(obj, "items"):
        return {k: _to_py(v) for k, v in obj.items()}
    return obj


# --------------------------------------------------------------------------
# parse_request
# --------------------------------------------------------------------------
def parse_request(user_text: str, now: str = None) -> Dict[str, Any]:
    now = now or datetime.now().isoformat(timespec="minutes")
    if _has_api():
        try:
            return _parse_gemini(user_text, now)
        except Exception as e:  # fallback aman
            print(f"[llm] parse fallback ({e})")
    return _parse_rule(user_text, now)


def _parse_gemini(user_text: str, now: str) -> Dict[str, Any]:
    from google import genai
    from google.genai import types

    client = genai.Client()  # membaca GEMINI_API_KEY / GOOGLE_API_KEY
    tool = types.Tool(function_declarations=[{
        "name": "parse_request",
        "description": "Ubah kalimat pengguna menjadi parameter pengiriman terstruktur. Tidak menghitung apa pun.",
        "parameters": PARSE_PARAMS,
    }])
    config = types.GenerateContentConfig(
        tools=[tool],
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(
                mode="ANY", allowed_function_names=["parse_request"])),
        temperature=0,
    )
    resp = client.models.generate_content(
        model=_model(),
        contents=f"Waktu sekarang: {now}. Ekstrak parameter dari kalimat berikut: {user_text}",
        config=config,
    )
    for part in resp.candidates[0].content.parts:
        fc = getattr(part, "function_call", None)
        if fc and fc.name == "parse_request":
            return _fill_defaults(_to_py(fc.args), now)
    raise RuntimeError("no function_call returned")


_CITIES = ["jakarta", "bandung", "surabaya", "semarang", "yogyakarta", "medan",
           "makassar", "denpasar", "bogor", "bekasi", "cirebon", "solo"]


def _parse_rule(user_text: str, now: str) -> Dict[str, Any]:
    t = user_text.lower()
    commodity = "ikan"
    for c in ["kentang", "potato", "bayam", "spinach", "sayur", "ikan", "fish"]:
        if c in t:
            commodity = {"potato": "kentang", "spinach": "bayam",
                         "sayur": "bayam", "fish": "ikan"}.get(c, c)
            break
    m = re.search(r"dari\s+([a-z]+)\s+ke\s+([a-z]+)", t)
    if m:
        origin, dest = m.group(1), m.group(2)
    else:
        found = [c for c in _CITIES if c in t]
        origin = found[0] if found else "jakarta"
        dest = found[1] if len(found) > 1 else "bandung"
    cond = "segar"
    if "sangat segar" in t: cond = "sangat_segar"
    elif "kurang segar" in t: cond = "kurang_segar"
    if "non-reefer" in t or "non reefer" in t or "tanpa pendingin" in t:
        cargo = "non_reefer"
    elif "reefer" in t or "berpendingin" in t:
        cargo = "reefer"
    else:
        cargo = "non_reefer"
    prio = "fast" if "cepat" in t else "cheap" if "hemat" in t or "murah" in t else "balanced"
    return _fill_defaults({
        "commodity": commodity,
        "origin": {"name": origin.title()},
        "destination": {"name": dest.title()},
        "initial_condition": cond, "cargo_mode": cargo, "priority": prio,
    }, now)


def _fill_defaults(d: Dict[str, Any], now: str) -> Dict[str, Any]:
    d = dict(d or {})
    d.setdefault("departure_time", now)
    d.setdefault("initial_condition", "segar")
    d.setdefault("cargo_mode", "non_reefer")
    d.setdefault("priority", "balanced")
    if isinstance(d.get("origin"), str):
        d["origin"] = {"name": d["origin"]}
    if isinstance(d.get("destination"), str):
        d["destination"] = {"name": d["destination"]}
    if not d.get("departure_time"):
        d["departure_time"] = now
    return d


# --------------------------------------------------------------------------
# narrate — angka HANYA dari ctx
# --------------------------------------------------------------------------
NARRATE_SYSTEM = (
    "Anda asisten logistik rantai dingin. Susun penjelasan singkat keputusan rute. "
    "ATURAN MUTLAK: jangan pernah membuat/menghitung angka sendiri. Kutip angka HANYA "
    "apa adanya dari data JSON yang diberikan. Sertakan saran penanganan dari 'advisory' "
    "beserta sumbernya. Bahasa Indonesia, ringkas."
)


def narrate(ctx_dict: Dict[str, Any]) -> str:
    if _has_api():
        try:
            return _narrate_gemini(ctx_dict)
        except Exception as e:
            print(f"[llm] narrate fallback ({e})")
    return _narrate_template(ctx_dict)


def _narrate_gemini(ctx_dict: Dict[str, Any]) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client()
    config = types.GenerateContentConfig(
        system_instruction=NARRATE_SYSTEM, temperature=0.3, max_output_tokens=700)
    resp = client.models.generate_content(
        model=_model(),
        contents="Data keputusan (JSON):\n" + json.dumps(ctx_dict, ensure_ascii=False),
        config=config,
    )
    return (resp.text or "").strip() or _narrate_template(ctx_dict)


def _narrate_template(ctx: Dict[str, Any]) -> str:
    req = ctx["request"]; rank = ctx["ranking"]; best = rank["best_route_id"]
    sp = ctx["spoilage"][best]; eta = ctx["eta"][best]
    route = next(r for r in ctx["routes"] if r["route_id"] == best)
    lines = []
    lines.append(f"Rekomendasi rute: {best} untuk {req['commodity']} "
                 f"({req['origin']['name']} → {req['destination']['name']}, "
                 f"prioritas {req['priority']}, {req['cargo_mode']}).")
    lines.append(f"Jarak {route['distance_km']} km. ETA {eta['likely_min']} menit "
                 f"(pita {eta['optimistic_min']}–{eta['pessimistic_min']} menit).")
    lines.append(f"Prediksi kesegaran saat tiba: {sp['pct_fresh']}% "
                 f"(risiko {sp['risk_level']}).")
    if rank.get("pareto_front"):
        lines.append(f"Rute non-dominated (Pareto): {', '.join(rank['pareto_front'])}.")
    adv = ctx.get("advisory", {})
    if adv.get("snippets"):
        lines.append("Saran penanganan:")
        for s in adv["snippets"][:2]:
            txt = s["text"][:180].rstrip() + ("…" if len(s["text"]) > 180 else "")
            lines.append(f"  • {txt} — [{s['source']}]")
    elif adv.get("note"):
        lines.append(f"Saran (fallback): {adv['note']}")
    if ctx.get("assumptions"):
        lines.append("Asumsi: " + "; ".join(ctx["assumptions"]) + ".")
    return "\n".join(lines)
