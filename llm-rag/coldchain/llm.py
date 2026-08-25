from __future__ import annotations
import os
import re
import json
from datetime import datetime
from typing import Dict, Any

try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(usecwd=True))
except Exception:
    pass

DEFAULT_MODEL = "gemini-3.6-flash"
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
    if isinstance(obj, dict):
        return {k: _to_py(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_py(v) for v in obj]
    if hasattr(obj, "items"):
        return {k: _to_py(v) for k, v in obj.items()}
    return obj

def parse_request(user_text: str, now: str = None) -> Dict[str, Any]:
    now = now or datetime.now().isoformat(timespec="minutes")
    if _has_api():
        try:
            return _parse_gemini(user_text, now)
        except Exception as e:
            print(f"[llm] parse fallback ({e})")
    return _parse_rule(user_text, now)


def _parse_gemini(user_text: str, now: str) -> Dict[str, Any]:
    from google import genai
    from google.genai import types

    client = genai.Client()
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


POLISH_SYSTEM = (
    "Anda editor bahasa untuk laporan logistik rantai dingin berbahasa Indonesia. "
    "Anda menerima penalaran yang SUDAH BENAR beserta angkanya. Tugas Anda HANYA "
    "membuat kalimatnya mengalir dan mudah dibaca operator gudang. "
    "DILARANG KERAS: mengubah, membulatkan, menambah, atau menghapus angka apa pun; "
    "menambahkan klaim baru; mengubah kesimpulan. "
    "Jangan memakai istilah teknis mentah (nama model, simbol rumus, singkatan "
    "seperti Ea/SL_ref/RRS) — jelaskan dengan kata sehari-hari. "
    "Balas HANYA JSON valid dengan bentuk: "
    '{"routes":[{"route_id":"...","reasoning":[{"aspect":"...","text":"..."}],'
    '"when_to_pick":"..."}]}'
)


def _extract_json(text: str) -> str:
    s = (text or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s).strip()
    i, j = s.find("{"), s.rfind("}")
    return s[i:j + 1] if (i != -1 and j != -1 and j > i) else (s or "{}")


def polish_explanations(routes, payload):
    if not _has_api() or not routes:
        return None
    try:
        from google import genai
        from google.genai import types

        ringkas = [{
            "route_id": r["route_id"],
            "name": r["name"],
            "reasoning": [{"aspect": a["aspect"], "text": a["text"]} for a in r["reasoning"]],
            "when_to_pick": r["when_to_pick"],
        } for r in routes]

        client = genai.Client()
        resp = client.models.generate_content(
            model=_model(),
            contents="Perhalus penalaran berikut tanpa mengubah satu pun angka:\n"
                     + json.dumps(ringkas, ensure_ascii=False),
            config=types.GenerateContentConfig(
                system_instruction=POLISH_SYSTEM,
                temperature=0.2,
                max_output_tokens=8192,
                response_mime_type="application/json",
            ),
        )
        data = json.loads(_extract_json(resp.text))
    except Exception as e:
        print(f"[llm] polish fallback ({e})")
        return None

    by_id = {r.get("route_id"): r for r in (data.get("routes") or [])}
    if set(by_id) != {r["route_id"] for r in routes}:
        return None

    out = []
    for r in routes:
        p = by_id[r["route_id"]]
        aspects = {a.get("aspect"): a.get("text") for a in (p.get("reasoning") or [])}
        if set(aspects) != {a["aspect"] for a in r["reasoning"]}:
            return None
        salinan = dict(r)
        salinan["reasoning"] = [
            {"aspect": a["aspect"], "text": aspects[a["aspect"]] or a["text"]}
            for a in r["reasoning"]
        ]
        salinan["when_to_pick"] = p.get("when_to_pick") or r["when_to_pick"]
        out.append(salinan)
    return out

def narrate(ctx_dict) -> str:
    baris = [ctx_dict.get("overview", "")]
    for r in ctx_dict.get("explanations", []):
        baris.append(f"\n## {r['name']}")
        baris.append(r.get("headline", ""))
        for a in r.get("reasoning", []):
            baris.append(f"  - {a['aspect']}: {a['text']}")
        if r.get("when_to_pick"):
            baris.append(f"  - Kapan dipakai: {r['when_to_pick']}")
        for s in (r.get("advisory") or [])[:1]:
            teks = s["text"][:180].rstrip() + ("…" if len(s["text"]) > 180 else "")
            baris.append(f"  - Saran penanganan: {teks} — [{s['source']}]")
    return "\n".join(b for b in baris if b)
