"""
geocode.py — Pencarian tempat bebas (bukan lagi dropdown antar-kota)  (BARU)
=============================================================================
PATCH 2026-08-24 — bug "Semarang ter-label Jawa Barat".
  Penyebabnya BUKAN data hardcode (locations.py tidak menyimpan provinsi sama
  sekali), melainkan urutan hasil Nominatim: untuk nama polos yang dipakai
  banyak tempat, desa kecil bisa muncul di atas kotanya. Dua perbaikan di
  bawah: `_rerank()` menaikkan hasil bernama persis sama menurut skor
  `importance`, dan `_label()` selalu menampilkan provinsi.
  Uji tanpa jaringan: `python geocode.py --selftest`.

PATCH 2026-08-23 — menjawab temuan pengguna [7]:

  "ini datanya masih cimahi-jakarta gitu ya (antar kota saja), bisakah kita
   inputnya itu langsung lokasi detailnya apa nama tempatnya seperti di
   google maps?"

MASALAH LAMA
------------
`locations.py` hanya berisi 6 kota preset dan `api.py` hanya menerima
`origin_key`/`destination_key` dari daftar itu. Padahal `routing.py` sejak awal
memanggil OSRM dengan (lon,lat) — jadi sebetulnya koordinat MANA PUN bisa
dipakai; yang membatasi cuma lapisan API dan dropdown di frontend.

CARA BARU
---------
Nominatim (layanan geocoding resmi OpenStreetMap — sumber peta yang sama dengan
tile Leaflet dan jaringan jalan OSRM, jadi konsisten) dipakai untuk mencari
nama tempat: "Pasar Induk Caringin", "Gudang Pendingin Muara Baru", "Jl. Asia
Afrika 8 Bandung", dst. Hasilnya dikembalikan sebagai daftar saran untuk
autocomplete di frontend.

ATURAN PAKAI NOMINATIM (wajib dipatuhi, lihat operasional usage policy):
  - maksimal 1 permintaan per detik  -> `_throttle()`
  - wajib User-Agent yang mengidentifikasi aplikasi -> `USER_AGENT`
  - hasil sebaiknya di-cache di sisi kita -> `_CACHE`
Kalau Nominatim tidak terjangkau (offline/rate-limited), fungsi mengembalikan
daftar kosong dan API akan jatuh ke preset `locations.py` — demo tetap jalan.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Dict, List, Optional

try:
    import requests
except ImportError:
    requests = None

NOMINATIM_SEARCH = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE = "https://nominatim.openstreetmap.org/reverse"

_KONTAK = os.environ.get("GEOCODER_CONTACT", "").strip()
USER_AGENT = f"ColdChainRouter/1.0 ({_KONTAK})" if _KONTAK else "ColdChainRouter/1.0"

PHOTON_SEARCH = "https://photon.komoot.io/api/"
TIMEOUT = 12

_lock = threading.Lock()
_last_call = 0.0
_CACHE: Dict[str, list] = {}


def _throttle() -> None:
    """Jaga jarak minimal 1 detik antar-permintaan (syarat pemakaian Nominatim)."""
    global _last_call
    with _lock:
        delta = time.time() - _last_call
        if delta < 1.05:
            time.sleep(1.05 - delta)
        _last_call = time.time()


def _name_of(item: dict) -> str:
    """Nama utama sebuah hasil Nominatim."""
    addr = item.get("address") or {}
    return (item.get("name")
            or addr.get("amenity") or addr.get("shop") or addr.get("road")
            or (item.get("display_name") or "").split(",")[0]
            or "")


def _label(item: dict) -> str:
    """Nama pendek + konteks, mirip tampilan saran di Google Maps.

    PATCH 2026-08-24 — provinsi (`state`) SELALU ikut ditampilkan.
    Dulu konteks dipotong 2 tingkat pertama dari (village, suburb,
    city_district, town, city, county, state), sehingga untuk hasil di
    tingkat desa/kecamatan yang muncul cuma "Desa X, Kecamatan Y" dan
    provinsinya hilang — pengguna tidak bisa melihat bahwa saran teratas
    ternyata berada di provinsi yang salah. Sekarang bentuknya:
    "<nama>, <konteks terdekat>, <provinsi>".
    """
    addr = item.get("address") or {}
    nama = _name_of(item)
    provinsi = addr.get("state") or ""
    konteks = [addr.get(k) for k in
               ("village", "suburb", "city_district", "town", "city", "county")]
    nama_l = nama.lower()
    konteks = [k for k in konteks
               if k and k != provinsi
               and nama_l not in k.lower() and k.lower() not in nama_l]
    bagian = [nama] + konteks[:1] + ([provinsi] if provinsi else [])
    return ", ".join(bagian) if nama else item.get("display_name", "")


def _rerank(hits: list, query: str) -> list:
    """Urutkan ulang hasil Nominatim untuk pencarian NAMA KOTA/TEMPAT polos.

    PATCH 2026-08-24 — memperbaiki bug "Semarang ter-label Jawa Barat".

    Nominatim mengurutkan hasil menurut relevansi teksnya sendiri, bukan
    menurut seberapa penting tempatnya. Untuk kueri berupa nama polos yang
    dipakai banyak tempat di Indonesia ("Semarang", "Cimahi", "Cikarang",
    "Batang"), desa kecil bernama sama bisa muncul di atas kotanya — dan
    itulah yang membuat "Semarang" tampil dengan provinsi Jawa Barat
    (ada desa bernama Semarang di Jawa Barat) alih-alih Jawa Tengah.

    Aturan: HANYA hasil yang namanya persis sama dengan yang diketik yang
    diurutkan ulang, memakai skor `importance` bawaan Nominatim (kota besar
    jauh lebih tinggi daripada desa). Hasil lain dibiarkan pada urutan asli,
    supaya pencarian POI spesifik ("Pasar Induk Caringin") tidak terganggu.
    """
    q = (query or "").strip().lower()
    if not q:
        return hits

    def importance(item):
        try:
            return float(item.get("importance") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    persis, sisanya = [], []
    for item in hits:
        (persis if _name_of(item).strip().lower() == q else sisanya).append(item)

    persis.sort(key=importance, reverse=True)
    return persis + sisanya


_GALAT_TERAKHIR = {"pesan": "", "penyedia": ""}


def galat_terakhir() -> str:
    return _GALAT_TERAKHIR["pesan"]


def penyedia_terakhir() -> str:
    return _GALAT_TERAKHIR["penyedia"] or "nominatim"


def _catat_galat(pesan: str) -> None:
    _GALAT_TERAKHIR["pesan"] = pesan
    print(f"[geocode] {pesan}", flush=True)


def _photon(q: str, limit: int, country: str) -> List[dict]:
    """Penyedia cadangan berbasis OpenStreetMap, tanpa syarat User-Agent ketat."""
    if requests is None:
        return []
    try:
        r = requests.get(
            PHOTON_SEARCH,
            params={"q": q, "limit": limit, "lang": "id",
                    "lat": -2.5, "lon": 118.0},
            timeout=TIMEOUT,
        )
        fitur = (r.json() or {}).get("features", [])
    except Exception as e:
        _catat_galat(f"Photon juga gagal: {type(e).__name__}: {e}")
        return []

    out = []
    for f in fitur:
        pr = f.get("properties") or {}
        if country and (pr.get("countrycode") or "").lower() != country:
            continue
        koor = (f.get("geometry") or {}).get("coordinates") or []
        if len(koor) != 2:
            continue
        nama = pr.get("name") or ""
        konteks = [pr.get(k) for k in ("district", "city", "county", "state")]
        konteks = [k for k in konteks if k and k != nama]
        out.append({
            "key": f"photon:{pr.get('osm_type','')}:{pr.get('osm_id','')}",
            "label": ", ".join([nama] + konteks[:2]) if nama else pr.get("street", q),
            "address": ", ".join([x for x in konteks if x]) or pr.get("country", ""),
            "lon": float(koor[0]), "lat": float(koor[1]),
            "kind": pr.get("osm_value") or "",
        })
    if out:
        _GALAT_TERAKHIR["penyedia"] = "photon"
        _catat_galat(f"memakai penyedia cadangan Photon — {len(out)} hasil untuk \"{q}\"")
    return out[:limit]


def search(query: str, limit: int = 6, country: str = "id") -> List[dict]:
    """Cari tempat menurut nama. Kembalikan [{key,label,address,lon,lat,kind}].

    `key` dibentuk dari osm_type+osm_id supaya stabil dan bisa dipakai sebagai
    identitas lokasi di request /api/plan.
    """
    q = (query or "").strip()
    if len(q) < 3 or requests is None:
        return []

    _GALAT_TERAKHIR["pesan"] = ""
    _GALAT_TERAKHIR["penyedia"] = "nominatim"

    cache_key = f"{country}|{limit}|{q.lower()}"
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    fetch_limit = max(limit, min(limit * 4, 25))

    try:
        _throttle()
        r = requests.get(
            NOMINATIM_SEARCH,
            params={
                "q": q,
                "format": "jsonv2",
                "addressdetails": 1,
                "limit": fetch_limit,
                "countrycodes": country,
                "accept-language": "id",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        data = r.json()
    except Exception as e:
        _catat_galat(f"Nominatim tidak bisa dihubungi: {type(e).__name__}: {e}")
        return _photon(q, limit, country)

    if r.status_code != 200:
        _catat_galat(
            f"Nominatim menolak permintaan (HTTP {r.status_code}). "
            + ("Kemungkinan besar User-Agent belum diisi kontak yang sah — "
               "setel GEOCODER_CONTACT lalu jalankan ulang server."
               if r.status_code in (403, 429) else "")
        )
        return _photon(q, limit, country)

    data = _rerank(data, q) if isinstance(data, list) else []

    out = []
    for item in data:
        try:
            out.append({
                "key": f"osm:{item.get('osm_type','')}:{item.get('osm_id','')}",
                "label": _label(item),
                "address": item.get("display_name", ""),
                "lon": float(item["lon"]),
                "lat": float(item["lat"]),
                "kind": item.get("type") or item.get("category") or "",
            })
        except (KeyError, TypeError, ValueError):
            continue

    out = out[:limit]
    _CACHE[cache_key] = out
    return out


def reverse(lon: float, lat: float) -> Optional[dict]:
    """Koordinat -> nama tempat (dipakai kalau pengguna menjatuhkan pin di peta)."""
    if requests is None:
        return None
    try:
        _throttle()
        r = requests.get(
            NOMINATIM_REVERSE,
            params={"lon": lon, "lat": lat, "format": "jsonv2",
                    "addressdetails": 1, "accept-language": "id"},
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        item = r.json()
        return {
            "key": f"osm:{item.get('osm_type','')}:{item.get('osm_id','')}",
            "label": _label(item),
            "address": item.get("display_name", ""),
            "lon": float(lon), "lat": float(lat),
            "kind": item.get("type", ""),
        }
    except Exception:
        return None


def _selftest() -> int:
    """Uji perbaikan pelabelan provinsi TANPA jaringan (pakai contoh jawaban Nominatim).

    Jalankan: python geocode.py --selftest
    """
    contoh = [
        {"osm_type": "node", "osm_id": 1, "name": "Semarang", "importance": 0.21,
         "lon": "108.33", "lat": "-6.35", "type": "village", "category": "place",
         "display_name": "Semarang, Kandanghaur, Indramayu, Jawa Barat, Indonesia",
         "address": {"village": "Semarang", "county": "Indramayu",
                     "state": "Jawa Barat"}},
        {"osm_type": "relation", "osm_id": 2, "name": "Semarang", "importance": 0.72,
         "lon": "110.4203", "lat": "-6.9932", "type": "city", "category": "place",
         "display_name": "Kota Semarang, Jawa Tengah, Indonesia",
         "address": {"city": "Kota Semarang", "state": "Jawa Tengah"}},
        {"osm_type": "way", "osm_id": 3, "name": "Gudang Beku Semarang",
         "importance": 0.15, "lon": "110.41", "lat": "-6.95", "type": "warehouse",
         "category": "building",
         "display_name": "Gudang Beku Semarang, Semarang Utara, Jawa Tengah",
         "address": {"suburb": "Semarang Utara", "state": "Jawa Tengah"}},
    ]

    gagal = 0

    urut = _rerank(contoh, "Semarang")
    if urut[0] is not contoh[1]:
        print("GAGAL: kota Semarang (Jawa Tengah) tidak naik ke urutan pertama")
        gagal += 1
    if urut[-1] is not contoh[2]:
        print("GAGAL: hasil non-nama-persis tidak dipertahankan di urutan asli")
        gagal += 1

    label = _label(urut[0])
    if "Jawa Tengah" not in label:
        print(f"GAGAL: provinsi tidak muncul di label -> {label!r}")
        gagal += 1

    label_desa = _label(contoh[0])
    if "Jawa Barat" not in label_desa:
        print(f"GAGAL: provinsi desa tidak muncul di label -> {label_desa!r}")
        gagal += 1

    if _rerank(contoh, "Gudang Beku Semarang")[0] is not contoh[2]:
        print("GAGAL: pencarian POI spesifik ikut diurutkan ulang")
        gagal += 1

    print(f"\nurutan sesudah perbaikan: {[_label(i) for i in urut]}")
    print("SEMUA UJI LULUS" if gagal == 0 else f"{gagal} UJI GAGAL")
    return 1 if gagal else 0


if __name__ == "__main__":
    import sys

    if "--selftest" in sys.argv:
        sys.exit(_selftest())

    for q in ["Semarang", "Pasar Induk Caringin Bandung", "Pelabuhan Muara Baru", "Cimahi"]:
        print(f"\n== {q}")
        for hit in search(q):
            print(f"   {hit['label']}  ({hit['lat']:.5f}, {hit['lon']:.5f})")
