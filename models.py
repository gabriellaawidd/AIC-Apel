from dataclasses import dataclass, field
from typing import List, Dict, Literal

@dataclass
class Citation:
    label: str
    url: str

@dataclass
class CommodityModel:
    label: str
    model_type: Literal["rrs_tropical", "arrhenius"]
    ref_temp_c: float
    shelf_life_ref: float
    q10_reference: str
    sources: List[Citation] = field(default_factory=list)
    
    rrs_coefficient: float = None
    activation_energy: float = None

GAS_CONSTANT = 8.314 

COMMODITY_DB: Dict[str, CommodityModel] = {
    "fish": CommodityModel(
        label="Fresh fish (Pangasius)",
        model_type="rrs_tropical",
        ref_temp_c=1.0,          
        shelf_life_ref=9.0,     
        rrs_coefficient=0.18,   
        q10_reference="Fit dari data TVC pangasius (Mai & Huynh 2017), b=0.18/C",
        sources=[
            Citation("Mai & Huynh 2017 - J. Food Quality", "https://doi.org/10.1155/2017/2865185"),
            Citation("Bao 2006 - QIM pangasius shelf life", "https://www.globalseafood.org/advocate/qim-method-scores-quality-shelf-life-of-pangasius-fillets/")
        ]
    ),
    "leafy_greens": CommodityModel(
        label="Spinach",
        model_type="arrhenius",
        ref_temp_c=4.0,
        shelf_life_ref=18.0,
        activation_energy=79000.0,
        q10_reference="Ea 79 kJ/mol (Kaur et al. 2011)",
        sources=[
            Citation("HortTechnology 2015", "https://journals.ashs.org/view/journals/horttech/25/5/article-p665.xml"),
            Citation("Kaur et al. 2011", "https://onlinelibrary.wiley.com/doi/10.1111/j.1745-4530.2009.00508.x")
        ]
    ),
    "potato": CommodityModel(
        label="Potato",
        model_type="arrhenius",
        ref_temp_c=5.0,
        shelf_life_ref=150.0,
        activation_energy=48000.0,
        q10_reference="Q10=2, valid 5-25C (FAO)",
        sources=[
            Citation("FAO - Storability", "https://www.fao.org/4/x5415e/x5415e02.htm")
        ]
    )
}

INITIAL_CONDITION_MAP = {
    "sangat_segar": 1.00,
    "segar": 0.85,
    "kurang_segar": 0.65,
}

RISK_LEVEL_THRESHOLDS = (0.3, 0.7)
RISK_MIDPOINT_USED = 0.85
RISK_STEEPNESS = 8.0