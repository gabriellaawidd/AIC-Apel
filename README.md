# Cold Chain AI — LLM on Rails + RAG (MVP)

Implementasi pipeline deterministik "LLM on rails" + RAG advisory untuk prediksi kesegaran & routing rantai dingin. **Jalan tanpa dependensi & tanpa API key** (mode fallback), bisa di-upgrade ke LLM asli dan embedding semantik.

## Prinsip
Urutan komputasi dikunci kode (deterministik): `parse → rute → cuaca → ETA → spoilage → ranking → advisory(RAG) → narasi`. LLM hanya di **parse** & **narrate**. **Semua angka dari fungsi Python — tidak pernah dari LLM.**

## Struktur
```
coldchain/
  config.py        # parameter tetap: shelf-life, faktor kalibrasi, bobot, ambang
  state.py         # state object (ctx) — hanya bertambah
  tools.py         # get_routes, get_weather, estimate_eta, compute_spoilage (RRS), rank_routes (Pareto+score)
  rag.py           # KnowledgeBase: ingest→chunk→embed(TF-IDF)→retrieve; retrieve_advisory
  llm.py           # parse_request & narrate (Gemini function calling + fallback offline)
  orchestrator.py  # LLM on rails — urutan deterministik
  kb/*.md          # knowledge base RAG (FAO, SNI, FSSP, USDA — ringkas & bersumber)
demo.py            # 3 skenario end-to-end
tests/test_spoilage.py  # uji kewarasan vs patokan FAO
```

## Menjalankan
```bash
python3 demo.py               # end-to-end (offline, reproducible)
python3 tests/test_spoilage.py # uji kewarasan + RAG + Pareto
```

### Mode LLM asli — Gemini (opsional)
```bash
pip install google-genai
export GEMINI_API_KEY=...            # atau GOOGLE_API_KEY
export CC_MODEL=gemini-2.5-flash     # opsional; bisa gemini-3.6-flash
python3 demo.py                      # parse_request & narrate memakai function calling Gemini
```
Tanpa key, sistem otomatis pakai parser rule-based + narrator template (angka tetap dari pipeline).

## Model spoilage (inti)
RRS square-root: `RRS(T) = ((T−Tmin)/(T_ref−Tmin))²`, `SL(T) = SL_ref/RRS(T)`,
`damage = Σ dt_i/SL(T_i)`, `pct_fresh = max(0, 1−damage)×100`.

Uji kewarasan (otomatis) vs FAO — Tmin=−10, T_ref=0: RRS(5)=2.25 (≈2×), RRS(10)=4 (konservatif vs 5–6×).

## Yang perlu diganti untuk produksi
- `tools.get_routes` → panggilan OSRM asli (`/route/v1/driving?alternatives=true`).
- `tools.get_weather` → Open-Meteo/BMKG.
- `config.COMMODITY_PARAMS` → verifikasi SL_ref & Tmin dari FSSP/Dalgaard.
- `config.F_TIME_BY_HOUR` / `f_weather` → kalibrasi dari sampel API traffic (Google/TomTom).
- `rag.TfidfEmbedder` → sentence-transformers + FAISS (opsional).

## Sumber
FSSP (DTU Food), FAO (v7180e), Ratkowsky 1991, STAD (IEEE MDM 2020), OSRM, SNI. Isi `kb/` diringkas & di-atribusi, bukan salinan verbatim.
