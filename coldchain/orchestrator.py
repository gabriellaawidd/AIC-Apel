"""Orchestrator — LLM ON RAILS.

Urutan ditetapkan kode (deterministik): parse -> rute -> cuaca -> ETA -> spoilage
-> ranking -> advisory(RAG) -> narasi. LLM hanya di parse & narrate.
State object hanya bertambah; angka tidak pernah dari LLM.
"""
from __future__ import annotations
from typing import Dict, Any

from . import tools, llm
from .rag import KnowledgeBase, retrieve_advisory
from .state import Context, Request


class Orchestrator:
    def __init__(self, kb: KnowledgeBase = None):
        self.kb = kb or KnowledgeBase()

    def run(self, user_text: str, now: str = None, verbose: bool = False) -> Dict[str, Any]:
        ctx = Context()
        log = (lambda m: print(m)) if verbose else (lambda m: None)

        # (0) LLM — parsing
        req = llm.parse_request(user_text, now=now)
        ctx.request = Request(**req)
        log(f"[0] parse -> {ctx.request.commodity} {ctx.request.origin['name']}→"
            f"{ctx.request.destination['name']} ({ctx.request.cargo_mode}, {ctx.request.priority})")

        # (1) KODE — rute (OSRM)
        ctx.routes = tools.get_routes(ctx.request.origin, ctx.request.destination)
        log(f"[1] rute -> {len(ctx.routes)} kandidat")

        metrics = []
        for r in ctx.routes:
            # (2) cuaca
            segs = tools.get_weather(r, ctx.request.departure_time)
            ctx.weather[r.route_id] = segs
            # (3) ETA
            e = tools.estimate_eta(r.base_duration_min, ctx.request.departure_time, segs)
            ctx.eta[r.route_id] = e
            # (4) spoilage (RRS)
            sp = tools.compute_spoilage(ctx.request.commodity, ctx.request.initial_condition,
                                        ctx.request.cargo_mode, segs, e.likely_min)
            ctx.spoilage[r.route_id] = sp
            metrics.append({"route_id": r.route_id, "eta": e.likely_min,
                            "cost": r.toll_cost + r.distance_km * 2500,  # proxy biaya
                            "risk": round(100 - sp.pct_fresh, 2)})
        log(f"[3-4] ETA & spoilage dihitung untuk semua rute")

        # (5) KODE — ranking (Pareto + weighted)
        ctx.ranking = tools.rank_routes(metrics, ctx.request.priority)
        best = ctx.ranking["best_route_id"]
        log(f"[5] ranking -> best={best}, pareto={ctx.ranking['pareto_front']}")

        # kumpulkan asumsi dari rute terbaik
        ctx.assumptions = list(dict.fromkeys(ctx.spoilage[best].assumptions))

        # (6) RAG — advisory
        ctx.advisory = retrieve_advisory(self.kb, ctx.request.commodity,
                                         ctx.spoilage[best].risk_level)
        log(f"[6] advisory -> {len(ctx.advisory.get('snippets', []))} snippet"
            f"{' (fallback)' if ctx.advisory.get('fallback') else ''}")

        # (7) LLM — narasi (angka dari ctx saja)
        ctx_dict = ctx.to_dict()
        narrative = llm.narrate(ctx_dict)
        log("[7] narasi dibuat")

        return {"ctx": ctx_dict, "narrative": narrative, "best_route_id": best}


def run(user_text: str, **kw) -> Dict[str, Any]:
    return Orchestrator().run(user_text, **kw)
