
LOCATIONS = {
    "jakarta": {"label": "Jakarta", "lon": 106.8272, "lat": -6.1751},
    "bandung": {"label": "Bandung", "lon": 107.6098, "lat": -6.9147},
    "tangerang": {"label": "Tangerang", "lon": 106.6319, "lat": -6.1783},
    "cimahi": {"label": "Cimahi", "lon": 107.5413, "lat": -6.8841},
    "surabaya": {"label": "Surabaya", "lon": 112.7521, "lat": -7.2575},
    "semarang": {"label": "Semarang", "lon": 110.4203, "lat": -6.9932},
}

VALIDATED_TOLL_CORRIDORS = {frozenset({"jakarta", "bandung"})}


def is_validated_corridor(origin_key: str, destination_key: str) -> bool:
    return frozenset({origin_key, destination_key}) in VALIDATED_TOLL_CORRIDORS
