import { useMemo, useState } from 'react';
import RouteMap from './components/RouteMap.jsx';
import DetailModal from './components/DetailModal.jsx';
import OptionsPanel from './components/OptionsPanel.jsx';
import { COMMODITIES } from './lib/data.js';
import { computeScored, buildReasoning, buildSaran, fmtRp } from './lib/scoring.js';

// Design-time defaults carried over from the .dc component's editable props
const DEFAULT_THRESHOLD = 80;
const DEFAULT_WEIGHT_PRESET = 'Seimbang';
const DEFAULT_HEAT_MODE = true;

export default function App() {
  const [threshold, setThreshold] = useState(DEFAULT_THRESHOLD);
  const [commodityId, setCommodityId] = useState('sayur-buah');
  const [departTime, setDepartTime] = useState('06:00');
  const [weightPreset, setWeightPreset] = useState(DEFAULT_WEIGHT_PRESET);
  const [asal, setAsal] = useState('Tangerang, Banten');
  const [tujuan, setTujuan] = useState('Cimahi, Jawa Barat');

  const heatMode = DEFAULT_HEAT_MODE;

  const [selectedIdState, setSelectedIdState] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [modalRouteIdState, setModalRouteId] = useState(null);
  const [activeTab, setActiveTab] = useState('suhu');

  // Mirror of the design's renderVals(): all derived view data in one memo.
  const view = useMemo(() => {
    const { scored, bestId, fallback, commodity } = computeScored({ commodityId, weightPreset, threshold });
    const selectedId = selectedIdState || bestId;
    const modalRouteId = modalRouteIdState || bestId;
    const weightLabel = weightPreset || 'Seimbang';

    const displayRoutes = scored.map((r) => ({
      ...r,
      isBest: r.id === bestId,
      isSelected: r.id === selectedId,
      durationHrs: Math.round(r.durationLikelyMin / 6) / 10,
      costFormatted: fmtRp(r.costRp),
    }));

    const bestRoute = displayRoutes.find((r) => r.id === bestId);
    const modalRoute = displayRoutes.find((r) => r.id === modalRouteId);
    const reasoning = buildReasoning({ scored, bestId, fallback, commodity, threshold });
    const saran = buildSaran({ scored, bestId, commodity, departTime });

    return { displayRoutes, bestId, bestRoute, modalRoute, modalRouteId, fallback, commodity, weightLabel, selectedId, reasoning, saran };
  }, [commodityId, weightPreset, threshold, departTime, selectedIdState, modalRouteIdState]);

  const { displayRoutes, bestRoute, modalRoute, modalRouteId, fallback, commodity, weightLabel, selectedId, reasoning, saran } = view;

  // Headline "freshness window": best route's likely travel time, rounded to hours.
  const freshnessWindowHrs = Math.max(1, Math.round(bestRoute.durationLikelyMin / 60));

  const openModal = (id) => {
    setModalRouteId(id);
    setActiveTab('suhu');
    setShowModal(true);
  };

  return (
    <div className="min-h-screen font-sans text-slate-900">
      {/* Header */}
      <header className="flex items-center gap-3.5 bg-navy px-8 py-5 text-white">
        <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-brand">
          <div className="h-3.5 w-3.5 rounded-full border-[2.5px] border-white" />
        </div>
        <div>
          <div className="text-lg font-bold tracking-[-0.01em]">Smart Logistics — Cold Chain Router</div>
          <div className="text-[13px] text-[#a9c3e6]">
            Pemilihan rute pengiriman sadar-kesegaran untuk kargo mudah rusak
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-[1360px] flex-col gap-6 px-8 pb-16 pt-7">
        {/* Input card */}
        <section className="rounded-[14px] bg-white px-7 py-6 shadow-card">
          {/* Row 1: Asal -> Tujuan */}
          <div className="grid grid-cols-1 items-end gap-3 sm:grid-cols-[1fr_auto_1fr]">
            <Field label="Asal">
              <input
                type="text"
                value={asal}
                onChange={(e) => setAsal(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-700 focus:border-brand focus:bg-white focus:outline-none"
              />
            </Field>
            <div className="hidden pb-2.5 text-xl text-slate-300 sm:block">→</div>
            <Field label="Tujuan">
              <input
                type="text"
                value={tujuan}
                onChange={(e) => setTujuan(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-700 focus:border-brand focus:bg-white focus:outline-none"
              />
            </Field>
          </div>

          {/* Row 2: Jam Berangkat | Komoditas | freshness window */}
          <div className="mt-5 grid grid-cols-1 items-start gap-5 sm:grid-cols-3">
            <Field label="Jam Berangkat">
              <input
                type="time"
                value={departTime}
                onChange={(e) => setDepartTime(e.target.value)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm text-slate-900"
              />
            </Field>
            <Field label="Komoditas">
              <select
                value={commodityId}
                onChange={(e) => setCommodityId(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900"
              >
                {COMMODITIES.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.label}
                  </option>
                ))}
              </select>
            </Field>
            <div>
              <div className="flex items-baseline gap-2">
                <span className="tnum text-[34px] font-bold leading-none text-navy">≈{freshnessWindowHrs}</span>
                <span className="text-lg font-semibold text-slate-500">Jam</span>
              </div>
              <div className="mt-1.5 flex items-center gap-1.5">
                <span className="text-[12.5px] leading-snug text-slate-500">
                  Sebelum tingkat kesegaran menurun
                </span>
                <InfoDot title="Perkiraan waktu tempuh rute terbaik — estimasi jendela sebelum kesegaran kargo turun signifikan di bawah ambang minimum. Dihitung dari model Ratkowsky/RRS per segmen." />
              </div>
            </div>
          </div>

          <div className="mt-4 text-xs text-slate-400">
            Shelf-life {commodity.shelfLifeHours} jam · Sensitivitas suhu {commodity.sensitivityLabel}. Hasil di
            bawah diperbarui otomatis saat input berubah.
          </div>
        </section>

        {/* Map + Options */}
        <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[1.5fr_1fr]">
          {/* Map */}
          <section className="rounded-[14px] bg-white px-7 py-6 shadow-card">
            <div className="mb-3.5 text-xs font-bold uppercase tracking-[0.08em] text-brand">Output Map</div>
            <div className="h-[460px]">
              <RouteMap routes={displayRoutes} selectedId={selectedId} heatMode={heatMode} onSelect={setSelectedIdState} />
            </div>
            <div className="mt-3.5 flex flex-wrap gap-[18px] text-xs text-slate-500">
              <Legend color="#16a34a" label="Segmen aman" />
              <Legend color="#ca8a04" label="Segmen waspada" />
              <Legend color="#dc2626" label="Segmen berisiko" />
            </div>
          </section>

          {/* Options route list */}
          <OptionsPanel
            routes={displayRoutes}
            selectedId={selectedId}
            onSelect={setSelectedIdState}
            onOpenDetail={openModal}
            weightPreset={weightPreset}
            onWeightPreset={setWeightPreset}
            threshold={threshold}
            onThreshold={setThreshold}
            fallback={fallback}
          />
        </div>

        {/* RAG output */}
        <section className="rounded-[14px] bg-white px-7 py-6 shadow-card">
          <div className="mb-3.5 text-xs font-bold uppercase tracking-[0.08em] text-teal">
            Explanation — RAG Output
          </div>
          <div className="mb-[18px] flex flex-col gap-2.5">
            {reasoning.map((line, i) => (
              <p key={i} className="text-[14.5px] leading-[1.6] text-slate-800">
                {line}
              </p>
            ))}
          </div>
          <div className="mb-2.5 text-xs font-bold uppercase tracking-[0.05em] text-slate-500">Saran</div>
          <ul className="flex list-disc flex-col gap-2 pl-5">
            {saran.map((s, i) => (
              <li key={i} className="text-sm leading-[1.55] text-slate-700">
                {s}
              </li>
            ))}
          </ul>
        </section>
      </main>

      {showModal && (
        <DetailModal
          route={modalRoute}
          routes={displayRoutes}
          modalRouteId={modalRouteId}
          onPickRoute={setModalRouteId}
          activeTab={activeTab}
          onPickTab={setActiveTab}
          departTime={departTime}
          weightLabel={weightLabel}
          onClose={() => setShowModal(false)}
        />
      )}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <label className="mb-1.5 block text-xs text-slate-500">{label}</label>
      {children}
    </div>
  );
}

function Legend({ color, label }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: color }} />
      {label}
    </div>
  );
}

function InfoDot({ title }) {
  return (
    <span
      title={title}
      className="inline-flex h-4 w-4 flex-shrink-0 cursor-help items-center justify-center rounded-full border border-slate-300 text-[10px] font-bold text-slate-400"
    >
      i
    </span>
  );
}
