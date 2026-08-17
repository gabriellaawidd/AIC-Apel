"""State object (ctx) — hanya bertambah, tak pernah ditimpa LLM."""
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class Request:
    commodity: str
    origin: Dict[str, Any]
    destination: Dict[str, Any]
    departure_time: str
    initial_condition: str = "segar"
    cargo_mode: str = "non_reefer"
    priority: str = "balanced"


@dataclass
class Route:
    route_id: str
    distance_km: float
    base_duration_min: float
    toll_cost: float
    geometry: str = ""


@dataclass
class Eta:
    optimistic_min: float
    likely_min: float
    pessimistic_min: float
    factors: Dict[str, float] = field(default_factory=dict)


@dataclass
class Spoilage:
    pct_fresh: float
    damage_fraction: float
    risk_level: str
    assumptions: List[str] = field(default_factory=list)


@dataclass
class Context:
    request: Optional[Request] = None
    routes: List[Route] = field(default_factory=list)
    weather: Dict[str, list] = field(default_factory=dict)
    eta: Dict[str, Eta] = field(default_factory=dict)
    spoilage: Dict[str, Spoilage] = field(default_factory=dict)
    ranking: Dict[str, Any] = field(default_factory=dict)
    advisory: Dict[str, Any] = field(default_factory=dict)
    assumptions: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "request": asdict(self.request) if self.request else None,
            "routes": [asdict(r) for r in self.routes],
            "eta": {k: asdict(v) for k, v in self.eta.items()},
            "spoilage": {k: asdict(v) for k, v in self.spoilage.items()},
            "ranking": self.ranking,
            "advisory": self.advisory,
            "assumptions": self.assumptions,
        }
