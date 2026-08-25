


from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional, Tuple


ROAD_ALIASES: List[Tuple[str, str]] = [
    ("jagorawi",                    "Jakarta-Bogor-Ciawi"),
    ("jakarta-bogor",               "Jakarta-Bogor-Ciawi"),
    ("sedyatmo",                    "Prof.Dr.Ir.Soedijatmo"),
    ("soedijatmo",                  "Prof.Dr.Ir.Soedijatmo"),
    ("cawang-tomang",               "Cawang-Tomang-Pluit (CTC)"),
    ("dalam kota",                  "Cawang-Tomang-Pluit (CTC)"),
    ("jorr s",                      "JORR S"),
    ("jorr w1",                     "JORR W1 (Kebon Jeruk-Penjaringan)"),
    ("jorr w2",                     "JORR W2 Utara (Kebon Jeruk-Ulujami)"),
    ("jorr",                        "JORR NON S"),
    ("lingkar luar",                "JORR NON S"),
    ("becakayu",                    "Bekasi-Cawang-Kampung Melayu"),
    ("bekasi-cawang",               "Bekasi-Cawang-Kampung Melayu"),
    ("desari",                      "Depok-Antasari"),
    ("depok-antasari",              "Depok-Antasari"),
    ("cijago",                      "Cinere-Jagorawi"),
    ("cinere-jagorawi",             "Cinere-Jagorawi"),
    ("cimanggis-cibitung",          "Cimanggis-Cibitung Seksi 2B"),
    ("cibitung-cilincing",          "Cibitung - Cilincing Seksi 2 &3"),
    ("cengkareng-batu ceper",       "Cengkareng-Batu Ceper-Kunciran"),
    ("kunciran-serpong",            "Kunciran-Serpong"),
    ("serpong-cinere",              "Serpong-Cinere Seksi 1 dan 2"),
    ("pondok aren-serpong",         "Pondok Aren-Serpong"),
    ("bintaro",                     "Pondok Aren-Bintaro Viaduct-Ulujami"),
    ("bogor ring road",             "Bogor Ring Road Seksi I-IIIA (Sentul Selatan-Simpang Semplak)"),
    ("bogor outer ring",            "Bogor Ring Road Seksi I-IIIA (Sentul Selatan-Simpang Semplak)"),
    ("jakarta-tangerang",           "Jakarta-Tangerang"),
    ("tangerang-merak",             "Tangerang-Merak"),
    ("merak",                       "Tangerang-Merak"),
    ("serang-panimbang",            "Serang-Panimbang Seksi 1 (Serang-Rangkasbitung)"),
    ("serpong-balaraja",            "Serpong-Balaraja Seksi 1 (Serpong-SS Legok)"),

    ("jakarta-cikampek",            "Jakarta-Cikampek dan Jakarta -Cikampek II Elevated"),
    ("jakarta - cikampek",          "Jakarta-Cikampek dan Jakarta -Cikampek II Elevated"),
    ("japek",                       "Jakarta-Cikampek dan Jakarta -Cikampek II Elevated"),
    ("cikopo-palimanan",            "Cikampek-Palimanan"),
    ("cikopo - palimanan",          "Cikampek-Palimanan"),
    ("cipali",                      "Cikampek-Palimanan"),
    ("cikampek-palimanan",          "Cikampek-Palimanan"),
    ("palimanan-kanci",             "Palimanan-Kanci"),
    ("palikanci",                   "Palimanan-Kanci"),
    ("kanci-pejagan",               "Kanci-Pejagan"),
    ("pejagan-pemalang",            "Pejagan-Pemalang"),
    ("pemalang-batang",             "Pemalang-Batang"),
    ("batang-semarang",             "Semarang-Batang"),
    ("semarang-batang",             "Semarang-Batang"),
    ("semarang-solo",               "Semarang-Solo"),
    ("solo-ngawi",                  "Solo-Ngawi"),
    ("ngawi-kertosono",             "Ngawi-Kertosono"),
    ("kertosono-mojokerto",         "Kertosono-Mojokerto"),
    ("mojokerto-surabaya",          "Surabaya-Mojokerto"),
    ("surabaya-mojokerto",          "Surabaya-Mojokerto"),
    ("surabaya-gempol",             "Surabaya-Gempol"),
    ("gempol-pasuruan",             "Gempol-Pasuruan"),
    ("gempol-pandaan",              "Gempol-Pandaan"),
    ("pandaan-malang",              "Pandaan-Malang"),
    ("pasuruan-probolinggo",        "Pasuruan-Probolinggo Seksi I - IVA"),
    ("surabaya-gresik",             "Surabaya-Gresik"),
    ("krian",                       "Krian–Legundi–Bunder–Manyar (Krian–Legundi–Bunder)"),
    ("semarang-demak",              "Semarang-Demak Seksi 2 (Sayung-Demak)"),
    ("solo-yogyakarta",             "Solo-Yogyakarta-NYIA Kulon Progo"),
    ("jogja",                       "Solo-Yogyakarta-NYIA Kulon Progo"),

    ("purbaleunyi",                 "Cikampek-Padalarang"),
    ("cipularang",                  "Cikampek-Padalarang"),
    ("cikampek-padalarang",         "Cikampek-Padalarang"),
    ("padalarang-cileunyi",         "Padalarang-Cileunyi"),
    ("padaleunyi",                  "Padalarang-Cileunyi"),
    ("cisumdawu",                   "Cileunyi-Sumedang-Dawuan 1,2,3"),
    ("cileunyi-sumedang",           "Cileunyi-Sumedang-Dawuan 1,2,3"),
    ("soroja",                      "Soreang-Pasir Koja"),
    ("soreang",                     "Soreang-Pasir Koja"),
    ("bocimi",                      "Ciawi-Sukabumi"),
    ("ciawi-sukabumi",              "Ciawi-Sukabumi"),
]

COMPOSITE_ROADS: Dict[str, List[str]] = {
    "purbaleunyi": ["Cikampek-Padalarang", "Padalarang-Cileunyi"],
}


RUAS_LENGTH_KM: Dict[str, float] = {
    "Jakarta-Cikampek dan Jakarta -Cikampek II Elevated": 83.0,
    "Cikampek-Padalarang": 58.5,
    "Padalarang-Cileunyi": 64.4,
    "Cikampek-Palimanan": 116.8,
    "Palimanan-Kanci": 26.3,
    "Kanci-Pejagan": 35.0,
    "Pejagan-Pemalang": 57.5,
    "Pemalang-Batang": 39.2,
    "Semarang-Batang": 75.0,
    "Semarang-Solo": 72.6,
    "Solo-Ngawi": 90.4,
    "Ngawi-Kertosono": 87.0,
    "Kertosono-Mojokerto": 40.5,
    "Surabaya-Mojokerto": 36.3,
    "Surabaya-Gempol": 49.0,
    "Gempol-Pasuruan": 34.2,
    "Gempol-Pandaan": 13.6,
    "Pandaan-Malang": 38.5,
    "Pasuruan-Probolinggo Seksi I - IVA": 31.3,
    "Surabaya-Gresik": 20.7,
    "Tangerang-Merak": 72.5,
    "Jakarta-Tangerang": 33.0,
    "Jakarta-Bogor-Ciawi": 59.0,
    "Prof.Dr.Ir.Soedijatmo": 14.3,
    "Cileunyi-Sumedang-Dawuan 1,2,3": 30.8,
    "Cileunyi-Sumedang-Dawuan 4,5,6": 30.8,
    "Ciawi-Sukabumi": 27.0,
    "Soreang-Pasir Koja": 10.6,
    "Solo-Yogyakarta-NYIA Kulon Progo": 42.0,
    "Semarang-Demak Seksi 2 (Sayung-Demak)": 16.3,
    "Krian–Legundi–Bunder–Manyar (Krian–Legundi–Bunder)": 29.0,
    "Serang-Panimbang Seksi 1 (Serang-Rangkasbitung)": 26.5,
    "Cimanggis-Cibitung Seksi 2B": 19.6,
    "Cibitung - Cilincing Seksi 2 &3": 19.0,
    "Cengkareng-Batu Ceper-Kunciran": 14.2,
    "Kunciran-Serpong": 11.2,
    "Serpong-Cinere Seksi 1 dan 2": 10.1,
    "Pondok Aren-Serpong": 7.2,
    "Depok-Antasari": 21.5,
    "Cinere-Jagorawi": 14.6,
    "Bekasi-Cawang-Kampung Melayu": 21.0,
    "JORR S": 32.0,
    "JORR NON S": 44.0,
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = s.lower()
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def is_toll_name(name: str) -> bool:
    n = _norm(name)
    return "tol" in n or "toll" in n


def match_ruas(road_name: str) -> List[str]:
    n = _norm(road_name)
    for alias, ruas in COMPOSITE_ROADS.items():
        if alias in n:
            return list(ruas)
    for alias, ruas in ROAD_ALIASES:
        if alias in n:
            return [ruas]
    return []


def summarize_road_usage(osrm_route: dict) -> dict:

    toll_km = 0.0
    non_toll_km = 0.0
    ruas_km: Dict[str, float] = {}
    seen_names: List[str] = []
    unknown: List[str] = []

    for leg in osrm_route.get("legs", []) or []:
        for step in leg.get("steps", []) or []:
            name = step.get("name") or step.get("ref") or ""
            km = (step.get("distance") or 0.0) / 1000.0
            if not is_toll_name(name):
                non_toll_km += km
                continue

            toll_km += km
            if name not in seen_names:
                seen_names.append(name)

            matched = match_ruas(name)
            if not matched:
                if name not in unknown:
                    unknown.append(name)
                continue
            share = km / len(matched)
            for ruas in matched:
                ruas_km[ruas] = ruas_km.get(ruas, 0.0) + share

    return {
        "toll_km": round(toll_km, 2),
        "non_toll_km": round(non_toll_km, 2),
        "ruas_km": {k: round(v, 2) for k, v in ruas_km.items()},
        "toll_road_names": seen_names,
        "unknown_toll_names": unknown,
    }


def ruas_length_km(ruas: str) -> Optional[float]:
    return RUAS_LENGTH_KM.get(ruas)
