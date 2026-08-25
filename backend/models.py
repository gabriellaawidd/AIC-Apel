


from dataclasses import dataclass, field
from typing import List, Dict, Literal, Optional

ModelType = Literal["rrs_square_root", "arrhenius"]
Mechanism = Literal["mikrobial", "respirasi"]


@dataclass
class Citation:
    label: str
    url: str


@dataclass
class CommodityModel:
    label: str
    model_type: ModelType
    mechanism: Mechanism
    ref_temp_c: float
    shelf_life_ref: float
    calibration_note: str
    sources: List[Citation] = field(default_factory=list)

    tmin_c: Optional[float] = None
    activation_energy: Optional[float] = None

    sellable_min_pct: float = 60.0

    needs_approval: bool = False

    def __post_init__(self):

        if self.model_type == "rrs_square_root" and self.tmin_c is None:
            raise ValueError(f"{self.label}: model square-root wajib punya tmin_c")
        if self.model_type == "arrhenius" and self.activation_energy is None:
            raise ValueError(f"{self.label}: model arrhenius wajib punya activation_energy")
        if not self.sources:
            raise ValueError(f"{self.label}: setiap komoditas wajib punya sumber")


GAS_CONSTANT = 8.314


COMMODITY_DB: Dict[str, CommodityModel] = {

    "ikan_segar": CommodityModel(
        label="Ikan segar (Pangasius)",
        model_type="rrs_square_root",
        mechanism="mikrobial",
        ref_temp_c=1.0,
        shelf_life_ref=9.0,
        tmin_c=-10.0,
        calibration_note=(
            "Ratkowsky square-root, Tmin=-10C (nilai baku Pseudomonas/Shewanella "
            "pada SSSP-DTU). SL_ref 9 hari @1C dari data TVC pangasius."
        ),
        sources=[
            Citation("Mai & Huynh 2017 - J. Food Quality",
                     "https://doi.org/10.1155/2017/2865185"),
            Citation("Bao 2006 - QIM pangasius shelf life",
                     "https://www.globalseafood.org/advocate/qim-method-scores-quality-shelf-life-of-pangasius-fillets/"),
        ],
    ),

    "bayam": CommodityModel(
        label="Bayam",
        model_type="arrhenius",
        mechanism="respirasi",
        ref_temp_c=4.0,
        shelf_life_ref=18.0,
        activation_energy=79000.0,
        calibration_note="Ea 79 kJ/mol (Kaur et al. 2011) -> Q10 = 3,30 pada 4-14C",
        sources=[
            Citation("HortTechnology 2015",
                     "https://journals.ashs.org/view/journals/horttech/25/5/article-p665.xml"),
            Citation("Kaur et al. 2011",
                     "https://onlinelibrary.wiley.com/doi/10.1111/j.1745-4530.2009.00508.x"),
        ],
        needs_approval=True,
    ),

    "kentang": CommodityModel(
        label="Kentang",
        model_type="arrhenius",
        mechanism="respirasi",
        ref_temp_c=5.0,
        shelf_life_ref=150.0,
        activation_energy=48000.0,
        calibration_note="Ea 48 kJ/mol -> Q10 = 2,06 pada 5-15C, cocok dgn FAO (Q10=2)",
        sources=[
            Citation("FAO - Storability",
                     "https://www.fao.org/4/x5415e/x5415e02.htm"),
        ],
        needs_approval=True,
    ),
}

COMMODITY_ALIASES = {
    "fish": "ikan_segar",
    "leafy_greens": "bayam",
    "potato": "kentang",
}


def resolve_commodity(key: str) -> CommodityModel:
    k = COMMODITY_ALIASES.get(key, key)
    if k not in COMMODITY_DB:
        raise ValueError(
            f"Komoditas tidak dikenal: {key!r}. "
            f"Tersedia: {sorted(COMMODITY_DB)} (alias: {sorted(COMMODITY_ALIASES)})"
        )
    return COMMODITY_DB[k]


INITIAL_CONDITION_MAP = {
    "sangat_segar": 1.00,
    "segar": 0.85,
    "kurang_segar": 0.65,
}

RISK_MIDPOINT = 0.50
RISK_STEEPNESS = 8.0
RISK_LEVEL_THRESHOLDS = (0.3, 0.7)
