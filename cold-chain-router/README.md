# Smart Logistics — Cold Chain Router

Freshness-aware route selection for perishable cargo, implemented in **React + Vite + Tailwind CSS**. Ported from the Claude Design `Cold Chain Router.dc.html` prototype.

Given a fixed Tangerang → Cimahi corridor, the app scores three candidate routes on **freshness, travel time, and cost**, picks the best option under a configurable minimum-freshness threshold, and explains the decision (RAG-style narration + handling advice).

## Features

- **Address autocomplete (MapKit JS)** — Asal/Tujuan fields query `mapkit.Search.autocomplete` as you type, biased to Indonesia (`limitToCountries: 'ID'`, region centred on Java) so the nearest matches surface first. Selecting a suggestion locks in its coordinate.
- **Input row** — origin, destination, departure time, and commodity in a single card; the freshness window and shelf-life read out underneath as supporting footnotes.
- **Leaflet route map** — all candidate routes drawn at once; the selected route is emphasized and colored segment-by-segment by spoilage risk. A "Terbaik" badge marks the winning route.
- **Insights card** — the only tinted surface on the page, so AI output reads as distinct from measured data: plain-language reasoning plus actionable recommendations.
- **Route sheet** — an iOS-style sheet (bottom sheet on phones, centred form sheet on wider screens) with a segmented control across four views: Suhu (per-segment Ratkowsky/RRS list), ETA (optimistic/likely/pessimistic, each with a `?` explaining the scenario), Biaya (cost breakdown), and Banding (all three routes side by side).

The scoring model (`freshnessBase`, sensitivity adjustment, min-max normalized time/cost scores, weighted total) is ported verbatim from the design so results match the original prototype.

## Getting started

```bash
npm install
npm run dev      # start the dev server
npm run build    # production build to dist/
npm run preview  # preview the production build
```

Requires Node 18+.

### MapKit JS token

Address autocomplete needs an Apple MapKit JS token. Copy `.env.example` to `.env` and fill in one of:

- `VITE_MAPKIT_TOKEN` — a signed ES256 JWT (Maps ID + Key ID + Team ID from the Apple Developer portal). Fastest path for a demo.
- `VITE_MAPKIT_TOKEN_URL` — an endpoint returning a freshly signed token (`text/plain` or `{"token": "..."}`). Preferred for anything long-lived, since JWTs expire. Takes precedence over the static token.

Without either, the rest of the app still works — the Asal/Tujuan fields simply fall back to plain free-text entry and show a hint.

## Project structure

```
src/
├── main.jsx                  App entry
├── App.jsx                   State + layout (large title, input row, map, panels)
├── index.css                 Tailwind + Leaflet CSS + HIG-flavoured Leaflet control styling
├── components/
│   ├── Icons.jsx             SF-Symbols-style stroke icon set
│   ├── Field.jsx             Shared form primitives (46px control, label, leading icon)
│   ├── PlaceInput.jsx        Asal/Tujuan field with MapKit autocomplete dropdown
│   ├── RouteMap.jsx          Leaflet map with per-segment risk colouring
│   ├── RouteOptions.jsx      Ranked route list (freshness ring, price, disclosure)
│   ├── FreshnessRing.jsx     Circular freshness gauge
│   ├── InsightsCard.jsx      RAG explanation + recommendations
│   ├── RouteSheet.jsx        iOS-style sheet: Suhu / ETA / Biaya / Banding
│   └── InfoTip.jsx           Reusable "?" popover
└── lib/
    ├── data.js               Routes, commodities, weight presets, status meta
    ├── mapkit.js             MapKit JS loader, token handling, region bias
    ├── useMapkitSearch.js    Debounced autocomplete hook + coordinate resolver
    └── scoring.js            computeScored / buildReasoning / buildSaran
```

## Design system

The UI follows **Apple's Human Interface Guidelines** for the light appearance. Tokens live in `tailwind.config.js`:

- **Color** — iOS system colors (`ios.blue` `#007AFF`, `ios.green` `#34C759`, `ios.orange` `#FF9500`, `ios.red` `#FF3B30`), plus the label (`label` / `label-secondary` / `label-tertiary`) and fill (`fill` → `fill-quaternary`) hierarchies. Hierarchy is expressed through contrast, not through different hues.
- **Typography** — the iOS type scale (`text-largetitle`, `text-title2`, `text-headline`, `text-callout`, `text-footnote`, `text-caption`) on the SF Pro system stack, with HIG letter-spacing.
- **Layout** — `rounded-card` surfaces on a `bg-canvas` page, controls at least 44pt tall, and the standard iOS easing curve (`ease-ios`) on transitions.
- **Accessibility** — status is always paired with a number or label rather than carried by color alone; `prefers-reduced-motion` disables animation in `index.css`.

To reskin the app, change the `colors` block in `tailwind.config.js` and the `body` background in `src/index.css`. Route line colors and segment status colors live in `src/lib/data.js` because Leaflet consumes them directly.

## Notes

- Route coordinates, distances, temperatures, and costs are illustrative demo data carried over from the design prototype — not live routing or weather. Wiring the panel to the FastAPI backend (`/route`, `/spoilage`, `/eta`) documented in the parent project is a natural next step.
- Leaflet and its CSS are bundled locally (no CDN dependency); map tiles come from OpenStreetMap.
