from __future__ import annotations

import os

DEFAULT_MODEL = os.environ.get("CC_MODEL", "gemini-2.5-flash")
NARRATE_TEMPERATURE = 0.3
NARRATE_MAX_TOKENS = 1400

RAG_TOP_K = 4
RAG_MIN_SCORE = 0.05
RAG_COMMODITY_BOOST = 1.15


def preference_weights(preference: str) -> dict:
    from .tools import backend_available
    if backend_available():
        from optimizer import PREFERENCE_WEIGHTS
        w = PREFERENCE_WEIGHTS.get(preference, PREFERENCE_WEIGHTS["balanced"])
        return {"eta": w[0], "cost": w[1], "risk": w[2]}
    return {"eta": 0.34, "cost": 0.33, "risk": 0.33}
