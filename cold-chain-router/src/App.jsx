import { useMemo, useState } from 'react';
import RouteMap from './components/RouteMap.jsx';
import RouteSheet from './components/RouteSheet.jsx';
import RouteOptions from './components/RouteOptions.jsx';
import InsightsCard from './components/InsightsCard.jsx';
import PlaceInput from './components/PlaceInput.jsx';
import { Field, FIELD_SHELL, FIELD_INPUT, FieldIcon } from './components/Field.jsx';
import { ArrowRight, MapPin, Clock, Basket, ChevronDown } from './components/Icons.jsx';
import { COMMODITIES } from './lib/data.js';
import { computeScored, buildReasoning, buildSaran } from './lib/scoring.js';

// Nilai tetap: kontrol ambang & preset bobot dihapus dari UI, model tetap
// memakai default yang sama seperti sebelumnya.
const THRESHOLD = 80;
const WEIGHT_PRESET = 'Seimbang';
const HEAT_MODE = true;

export default function App() {
  const [commodityId, setCommodityId] = useState('sayur-buah');
  const [departTime, setDepartTime] = useState('06:00');
  const [asal, setAsal] = useState({ label: 'Tangerang, Banten', coordinate: null });
  const [tujuan, setTujuan] = useState({ label: 'Cimahi, Jawa Barat', coordinate: null });

  const [selectedIdState, setSelectedIdState] = useState(null);
  const [showSheet, setShowSheet] = useState(false);
  const [sheetRouteIdState, setSheetRouteId] = useState(null);
  const [activeTab, setActiveTab] = useState('suhu');

  const view = useMemo(() => {
    const { scored, bestId, fallback, commodity } = computeScored({
      commodityId,
      weightPreset: WEIGHT_PRESET,
      threshold: THRESHOLD,
    });
    const selectedId = selectedIdState || bestId;
    const sheetRouteId = sheetRouteIdState || bestId;

    const displayRoutes = scored.map((r) => ({
      ...r,
      isBest: r.id === bestId,
      // "Rute A — Tol Cipularang" -> "Tol Cipularang"; kolom sudah berjudul "Rute",
      // jadi prefiksnya redundan dan bikin nama kepotong.
      shortName: r.name.split('—').slice(1).join('—').trim() || r.name,
    }));

    return {
      displayRoutes,
      bestRoute: displayRoutes.find((r) => r.id === bestId),
      sheetRoute: displayRoutes.find((r) => r.id === sheetRouteId),
      sheetRouteId,
      selectedId,
      commodity,
      reasoning: buildReasoning({ scored, bestId, fallback, commodity, threshold: THRESHOLD }),
      saran: buildSaran({ scored, bestId, commodity, departTime }),
    };
  }, [commodityId, departTime, selectedIdState, sheetRouteIdState]);

  const { displayRoutes, bestRoute, sheetRoute, sheetRouteId, selectedId, commodity, reasoning, saran } =
    view;

  const freshnessWindowHrs = Math.max(1, Math.round(bestRoute.durationLikelyMin / 60));

  const openSheet = (id, tab = 'suhu') => {
    setSheetRouteId(id);
    setSelectedIdState(id);
    setActiveTab(tab);
    setShowSheet(true);
  };

  return (
    <div className="min-h-screen bg-canvas font-sans text-label">
      <main className="mx-auto max-w-[1360px] px-5 pb-16 pt-10 sm:px-8 sm:pt-12">
        {/* Large title — hierarki utama halaman, tanpa bilah navigasi berwarna */}
        <header className="mb-7">
          <h1 className="text-largetitle font-bold text-label">Cold Chain Router</h1>
          <p className="mt-1.5 text-callout text-label-secondary">
            Optimalkan rute, pantau kesegaran, dan tekan susut kargo.
          </p>
        </header>

        {/* Baris input */}
        <section className="rounded-card bg-surface p-5 shadow-card" aria-label="Parameter pengiriman">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Asal">
              <PlaceInput
                value={asal}
                onChange={setAsal}
                icon={ArrowRight}
                ariaLabel="Asal pengiriman"
                placeholder="Kota, alamat, atau gudang"
              />
            </Field>

            <Field label="Tujuan">
              <PlaceInput
                value={tujuan}
                onChange={setTujuan}
                icon={MapPin}
                ariaLabel="Tujuan pengiriman"
                placeholder="Kota, alamat, atau pasar"
              />
            </Field>

            <Field label="Berangkat" htmlFor="depart-time">
              <div className={FIELD_SHELL}>
                <FieldIcon as={Clock} />
                <input
                  id="depart-time"
                  type="time"
                  value={departTime}
                  onChange={(e) => setDepartTime(e.target.value)}
                  className={`${FIELD_INPUT} tnum`}
                />
              </div>
            </Field>

            <Field label="Komoditas" htmlFor="commodity">
              <div className={`${FIELD_SHELL} relative`}>
                <FieldIcon as={Basket} />
                <select
                  id="commodity"
                  value={commodityId}
                  onChange={(e) => setCommodityId(e.target.value)}
                  className={`${FIELD_INPUT} cursor-pointer appearance-none pr-6`}
                >
                  {COMMODITIES.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.label}
                    </option>
                  ))}
                </select>
                <span className="pointer-events-none absolute right-3.5 text-label-tertiary">
                  <ChevronDown size={16} />
                </span>
              </div>
            </Field>
          </div>

          {/* Ringkasan kondisi — footnote, bukan kompetitor visual bagi input */}
          <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-separator pt-4">
            <span className="flex items-baseline gap-1.5">
              <span className="tnum text-title2 font-semibold text-label">≈{freshnessWindowHrs}</span>
              <span className="text-footnote text-label-secondary">
                jam sebelum kesegaran menurun
              </span>
            </span>
            <span className="text-footnote text-label-tertiary">
              Shelf-life {commodity.shelfLifeHours} jam · Sensitivitas suhu{' '}
              {commodity.sensitivityLabel}
            </span>
          </div>
        </section>

        {/* Peta + opsi rute — dua kolom bertinggi sama */}
        <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-[1.3fr_1fr]">
          <section
            className="flex flex-col rounded-card bg-surface p-5 shadow-card"
            aria-labelledby="map-title"
          >
            <h2 id="map-title" className="mb-4 text-title3 font-semibold text-label">
              Peta
            </h2>
            <div className="min-h-[400px] flex-1">
              <RouteMap
                routes={displayRoutes}
                selectedId={selectedId}
                heatMode={HEAT_MODE}
                onSelect={setSelectedIdState}
              />
            </div>
            <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2">
              <Legend color="#34C759" label="Segmen aman" />
              <Legend color="#FF9500" label="Segmen waspada" />
              <Legend color="#FF3B30" label="Segmen berisiko" />
            </div>
          </section>

          <RouteOptions
            routes={displayRoutes}
            selectedId={selectedId}
            onSelect={setSelectedIdState}
            onOpenDetail={(id) => openSheet(id, 'suhu')}
            onCompare={() => openSheet(selectedId, 'banding')}
          />
        </div>

        {/* Insight melebar penuh — teksnya panjang, jadi dibagi dua kolom di layar lebar */}
        <div className="mt-5">
          <InsightsCard reasoning={reasoning} saran={saran} />
        </div>
      </main>

      {showSheet && (
        <RouteSheet
          route={sheetRoute}
          routes={displayRoutes}
          modalRouteId={sheetRouteId}
          onPickRoute={(id) => {
            setSheetRouteId(id);
            setSelectedIdState(id);
          }}
          activeTab={activeTab}
          onPickTab={setActiveTab}
          departTime={departTime}
          onClose={() => setShowSheet(false)}
        />
      )}
    </div>
  );
}

function Legend({ color, label }) {
  return (
    <span className="flex items-center gap-1.5 text-footnote text-label-secondary">
      <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} aria-hidden="true" />
      {label}
    </span>
  );
}
