import { useCallback, useEffect, useMemo, useState } from 'react';
import RouteMap from './components/RouteMap.jsx';
import DetailModal from './components/DetailModal.jsx';
import RouteOptions from './components/RouteOptions.jsx';
import InsightCard from './components/InsightCard.jsx';
import AlertBanner from './components/AlertBanner.jsx';
import PlaceInput from './components/PlaceInput.jsx';
import { fetchMeta, planTrip, explainPlan } from './lib/api.js';
import { toDisplayRoutes } from './lib/transform.js';
import { buildFallbackExplanations, buildFallbackInsight } from './lib/narration.js';
import { fmtDur } from './lib/scoring.js';

const DEFAULT_ORIGIN = { label: 'Tangerang', lon: 106.6319, lat: -6.1783, address: 'Banten' };
const DEFAULT_DEST = { label: 'Cimahi', lon: 107.5413, lat: -6.8841, address: 'Jawa Barat' };

function todayAt(hh, mm) {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(hh)}:${pad(mm)}`;
}

export default function App() {
  const [meta, setMeta] = useState(null);
  const [metaError, setMetaError] = useState(null);

  const [origin, setOrigin] = useState(DEFAULT_ORIGIN);
  const [destination, setDestination] = useState(DEFAULT_DEST);
  const [commodity, setCommodity] = useState('ikan_segar');
  const [vehicle, setVehicle] = useState('non_reefer');
  const [preference, setPreference] = useState('balanced');
  const [initialCondition, setInitialCondition] = useState('segar');
  const [departureLocal, setDepartureLocal] = useState(() => todayAt(6, 0));
  const [deadlineEnabled, setDeadlineEnabled] = useState(false);
  const [deadlineLocal, setDeadlineLocal] = useState(() => todayAt(13, 0));
  const [showAdvanced, setShowAdvanced] = useState(false);

  const [planData, setPlanData] = useState(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [planError, setPlanError] = useState(null);
  const [hasRunOnce, setHasRunOnce] = useState(false);

  const [explain, setExplain] = useState(null);
  const [explainLoading, setExplainLoading] = useState(false);
  const [explainError, setExplainError] = useState(null);

  const [selectedIdState, setSelectedIdState] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [modalRouteIdState, setModalRouteId] = useState(null);
  const [activeTab, setActiveTab] = useState('alasan');

  useEffect(() => {
    let cancelled = false;
    fetchMeta()
      .then((m) => {
        if (cancelled) return;
        setMeta(m);
        if (m.commodities?.length) setCommodity(m.commodities[0].key);
      })
      .catch((err) => !cancelled && setMetaError(err.message));
    return () => {
      cancelled = true;
    };
  }, []);

  const runPlan = useCallback(
    async (overrides = {}) => {
      setPlanLoading(true);
      setPlanError(null);
      setExplain(null);
      setExplainError(null);
      try {
        const body = {
          origin: overrides.origin ?? origin,
          destination: overrides.destination ?? destination,
          commodity: overrides.commodity ?? commodity,
          departure_time: overrides.departureLocal ?? departureLocal,
          vehicle: overrides.vehicle ?? vehicle,
          preference: overrides.preference ?? preference,
          deadline: (overrides.deadlineEnabled ?? deadlineEnabled)
            ? overrides.deadlineLocal ?? deadlineLocal
            : null,
          initial_condition: overrides.initialCondition ?? initialCondition,
        };
        const data = await planTrip(body);
        setPlanData(data);
        setSelectedIdState(null);
        setModalRouteId(null);

        setExplainLoading(true);
        explainPlan(data)
          .then((res) => {
            setExplain(res);
            if (!res?.insight) {
              setExplainError(
                'Server penjelasan menjawab tanpa blok "insight" — kemungkinan uvicorn masih ' +
                  'memakai versi lama llm-rag. Hentikan lalu jalankan ulang npm run dev.'
              );
            }
          })
          .catch((err) => {
            setExplain(null);
            setExplainError(err.message);
          })
          .finally(() => setExplainLoading(false));
      } catch (err) {
        setPlanError(err.message);
      } finally {
        setPlanLoading(false);
        setHasRunOnce(true);
      }
    },
    [origin, destination, commodity, vehicle, preference, initialCondition,
     departureLocal, deadlineEnabled, deadlineLocal]
  );

  useEffect(() => {
    if (meta && !hasRunOnce && !planLoading) runPlan();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meta]);

  const displayRoutes = useMemo(() => toDisplayRoutes(planData), [planData]);
  const selectedId = selectedIdState || planData?.best_route_id || displayRoutes[0]?.id;
  const modalRouteId = modalRouteIdState || selectedId;
  const bestRoute = displayRoutes.find((r) => r.id === planData?.best_route_id);
  const selectedRoute = displayRoutes.find((r) => r.id === selectedId);
  const modalRoute = displayRoutes.find((r) => r.id === modalRouteId);

  const explanations = explain?.routes || (planData ? buildFallbackExplanations(planData) : []);
  const insight =
    explain?.insights?.[selectedId] ||
    (planData ? buildFallbackInsight(planData, selectedId) : null);

  const summary = useMemo(() => {
    if (!selectedRoute?.tempSegments?.length) return null;
    const segs = selectedRoute.tempSegments;
    return {
      status: selectedRoute.status,
      riskyHours: segs.filter((s) => s.status !== 'aman').length,
      totalHours: segs.length,
      peakTemp: Math.round(Math.max(...segs.map((s) => s.temp_c))),
    };
  }, [selectedRoute]);

  const legendCounts = useMemo(() => {
    const counts = { aman: 0, waspada: 0, berisiko: 0 };
    (selectedRoute?.tempSegments || []).forEach((s) => {
      if (counts[s.status] != null) counts[s.status] += 1;
    });
    return counts;
  }, [selectedRoute]);

  const openModal = (id, tab = 'alasan') => {
    setModalRouteId(id);
    setActiveTab(tab);
    setShowModal(true);
  };

  return (
    <div className="min-h-screen">
      <div className="mx-auto max-w-[1180px] px-6 pb-16 pt-10">
        {}
        <header className="mb-7">
          <h1 className="text-[30px] font-bold leading-none tracking-[-0.022em] text-ink">
            LENS — Logistics Evaluation and Navigation System
          </h1>
          <p className="mt-2 text-[18px] text-slate-500">
            See the Route, Know the Impact.
          </p>
        </header>

        {metaError && (
          <Notice tone="red">
            Tidak bisa memuat data dari backend: {metaError}. Pastikan <code>npm run dev</code> masih berjalan.
          </Notice>
        )}

        {}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            runPlan();
          }}
          className="mb-6 rounded-2xl bg-white p-5 shadow-card"
        >
          <div className="grid gap-3 lg:grid-cols-4">
            <Field label="Asal">
              <PlaceInput
                value={origin}
                onChange={setOrigin}
                placeholder="Ketik gudang, pasar, atau alamat"
                icon={ArrowIcon}
              />
            </Field>
            <Field label="Tujuan">
              <PlaceInput
                value={destination}
                onChange={setDestination}
                placeholder="Ketik gudang, pasar, atau alamat"
                icon={PinIcon}
              />
            </Field>
            <Field label="Berangkat">
              <label className="flex items-center gap-2.5 rounded-xl bg-fieldbg px-3.5 py-3 focus-within:bg-white focus-within:ring-1 focus-within:ring-brand/40">
                <span className="flex-shrink-0 text-slate-400">{ClockIcon}</span>
                <input
                  type="datetime-local"
                  value={departureLocal}
                  onChange={(e) => setDepartureLocal(e.target.value)}
                  className="w-full bg-transparent text-[15px] text-ink outline-none"
                />
              </label>
            </Field>
            <Field label="Komoditas">
              <label className="flex items-center gap-2.5 rounded-xl bg-fieldbg px-3.5 py-3 focus-within:bg-white focus-within:ring-1 focus-within:ring-brand/40">
                <span className="flex-shrink-0 text-slate-400">{BasketIcon}</span>
                <select
                  value={commodity}
                  onChange={(e) => setCommodity(e.target.value)}
                  className="w-full appearance-none bg-transparent text-[15px] text-ink outline-none"
                >
                  {(meta?.commodities || []).map((c) => (
                    <option key={c.key} value={c.key}>
                      {c.label}
                    </option>
                  ))}
                </select>
                <span className="flex-shrink-0 text-slate-400">{ChevronDown}</span>
              </label>
            </Field>
          </div>

          {}
          <div className="mt-4 flex flex-wrap items-end justify-between gap-4 border-t border-slate-100 pt-4">
            <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
              {bestRoute ? (
                <>
                  <Headline
                    value={fmtDur(bestRoute.etaLikelyH)}
                    caption="perkiraan waktu tempuh rute terbaik"
                  />
                  <Meta>
                    Kesegaran saat tiba{' '}
                    <b className="text-ink">{bestRoute.freshnessPct}%</b>
                    {bestRoute.statusThresholds?.berisiko_di_bawah != null && (
                      <> · ambang layak jual {bestRoute.statusThresholds.berisiko_di_bawah}%</>
                    )}
                    {' · '}
                    kendaraan {vehicle === 'reefer' ? 'berpendingin' : 'biasa'}
                  </Meta>
                </>
              ) : (
                <Meta>Menyiapkan perhitungan…</Meta>
              )}
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setShowAdvanced((v) => !v)}
                className="rounded-lg px-3 py-2 text-[13px] font-medium text-brand transition hover:bg-brand/5"
              >
                {showAdvanced ? 'Sembunyikan opsi' : 'Opsi lainnya'}
              </button>
              <button
                type="submit"
                disabled={planLoading || !meta}
                className="rounded-xl bg-brand px-4 py-2.5 text-[14px] font-semibold text-white transition hover:brightness-105 disabled:opacity-40"
              >
                {planLoading ? 'Menghitung…' : 'Hitung Rute'}
              </button>
            </div>
          </div>

          {showAdvanced && (
            <div className="mt-4 grid gap-3 border-t border-slate-100 pt-4 lg:grid-cols-3">
              <Field label="Kendaraan">
                <Select value={vehicle} onChange={setVehicle} options={meta?.vehicles} />
              </Field>
              <Field label="Kondisi awal kargo">
                <Select
                  value={initialCondition}
                  onChange={setInitialCondition}
                  options={meta?.initial_conditions}
                />
              </Field>
              <Field label="Batas waktu pengiriman">
                <label className="flex items-center gap-2.5 rounded-xl bg-fieldbg px-3.5 py-3">
                  <input
                    type="checkbox"
                    checked={deadlineEnabled}
                    onChange={(e) => setDeadlineEnabled(e.target.checked)}
                    className="h-4 w-4 accent-[#2a78d6]"
                  />
                  <input
                    type="datetime-local"
                    value={deadlineLocal}
                    disabled={!deadlineEnabled}
                    onChange={(e) => setDeadlineLocal(e.target.value)}
                    className="w-full bg-transparent text-[15px] text-ink outline-none disabled:text-slate-400"
                  />
                </label>
              </Field>
            </div>
          )}
        </form>

        {planError && <Notice tone="red">Gagal menghitung rute: {planError}</Notice>}

        {planData && <AlertBanner alert={planData.alert} deadlineFeasible={planData.deadline_feasible} />}

        {displayRoutes.length > 0 && (
          <>
            <div className="grid items-start gap-6 lg:grid-cols-[1.45fr_1fr]">
              <section className="rounded-2xl bg-white p-5 shadow-card">
                <h2 className="mb-4 text-[17px] font-semibold tracking-[-0.01em] text-ink">Peta</h2>
                <div className="h-[470px]">
                  <RouteMap
                    routes={displayRoutes}
                    selectedId={selectedId}
                    onSelect={setSelectedIdState}
                  />
                </div>
                <div className="mt-3.5 flex flex-wrap gap-5 text-[12.5px] text-slate-500">
                  <Legend color="#16a34a" label="Segmen aman" n={legendCounts.aman} />
                  <Legend color="#ca8a04" label="Segmen waspada" n={legendCounts.waspada} />
                  <Legend color="#dc2626" label="Segmen berisiko" n={legendCounts.berisiko} />
                </div>
              </section>

              <RouteOptions
                routes={displayRoutes}
                selectedId={selectedId}
                onSelect={setSelectedIdState}
                onOpenDetail={(id) => openModal(id, 'alasan')}
                onCompare={() => openModal(selectedId, 'skor')}
                preferenceOptions={meta?.preferences}
                preference={preference}
                loading={planLoading}
                summary={summary}
                onPreference={(p) => {
                  setPreference(p);
                  runPlan({ preference: p });
                }}
              />
            </div>

            <div className="mt-6">
              <InsightCard
                insight={insight}
                loading={explainLoading && !insight}
                llmUsed={explain?.llm_used}
                fromBackend={Boolean(explain?.insights?.[selectedId])}
                routeName={selectedRoute?.name}
                routeColor={selectedRoute?.color}
                isBest={selectedRoute?.isBest}
                error={explainError}
              />
            </div>
          </>
        )}

        {!displayRoutes.length && !planLoading && hasRunOnce && !planError && (
          <div className="rounded-2xl bg-white px-7 py-12 text-center text-[14px] text-slate-400 shadow-card">
            Belum ada rute untuk kombinasi input ini.
          </div>
        )}
      </div>

      {showModal && (
        <DetailModal
          route={modalRoute}
          routes={displayRoutes}
          modalRouteId={modalRouteId}
          onPickRoute={setModalRouteId}
          activeTab={activeTab}
          onPickTab={setActiveTab}
          departTime={departureLocal.slice(11, 16)}
          scoring={planData?.scoring}
          explanation={explanations.find((e) => e.route_id === modalRouteId)}
          onClose={() => setShowModal(false)}
        />
      )}
    </div>
  );
}


function Field({ label, children }) {
  return (
    <div>
      <label className="mb-1.5 block text-[12px] text-slate-500">{label}</label>
      {children}
    </div>
  );
}

function Select({ value, onChange, options }) {
  return (
    <label className="flex items-center gap-2.5 rounded-xl bg-fieldbg px-3.5 py-3 focus-within:bg-white focus-within:ring-1 focus-within:ring-brand/40">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full appearance-none bg-transparent text-[15px] text-ink outline-none"
      >
        {(options || []).map((o) => (
          <option key={o.key} value={o.key}>
            {o.label}
          </option>
        ))}
      </select>
      <span className="flex-shrink-0 text-slate-400">{ChevronDown}</span>
    </label>
  );
}

function Headline({ value, caption }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="tnum text-[26px] font-semibold leading-none tracking-[-0.02em] text-ink">
        {value}
      </span>
      <span className="text-[13px] text-slate-500">{caption}</span>
    </div>
  );
}

function Meta({ children }) {
  return <span className="text-[13px] text-slate-400">{children}</span>;
}

function Notice({ children, tone }) {
  return (
    <div
      className={`mb-6 rounded-2xl px-5 py-4 text-[13.5px] ${
        tone === 'red' ? 'bg-red-50 text-red-700' : 'bg-slate-100 text-slate-600'
      }`}
    >
      {children}
    </div>
  );
}

function Legend({ color, label, n }) {
  return (
    <span className={`flex items-center gap-1.5 ${n ? '' : 'opacity-40'}`}>
      <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
      {label}
      {n ? <span className="tnum text-slate-400">({n} jam)</span> : null}
    </span>
  );
}


const ArrowIcon = (
  <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <path d="M2.5 8h10M9 4.5 12.5 8 9 11.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const PinIcon = (
  <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <path d="M8 1.5c-2.5 0-4.5 2-4.5 4.5 0 3.2 4.5 8 4.5 8s4.5-4.8 4.5-8c0-2.5-2-4.5-4.5-4.5Z" stroke="currentColor" strokeWidth="1.4" />
    <circle cx="8" cy="6" r="1.6" fill="currentColor" />
  </svg>
);

const ClockIcon = (
  <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <circle cx="8" cy="8" r="6.2" stroke="currentColor" strokeWidth="1.4" />
    <path d="M8 4.6V8l2.4 1.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
  </svg>
);

const BasketIcon = (
  <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <path d="M2.5 6h11l-1 7.2a1 1 0 0 1-1 .8H4.5a1 1 0 0 1-1-.8L2.5 6Z" stroke="currentColor" strokeWidth="1.3" />
    <path d="M5.5 6 8 2l2.5 4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const ChevronDown = (
  <svg width="12" height="12" viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <path d="M4 6.5 8 10.5 12 6.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
