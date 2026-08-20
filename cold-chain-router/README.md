# Smart Logistics — Cold Chain Router

Freshness-aware route selection for perishable cargo, implemented in **React + Vite + Tailwind CSS**. Ported from the Claude Design `Cold Chain Router.dc.html` prototype.

Given a fixed Tangerang → Cimahi corridor, the app scores three candidate routes on **freshness, travel time, and cost**, picks the best option under a configurable minimum-freshness threshold, and explains the decision (RAG-style narration + handling advice).

## Features

- **Interactive input panel** — commodity, departure time, minimum-freshness threshold, optimization priority preset, and segment heatmap toggle.
- **Leaflet route map** — all candidate routes drawn at once; the selected route is emphasized and (in heat mode) colored segment-by-segment by spoilage risk. A "TERBAIK" (best) badge marks the winning route.
- **Best-option card** — freshness %, travel time, cost, and distance for the top-scoring route.
- **RAG output** — plain-language reasoning for why the route was chosen, plus actionable `Saran` (advice).
- **Detail modal** — per-route breakdown across four tabs: Suhu & Spoilage (Ratkowsky/RRS segment table), ETA band (optimistic/likely/pessimistic), Biaya (cost breakdown), and Skor (freshness/time/cost sub-scores).

The scoring model (`freshnessBase`, sensitivity adjustment, min-max normalized time/cost scores, weighted total) is ported verbatim from the design so results match the original prototype.

## Getting started

```bash
npm install
npm run dev      # start the dev server
npm run build    # production build to dist/
npm run preview  # preview the production build
```

Requires Node 18+.

## Project structure

```
src/
├── main.jsx                  App entry
├── App.jsx                   State + layout (mirrors the design's renderVals)
├── index.css                 Tailwind + Leaflet CSS + brand tweaks
├── components/
│   ├── RouteMap.jsx          Leaflet map (ported from the design's RouteMap.jsx)
│   └── DetailModal.jsx       Route detail modal with the four tabs
└── lib/
    ├── data.js               Routes, commodities, weight presets, status meta
    └── scoring.js            computeScored / buildReasoning / buildSaran
```

## Notes

- Route coordinates, distances, temperatures, and costs are illustrative demo data carried over from the design prototype — not live routing or weather. Wiring the panel to the FastAPI backend (`/route`, `/spoilage`, `/eta`) documented in the parent project is a natural next step.
- Leaflet and its CSS are bundled locally (no CDN dependency); map tiles come from OpenStreetMap.
