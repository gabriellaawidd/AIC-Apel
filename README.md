# LENS (Logistic Evaluation and Navigation System)

> "Barangnya masih layak jual nggak ya, pas sampai nanti?"

Pertanyaan itu biasanya baru kejawab setelah truknya sampai, dan seringnya sudah telat.
LENS mencoba menjawabnya sebelum truk berangkat.

Kamu tinggal isi mau kirim apa, dari mana ke mana, jam berapa, dan pakai truk pendingin
atau tidak. Sistem lalu membandingkan beberapa pilihan rute, dan untuk tiap rute
menampilkan:

- berapa persen kesegaran barang saat tiba (bukan cuma "berapa jam sampai")
- perkiraan waktu tempuh, ditampilkan sebagai rentang optimis sampai pesimis
- perkiraan biaya tol dan BBM, lengkap dengan rincian gerbang tolnya
- peringatan kalau barangnya diperkirakan sudah tidak layak jual saat sampai

Untuk sekarang fokusnya tiga komoditas dulu: ikan segar, bayam, dan kentang.

Proyek ini dibuat untuk AI Innovation Challenge (AIC) COMPFEST 18, sub-tema Smart Logistics.

---

## Kenapa angkanya bisa dipercaya

**Angkanya bukan karangan AI.** Semua nilai (persentase kesegaran, waktu tempuh, rupiah)
dihitung fungsi Python biasa yang bisa kamu buka dan periksa sendiri. Rumusnya dari
literatur ilmu pangan (Ratkowsky dan Arrhenius) dan tarif tol resmi BPJT. LLM di sini
kerjanya cuma dua: membaca kalimat dari pengguna, dan merapikan bahasa penjelasannya.
Kalau sampai ada satu angka yang berubah gara-gara LLM, hasilnya langsung dibuang dan
diganti versi template.

**Kami tidak pakai sensor IoT.** Suhu di dalam kargo itu asumsi skenario, bukan hasil
pengukuran. Kalau pakai reefer, diasumsikan sesuai setpoint. Kalau tidak, mengikuti suhu
udara sepanjang rute dari data prakiraan cuaca. Ini ditulis apa adanya di layar, tidak
kami samarkan seolah-olah hasil sensor beneran.

**Ini alat bantu keputusan, bukan sistem produksi yang sudah teruji di lapangan.**
Anggap saja seperti simulator. Berguna buat membandingkan pilihan, tapi belum bisa
dijadikan jaminan.

Semua datanya sekunder: OSRM untuk rute, Open-Meteo untuk cuaca, Nominatim untuk cari
lokasi, BPJT untuk tarif tol, lalu FAO, USDA, dan SNI untuk parameter komoditas. Tidak
ada pengumpulan data primer, dan tidak ada model yang kami latih sendiri.

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

Tiga model itu jalan berurutan dan saling oper data lewat `route_id`. Aturan mainnya
dikunci di `backend/contracts.py`. Anggap file itu kontrak antar-modul, jadi jangan
diubah sembarangan.

### Alur permintaan, langkah demi langkah

Frontend memanggil backend lewat dua request terpisah, bukan satu. Urutannya tetap:

1. Pengguna isi form dan klik **Hitung Rute**. Frontend kirim `POST /api/plan`.
2. `backend/api.py` meneruskan request itu ke `pipeline.run_pipeline()`, yang menjalankan
   M1, M2, M3 secara berurutan. Hasilnya: daftar rute lengkap dengan kesegaran, ETA, dan biaya.
3. Frontend terima hasil itu dan langsung menampilkan kartu rute serta peta. Sampai titik ini,
   belum ada AI yang terlibat sama sekali.
4. Frontend kirim request kedua, `POST /api/explain`, dengan **hasil dari langkah 2** sebagai
   isi `payload`-nya. Dua request ini wajib berurutan karena `/api/explain` butuh angka dari
   `/api/plan` untuk dijelaskan.
5. `backend/api.py` meneruskan payload itu ke `coldchain.explain.explain_payload()` di
   `llm-rag/`. Fungsi ini mengambil potongan relevan dari basis pengetahuan (RAG), lalu
   memanggil Gemini untuk merapikan kalimat lewat `llm.polish_explanations()`.
6. Kalau Gemini gagal atau kuotanya habis, `explain_payload()` otomatis pakai kalimat
   template. Angka yang ditampilkan tetap sama persis, cuma kalimatnya kurang halus.
7. Frontend terima hasilnya dan menampilkan kartu Insight, lengkap dengan badge yang
   menunjukkan apakah narasinya dari Gemini atau template.

> **Catatan soal `orchestrator.py`.** Folder `llm-rag/coldchain/` juga punya
> `orchestrator.py` dengan class `Orchestrator`, yang mengurai teks bebas lewat Gemini
> function-calling lalu memanggil `tools.plan_trip()`. Class ini **tidak dipakai oleh web
> app**. Endpoint `/api/explain` di `api.py` memanggil `coldchain.explain.explain_payload`
> secara langsung, tanpa lewat `Orchestrator`. Anggap `orchestrator.py` sebagai jalur
> eksperimental yang belum tersambung, bukan bagian dari alur di atas.

---

## Isi folder

```
.
├── requirements.txt          daftar dependency Python (buat backend + llm-rag)
├── .env.example              contoh isi .env, copy jadi .env lalu isi sendiri
│
├── backend/                  FastAPI + tiga model perhitungan
│   ├── api.py                pintu masuk HTTP, semua endpoint /api/* ada di sini
│   ├── pipeline.py           penghubung: satu permintaan → M1 → M2 → M3 → hasil
│   ├── contracts.py          tipe data & tanda tangan fungsi antar-modul (dikunci)
│   │
│   ├── routing.py            M1: ambil rute alternatif dari OSRM, hitung rentang ETA
│   ├── temp_profile.py       M1: susun profil suhu sepanjang rute
│   │
│   ├── quality.py            M2: pintu masuk perhitungan kesegaran
│   ├── engine.py             M2: mesin hitungnya (Ratkowsky buat ikan, Arrhenius buat sayur)
│   ├── models.py             M2: parameter tiap komoditas dari literatur
│   │
│   ├── cost.py               M3: biaya BBM + tol
│   ├── toll_table.py         M3: pembacaan tabel tarif
│   ├── toll_detect.py        M3: deteksi ruas tol yang dilewati
│   ├── optimizer.py          M3: Pareto front + skor sesuai preferensi
│   │
│   ├── geocode.py            cari lokasi lewat Nominatim
│   ├── locations.py          daftar kota preset (jakarta, bandung, dst.)
│   ├── dashboard_export.py   rapikan hasil jadi bentuk siap tampil
│   ├── data/
│   │   └── tarif_tol_jawa.csv    858 baris tarif tol Jawa dari BPJT
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── llm-rag/coldchain/        lapisan AI, dipanggil backend lewat /api/explain
│   ├── orchestrator.py       urutan kerjanya: parse → pipeline → RAG → narasi
│   ├── llm.py                sambungan ke Gemini
│   ├── rag.py                cari potongan pengetahuan yang relevan (TF-IDF)
│   ├── explain.py            susun penjelasan per rute
│   ├── tools.py              fungsi yang boleh dipanggil LLM
│   ├── config.py, state.py
│   └── kb/                   basis pengetahuan dari FAO, SNI, USDA, FSSP (10 berkas .md)
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
| Python 3.10+ | sudah dites di 3.11 dan 3.12. Docker-nya pakai 3.11 |
| Node.js 18+ | cuma perlu kalau mau menjalankan tampilannya |
| Koneksi internet | wajib, karena rute dan cuaca diambil online |
| Gemini API key | opsional. Tanpa ini tetap jalan, cuma penjelasannya pakai template |
| MapKit JS token | opsional. Tanpa ini petanya otomatis pakai OpenStreetMap |

Cek versi Python:

```bash
python3 --version
```

Belum ada Python? macOS: `brew install python@3.12`. Windows:
[python.org/downloads](https://www.python.org/downloads/).

---

## Cara menjalankan

Pilih salah satu dari tiga cara berikut.

### Cara 1: satu perintah (rekomendasi)

```bash
cd frontend
npm install
npm run dev
```

Ini otomatis membuat `.venv`, install dependency Python, dan menyalakan backend.

- Tampilan: http://localhost:5173
- Backend: http://127.0.0.1:8000 (di-proxy dari frontend, tidak perlu dibuka langsung)

Berhenti dengan `Ctrl+C`.

### Cara 2: backend manual

Dari folder utama (yang ada `requirements.txt`):

```bash
python3 -m venv .venv
source .venv/bin/activate          # macOS / Linux
.venv\Scripts\Activate.ps1         # Windows PowerShell
.venv\Scripts\activate.bat         # Windows CMD

pip install --upgrade pip
pip install -r requirements.txt

cd backend
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

Prompt terminal akan menampilkan `(.venv)` setelah environment aktif. Dokumentasi API
otomatis tersedia di http://localhost:8000/docs.

Keluar dari venv dengan `deactivate`.

### Cara 3: Docker

```bash
cd backend
docker compose up --build
```

Backend berjalan di http://localhost:8000, dan `.env` dari folder utama otomatis terbaca.

Setelah mengubah `.env` atau kode, pakai `docker compose up -d --build`, bukan
`docker compose restart`. Perintah `restart` tidak membaca ulang `.env`.

---

## Mengisi `.env`

```bash
cp .env.example .env
```

Isi dua variabel ini:

```env
GEMINI_API_KEY=
MAPKIT_JS_TOKEN=
```

Keduanya opsional secara teknis, aplikasinya tetap jalan walau dikosongkan. Tapi isi
keduanya kalau mau semua fitur tampil maksimal, karena tanpanya ada bagian yang otomatis
turun ke versi sederhana:

| Kalau kosong | Yang terjadi |
|---|---|
| `GEMINI_API_KEY` | Penjelasannya pakai kalimat template. Angkanya tetap sama persis. Badge di UI bakal menampilkan "tanpa LLM" |
| `MAPKIT_JS_TOKEN` | Petanya pakai OpenStreetMap, bukan Apple Maps. Fungsinya sama saja |

Gemini API key bisa diambil gratis di [Google AI Studio](https://aistudio.google.com/),
sedangkan MapKit JS token dari portal Apple Developer.

> **Jangan pernah commit file `.env`.** Memang sudah masuk `.gitignore`, tapi biasakan
> cek `git status` sebelum `git add`, apalagi kalau kamu terbiasa pakai `git add .`

<details>
<summary><b>Catatan kalau token MapKit kamu dikunci ke domain tertentu</b></summary>

Token MapKit JS bisa dibatasi cuma boleh dipakai di domain tertentu (ada klaim `origin`
di dalam tokennya). Misalnya token kamu dikunci ke `*.contoh.com`, maka membuka aplikasi
lewat `localhost` bakal ditolak Apple, dan petanya otomatis pindah ke OpenStreetMap.

Solusinya, arahkan satu subdomain ke komputermu sendiri:

```bash
echo "127.0.0.1 dev.contoh.com" | sudo tee -a /etc/hosts
```

Lalu buka lewat `http://dev.contoh.com:5173`. Jangan lupa daftarkan juga hostname-nya
di bagian `allowedHosts` pada `frontend/vite.config.js`.

Satu hal yang gampang kelewat: token wildcard seperti `*.contoh.com` itu cocoknya dengan
subdomain, bukan domain polosnya. Jadi `dev.contoh.com` diterima, tapi `contoh.com` ditolak.

Kalau petanya tetap tidak muncul, buka Console browser. Sistem sengaja mencetak alasan
kegagalan yang sebenarnya di situ, bukan cuma pesan "Unauthorized" yang tidak jelas.

</details>

---

## Cek sudah jalan atau belum

Backend punya enam endpoint:

| Endpoint | Gunanya |
|---|---|
| `GET /api/health` | cek hidup atau tidak |
| `GET /api/meta` | daftar komoditas, kota preset, status fitur |
| `GET /api/geocode?q=...` | cari lokasi |
| `GET /api/mapkit-token` | token peta buat frontend |
| `POST /api/plan` | yang utama: hitung rute, kesegaran, dan biaya |
| `POST /api/explain` | ubah hasil `/api/plan` jadi penjelasan |

Tes cepat:

```bash
curl http://localhost:8000/api/health
```

Tes yang sebenarnya, kirim ikan segar dari Jakarta ke Bandung, berangkat jam 8 pagi,
pakai truk biasa:

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

Butuh beberapa detik karena harus nunggu OSRM dan Open-Meteo. Hasilnya kira-kira begini:

```
kesegaran saat tiba : ~61%     ← mepet ambang layak jual 60%
waktu tempuh        : 4 jam 31 menit
biaya               : Rp175.433
```

> Angka kesegarannya tidak akan sama persis tiap kali dijalankan, karena ikut prakiraan
> suhu Open-Meteo yang diperbarui beberapa kali sehari. Jadi wajar kalau sekarang 61,1%
> lalu setengah jam kemudian jadi 60,9%. Yang stabil justru rute, jarak, dan biayanya,
> karena tidak bergantung cuaca.

Coba ganti `departure_time` jadi `"2026-08-25T11:00:00"`. Berangkat tiga jam lebih siang,
tapi kesegarannya malah naik ke sekitar 70% karena tidak kena macet pagi. Ini contoh
keputusan yang susah ditebak kalau tidak ada alat bantu.

Ganti juga `"vehicle"` jadi `"reefer"` buat lihat efek truk pendingin, sekitar 82%.

---

## Kalau ada masalah

| Masalah | Coba ini |
|---|---|
| `command not found: python3` | Python belum terpasang, atau belum masuk `PATH` |
| `ModuleNotFoundError` | venv-nya belum aktif. Pastikan ada `(.venv)` di prompt sebelum `pip install` |
| Port 8000 sudah dipakai | Ganti port: `uvicorn api:app --port 8001 --reload` |
| Isi `.env` tidak kebaca | `.env` harus ada di folder utama, bukan di dalam `backend/` |
| Request lama lalu gagal | Cek koneksi internet, karena OSRM dan Open-Meteo diambil online |
| Badge UI bilang "tanpa LLM" padahal key sudah diisi | Cek log terminal backend. Paling sering karena kuota harian Gemini habis. Tier gratis dibatasi per model per hari, dan resetnya tengah malam waktu Pasifik atau sekitar jam 2 siang WIB |
| Peta cuma kotak-kotak krem | Token MapKit tidak cocok dengan domain yang kamu pakai. Lihat catatan MapKit di atas |

---

## Yang belum beres

Ditulis terus terang di sini biar tidak ada yang kaget:

- **Faktor macet dan cuaca di perhitungan ETA masih placeholder.** Belum dikalibrasi ke
  data lalu lintas beneran. Makanya ETA-nya sengaja ditampilkan sebagai rentang, bukan
  satu angka pasti.
- **Biaya truk reefer belum dihitung.** File `cost.py` belum membedakan reefer dan
  non-reefer, jadi biaya tambahan buat pendinginan belum masuk. Manfaat kesegarannya
  sudah nyata, tapi tambahan biayanya belum.
- **Angkanya bisa bergeser dalam hitungan jam**, karena prakiraan cuaca Open-Meteo
  diperbarui berkali-kali sehari. Kalau kamu butuh angka buat dikutip di dokumen, catat
  sekalian tanggal dan jam pengambilannya.
- **Belum ada uji otomatis** di repo ini.
