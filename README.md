# LENS — Logistic Evaluation and Navigation System

**"Barangnya masih layak jual nggak ya, pas sampai nanti?"**

Itu pertanyaan yang biasanya baru kejawab setelah truk sampai — dan seringnya sudah telat.
Aplikasi ini mencoba menjawabnya **sebelum berangkat**.

Kamu masukkan mau kirim apa, dari mana ke mana, jam berapa, pakai truk pendingin atau tidak.
Sistem lalu membandingkan beberapa rute yang mungkin, dan untuk tiap rute menampilkan:

- **berapa persen kesegaran barang saat tiba** (bukan cuma "berapa jam sampai")
- **perkiraan waktu tempuh** dalam bentuk pita optimis–normal–pesimis, bukan satu angka palsu
- **perkiraan biaya** (tol + BBM), lengkap dengan rincian gerbang tolnya
- **peringatan** kalau barangnya diperkirakan sudah tidak layak jual saat sampai

Fokusnya tiga komoditas dulu: **ikan segar, bayam, kentang**.

Dibuat untuk **AI Innovation Challenge (AIC) COMPFEST 18**, sub-tema *Smart Logistics*.

---

## Kenapa jawabannya bisa dipercaya?

Ini bagian yang penting, jadi kami tulis terus terang.

**Angkanya tidak datang dari AI yang mengarang.** Semua nilai — persentase kesegaran, ETA, rupiah —
dihitung oleh fungsi Python biasa yang bisa kamu buka dan periksa sendiri, pakai rumus dari literatur
ilmu pangan (Ratkowsky/Arrhenius) dan tarif tol resmi BPJT. LLM di sistem ini kerjanya cuma dua:
membaca kalimat bebas dari pengguna, dan memperhalus bahasa penjelasannya. Kalau LLM sampai
mengubah satu angka pun, hasilnya dibuang dan diganti template.

**Kami tidak memasang sensor IoT.** Suhu di dalam kargo adalah *asumsi skenario* — kalau pakai reefer,
diasumsikan sesuai setpoint; kalau tidak, mengikuti suhu udara sepanjang rute dari prakiraan cuaca.
Ini ditampilkan apa adanya di UI, tidak disamarkan seolah-olah hasil pengukuran.

**Ini alat bantu keputusan, bukan sistem produksi yang sudah tervalidasi di lapangan.**
Anggap seperti simulator: berguna buat membandingkan pilihan, belum untuk dijadikan jaminan.

Datanya 100% sekunder — OSRM (rute), Open-Meteo (cuaca), Nominatim (cari lokasi), BPJT (tarif tol),
FAO/USDA/SNI (parameter komoditas). Tidak ada pengumpulan data primer, tidak ada model yang dilatih.

---

## Cara kerjanya

```
Kamu isi form  →  ┌─────────────────────────────────────────────┐
                  │  M1  cari rute + hitung ETA + profil suhu   │
                  │  M2  hitung penurunan kesegaran per jam     │
                  │  M3  hitung biaya + ranking pilihan         │
                  └─────────────────────────────────────────────┘
                                    ↓
                  ┌─────────────────────────────────────────────┐
                  │  Gemini + RAG: ubah angka jadi kalimat      │
                  │  yang enak dibaca + saran penanganan        │
                  └─────────────────────────────────────────────┘
                                    ↓
                     Kartu rute + peta + insight di layar
```

Tiga model itu jalan berurutan dan saling oper lewat `route_id`. Aturan mainnya dibekukan di
`backend/contracts.py` — itu "kontrak" antar-modul, jangan diubah sembarangan.

---

## Isi folder

```
.
├── requirements.txt          daftar dependency Python (dipakai backend + llm-rag)
├── .env.example              contoh isi .env — copy jadi .env, lalu isi sendiri
│
├── backend/                  FastAPI + tiga model perhitungan
│   ├── api.py                pintu masuk HTTP — semua endpoint /api/* ada di sini
│   ├── pipeline.py           penghubung: satu permintaan → M1 → M2 → M3 → hasil
│   ├── contracts.py          tipe data & tanda tangan fungsi antar-modul (dibekukan)
│   │
│   ├── routing.py            M1 — ambil rute alternatif dari OSRM, hitung pita ETA
│   ├── temp_profile.py       M1 — susun profil suhu sepanjang rute
│   │
│   ├── quality.py            M2 — pintu masuk perhitungan kesegaran
│   ├── engine.py             M2 — mesin hitung (Ratkowsky untuk ikan, Arrhenius untuk sayur)
│   ├── models.py             M2 — parameter tiap komoditas dari literatur
│   │
│   ├── cost.py               M3 — biaya BBM + tol
│   ├── toll_table.py         M3 — pembacaan tabel tarif
│   ├── toll_detect.py        M3 — deteksi ruas tol yang dilewati
│   ├── optimizer.py          M3 — Pareto front + skor sesuai preferensi
│   │
│   ├── geocode.py            cari lokasi lewat Nominatim
│   ├── locations.py          daftar kota preset (jakarta, bandung, dst.)
│   ├── dashboard_export.py   rapikan hasil jadi bentuk siap-tampil
│   ├── data/
│   │   └── tarif_tol_jawa.csv    858 baris tarif tol Jawa dari BPJT
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── llm-rag/coldchain/        lapisan AI — dipanggil backend lewat /api/explain
│   ├── orchestrator.py       urutan kerjanya: parse → pipeline → RAG → narasi
│   ├── llm.py                sambungan ke Gemini
│   ├── rag.py                cari potongan pengetahuan yang relevan (TF-IDF)
│   ├── explain.py            susun penjelasan per rute
│   ├── tools.py              fungsi yang boleh dipanggil LLM
│   ├── config.py, state.py
│   └── kb/                   basis pengetahuan (FAO, SNI, USDA, FSSP) — 10 berkas .md
│
└── frontend/                 React + Vite + Tailwind
    ├── src/
    │   ├── App.jsx
    │   ├── components/       PlaceInput, RouteMap, RouteOptions, InsightCard, dll.
    │   └── lib/              api.js, places.js, transform.js, scoring.js, narration.js
    ├── scripts/
    │   └── dev-backend.mjs   penolong: bikin venv + nyalakan backend otomatis
    └── vite.config.js
```

---

## Yang perlu disiapkan

| Perlu | Keterangan |
|---|---|
| **Python 3.10+** | dites di 3.11 dan 3.12. Docker-nya pakai 3.11 |
| **Node.js 18+** | cuma kalau mau menjalankan tampilan/UI-nya |
| **Koneksi internet** | wajib — rute dari OSRM dan cuaca dari Open-Meteo diambil online |
| Gemini API key | opsional. Tanpa ini tetap jalan, cuma narasinya pakai template |
| MapKit JS token | opsional. Tanpa ini peta otomatis pakai OpenStreetMap |

Cek Python kamu dulu:

```bash
python3 --version
```

Belum ada? macOS: `brew install python@3.12`. Windows: unduh dari [python.org](https://www.python.org/downloads/).

---

## Cara menjalankan

Ada tiga jalur. Pilih salah satu — **jalur 1 paling gampang.**

### Jalur 1 — Sekali perintah (backend + tampilan sekaligus)

```bash
cd frontend
npm install
npm run dev
```

Selesai. Skrip `dev-backend.mjs` otomatis bikin `.venv`, install dependency Python-nya,
lalu menyalakan backend — kamu tidak perlu ngapa-ngapain lagi.

- Tampilan: **http://localhost:5173**
- Backend: http://127.0.0.1:8000 (sudah di-proxy, jadi tidak perlu diakses langsung)

Hentikan dengan `Ctrl+C`.

### Jalur 2 — Backend saja, manual

Kalau cuma mau API-nya, atau ingin tahu persis apa yang terjadi.

Jalankan **dari folder utama** (yang ada `requirements.txt`-nya):

```bash
python3 -m venv .venv
```

Aktifkan:

```bash
source .venv/bin/activate          # macOS / Linux
.venv\Scripts\Activate.ps1         # Windows PowerShell
.venv\Scripts\activate.bat         # Windows CMD
```

Kalau berhasil, ada tulisan `(.venv)` di depan prompt terminalmu.

Lalu install dan nyalakan:

```bash
pip install --upgrade pip
pip install -r requirements.txt

cd backend
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

Buka **http://localhost:8000/docs** — itu dokumentasi API otomatis, bisa langsung dicoba dari browser.

Kalau sudah selesai, keluar dari venv dengan `deactivate`.

### Jalur 3 — Docker

Tidak mau ribet urusan Python:

```bash
cd backend
docker compose up --build
```

Backend hidup di http://localhost:8000. File `.env` dari folder utama tetap kebaca.

---

## Mengisi `.env`

Copy contohnya dulu:

```bash
cp .env.example .env
```

Isinya dua baris:

```env
GEMINI_API_KEY=
MAPKIT_JS_TOKEN=
```

**Keduanya boleh dikosongkan** — aplikasinya tetap jalan, cuma turun kualitasnya:

| Kalau kosong | Yang terjadi |
|---|---|
| `GEMINI_API_KEY` | Penjelasan pakai kalimat template. Angkanya tetap sama persis. Badge di UI menampilkan "tanpa LLM" |
| `MAPKIT_JS_TOKEN` | Peta pakai OpenStreetMap, bukan Apple Maps. Fungsinya sama saja |

Ambil Gemini API key gratis di [Google AI Studio](https://aistudio.google.com/).
MapKit JS token dari portal Apple Developer.

> **Jangan pernah commit `.env`.** Sudah masuk `.gitignore`, tapi biasakan cek `git status`
> sebelum `git add` — apalagi kalau kamu pakai `git add .`

<details>
<summary><b>Catatan soal token MapKit yang dikunci ke domain tertentu</b></summary>

Token MapKit JS bisa dibatasi ke domain tertentu (ada klaim `origin` di dalam tokennya).
Kalau token kamu dikunci ke, misalnya, `*.contoh.com`, membuka aplikasi lewat `localhost`
akan ditolak Apple — dan peta otomatis pindah ke OpenStreetMap.

Solusinya, arahkan sebuah subdomain ke komputermu sendiri:

```bash
echo "127.0.0.1 dev.contoh.com" | sudo tee -a /etc/hosts
```

lalu buka `http://dev.contoh.com:5173`. Daftarkan juga hostname-nya di `allowedHosts`
pada `frontend/vite.config.js`.

Perhatikan: token wildcard (`*.contoh.com`) cocoknya dengan **subdomain**, bukan domain
polosnya. Jadi `dev.contoh.com` diterima, `contoh.com` ditolak.

Buka Console browser untuk melihat alasannya — sistem sengaja mencetak sebab kegagalan
yang sebenarnya, bukan cuma "Unauthorized".

</details>

---

## Cek sudah jalan atau belum

Backend menyediakan enam endpoint:

| Endpoint | Gunanya |
|---|---|
| `GET /api/health` | cek hidup atau tidak |
| `GET /api/meta` | daftar komoditas, kota preset, status fitur |
| `GET /api/geocode?q=...` | cari lokasi |
| `GET /api/mapkit-token` | token peta untuk frontend |
| `POST /api/plan` | **inti** — hitung rute, kesegaran, biaya |
| `POST /api/explain` | ubah hasil `/api/plan` jadi penjelasan |

Tes cepat:

```bash
curl http://localhost:8000/api/health
```

Tes beneran — kirim ikan segar dari Jakarta ke Bandung, berangkat jam 8 pagi, truk biasa:

```bash
curl -X POST http://localhost:8000/api/plan \
  -H 'Content-Type: application/json' \
  -d '{
    "origin_key": "jakarta",
    "destination_key": "bandung",
    "commodity": "ikan_segar",
    "departure_time": "2026-08-25T08:00:00",
    "vehicle": "non_reefer",
    "preference": "balanced"
  }'
```

Butuh beberapa detik (nunggu OSRM dan Open-Meteo). Hasilnya kira-kira begini:

```
kesegaran saat tiba : ~61%     ← mepet ambang layak jual 60%
waktu tempuh        : 4 jam 31 menit
biaya               : Rp175.433
```

> Angka kesegarannya **tidak akan sama persis** tiap kali dijalankan. Perhitungannya ikut
> prakiraan suhu Open-Meteo, dan prakiraan itu diperbarui beberapa kali sehari — jadi wajar
> kalau hari ini 61,1% lalu setengah jam kemudian jadi 60,9%. Yang stabil justru rute,
> jarak, dan biayanya, karena tidak bergantung cuaca.

Coba ganti `departure_time` jadi `"2026-08-25T11:00:00"` — berangkat 3 jam lebih siang,
kesegarannya justru naik ke ~70% karena melewati jam macet pagi. Itu contoh keputusan yang
susah ditebak tanpa alat bantu seperti ini.

Ganti `"vehicle"` jadi `"reefer"` untuk melihat efek truk pendingin (~82%).

---

## Kalau ada masalah

| Masalah | Coba ini |
|---|---|
| `command not found: python3` | Python belum terpasang atau belum masuk `PATH` |
| `ModuleNotFoundError` | venv-nya belum aktif. Pastikan ada `(.venv)` di prompt sebelum `pip install` |
| Port 8000 sudah dipakai | Ganti port: `uvicorn api:app --port 8001 --reload` |
| Isi `.env` tidak kebaca | `.env` harus di folder utama, bukan di dalam `backend/` |
| Request lama lalu gagal | Cek internet — OSRM & Open-Meteo diambil online |
| Badge UI bilang "tanpa LLM" padahal key sudah diisi | Cek log terminal backend. Sering karena **kuota harian Gemini habis** — tier gratis dibatasi per model per hari, dan resetnya tengah malam waktu Pasifik (sekitar jam 2 siang WIB) |
| Peta cuma kotak-kotak krem | Token MapKit tidak cocok dengan domain yang kamu pakai — lihat catatan MapKit di atas |

---

## Yang masih jujur kami akui belum beres

Ditulis di sini supaya tidak ada yang kaget:

- **Faktor macet dan cuaca di perhitungan ETA masih placeholder** — belum dikalibrasi ke data
  lalu lintas nyata. Makanya ETA-nya sengaja ditampilkan sebagai *pita*, bukan satu angka pasti.
- **Biaya truk reefer belum dimodelkan.** `cost.py` belum membedakan reefer dan non-reefer,
  jadi biaya tambahan pendinginan belum masuk hitungan. Manfaat kesegarannya nyata; tambahan
  biayanya belum.
- **Angkanya bisa bergeser bahkan dalam hitungan jam**, karena prakiraan cuaca Open-Meteo
  diperbarui berkali-kali sehari. Kalau kamu butuh angka yang bisa dikutip di dokumen,
  catat juga tanggal dan jam pengambilannya.
- **Belum ada uji otomatis** di repo ini.
