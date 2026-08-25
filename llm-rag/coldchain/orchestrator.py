from __future__ import annotations

from typing import Any, Dict

from . import llm, tools
from .explain import explain_payload
from .state import Context, Request


class Orchestrator:
    def __init__(self, kb=None):
        self._kb = kb

    def run(self, user_text: str, now: str = None, verbose: bool = False,
            use_llm: bool = True) -> Dict[str, Any]:
        ctx = Context()
        log = (lambda m: print(m)) if verbose else (lambda m: None)

        parsed = llm.parse_request(user_text, now=now)
        origin = tools.geocode_place(parsed["origin"]["name"]) or {
            "name": parsed["origin"]["name"], "lon": 106.8272, "lat": -6.1751}
        destination = tools.geocode_place(parsed["destination"]["name"]) or {
            "name": parsed["destination"]["name"], "lon": 107.6098, "lat": -6.9147}

        ctx.request = Request(
            commodity=parsed["commodity"],
            origin=origin, destination=destination,
            departure_time=parsed["departure_time"],
            initial_condition=parsed.get("initial_condition", "segar"),
            cargo_mode=parsed.get("cargo_mode", "non_reefer"),
            priority=parsed.get("priority", "balanced"),
        )
        log(f"[0-1] {ctx.request.commodity}: {origin['name']} -> {destination['name']} "
            f"({ctx.request.cargo_mode}, prioritas {ctx.request.priority})")

        ctx.plan = tools.plan_trip(
            origin=origin, destination=destination,
            commodity=_map_commodity(ctx.request.commodity),
            departure_time=ctx.request.departure_time,
            vehicle=ctx.request.cargo_mode,
            preference=ctx.request.priority,
            initial_condition=ctx.request.initial_condition,
        )
        log(f"[2] pipeline backend -> {len(ctx.plan.get('options', []))} rute, "
            f"terbaik={ctx.plan.get('best_route_id')}")

        hasil = explain_payload(ctx.plan, use_llm=use_llm)
        ctx.explanations = hasil["routes"]
        ctx.overview = hasil["overview"]
        ctx.llm_used = hasil["llm_used"]
        log(f"[3-5] penalaran untuk {len(ctx.explanations)} rute "
            f"({'LLM' if ctx.llm_used else 'template'})")

        return {
            "ctx": ctx.to_dict(),
            "best_route_id": ctx.best_route_id,
            "overview": ctx.overview,
            "explanations": ctx.explanations,
        }

_COMMODITY_MAP = {
    "ikan": "ikan_segar", "ikan segar": "ikan_segar", "fish": "ikan_segar",
    "bayam": "bayam", "spinach": "bayam", "sayur": "bayam",
    "kentang": "kentang", "potato": "kentang",
}


def _map_commodity(name: str) -> str:
    return _COMMODITY_MAP.get((name or "").strip().lower(), name)


def run(user_text: str, **kw) -> Dict[str, Any]:
    return Orchestrator().run(user_text, **kw)
