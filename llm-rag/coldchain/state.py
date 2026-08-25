
from dataclasses import dataclass, field
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
    deadline: Optional[str] = None


@dataclass
class Context:
    request: Optional[Request] = None
    plan: Dict[str, Any] = field(default_factory=dict)        
    explanations: List[Dict[str, Any]] = field(default_factory=list)  
    overview: str = ""
    llm_used: bool = False

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return {
            "request": asdict(self.request) if self.request else None,
            "plan": self.plan,
            "explanations": self.explanations,
            "overview": self.overview,
            "llm_used": self.llm_used,
        }

    @property
    def best_route_id(self) -> Optional[str]:
        return (self.plan or {}).get("best_route_id")
