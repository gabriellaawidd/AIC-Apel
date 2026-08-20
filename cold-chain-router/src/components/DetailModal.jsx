import { COST_LABELS, STATUS_META } from '../lib/data.js';
import { fmtRp } from '../lib/scoring.js';

const TAB_DEFS = [
  { key: 'suhu', label: 'Suhu & Spoilage' },
  { key: 'eta', label: 'ETA' },
  { key: 'biaya', label: 'Biaya' },
  { key: 'skor', label: 'Skor' },
];

function segDot(status) {
  const meta = STATUS_META[status === 'green' ? 'aman' : status === 'yellow' ? 'waspada' : 'berisiko'];
  return meta.dot;
}

export default function DetailModal({
  route,
  routes,
  modalRouteId,
  onPickRoute,
  activeTab,
  onPickTab,
  departTime,
  weightLabel,
  onClose,
}) {
  if (!route) return null;

  const costRows = Object.entries(route.costBreakdown).map(([k, v]) => ({
    key: k,
    label: COST_LABELS[k],
    pctWidth: Math.round(v * 100) + '%',
    amount: fmtRp(route.costRp * v),
  }));

  return (
    <div
      onClick={onClose}
      className="fixed inset-0 z-[2000] flex items-center justify-center bg-[rgba(15,23,42,0.55)] p-6"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="max-h-[85vh] w-full max-w-[720px] overflow-auto rounded-2xl bg-white shadow-modal"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-5">
          <div>
            <div className="text-base font-bold">{route.name}</div>
            <div className="text-xs text-slate-400">Detail perhitungan kesegaran, ETA, biaya, dan skor</div>
          </div>
          <button
            onClick={onClose}
            className="h-[30px] w-[30px] rounded-lg border border-slate-200 bg-white text-base text-slate-500"
            aria-label="Tutup"
          >
            ×
          </button>
        </div>

        {/* Route pills */}
        <div className="flex gap-2 px-6 pt-3.5">
          {routes.map((r) => {
            const active = r.id === modalRouteId;
            return (
              <button
                key={r.id}
                onClick={() => onPickRoute(r.id)}
                className="rounded-full border-[1.5px] px-3.5 py-1.5 text-[12.5px] font-semibold"
                style={{
                  background: active ? r.color : '#fff',
                  color: active ? '#fff' : '#475569',
                  borderColor: active ? r.color : '#e2e8f0',
                }}
              >
                {r.id}
              </button>
            );
          })}
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-slate-200 px-6 pt-3.5">
          {TAB_DEFS.map((t) => {
            const active = activeTab === t.key;
            return (
              <button
                key={t.key}
                onClick={() => onPickTab(t.key)}
                className="border-b-[2.5px] bg-none px-3.5 py-[9px] text-[13px] font-semibold"
                style={{
                  borderColor: active ? '#2a78d6' : 'transparent',
                  color: active ? '#2a78d6' : '#94a3b8',
                }}
              >
                {t.label}
              </button>
            );
          })}
        </div>

        {/* Tab content */}
        <div className="px-6 py-5">
          {activeTab === 'suhu' && (
            <div className="flex flex-col gap-2.5">
              <div className="text-xs text-slate-500">
                Model dekomposisi: Ratkowsky (laju reaksi) dikombinasikan dengan RRS (Remaining Relative
                Shelf-life) per segmen.
              </div>
              <table className="w-full border-collapse text-[12.5px]">
                <thead>
                  <tr className="text-left text-slate-500">
                    <th className="px-2 py-1.5 font-semibold">Segmen</th>
                    <th className="px-2 py-1.5 font-semibold">Jarak</th>
                    <th className="px-2 py-1.5 font-semibold">Suhu Rata²</th>
                    <th className="px-2 py-1.5 font-semibold">Penurunan</th>
                    <th className="px-2 py-1.5 font-semibold">Kumulatif</th>
                  </tr>
                </thead>
                <tbody>
                  {route.segments.map((seg, i) => (
                    <tr key={i} className="border-t border-slate-100">
                      <td className="flex items-center gap-2 p-2">
                        <span
                          className="inline-block h-2 w-2 rounded-full"
                          style={{ background: segDot(seg.status) }}
                        />
                        {seg.label}
                      </td>
                      <td className="tnum p-2">{seg.distanceKm} km</td>
                      <td className="tnum p-2">{seg.avgTempC}°C</td>
                      <td className="tnum p-2 text-red-700">-{seg.decayPct}%</td>
                      <td className="tnum p-2 font-semibold">{seg.cumulativePct}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {activeTab === 'eta' && (
            <div className="flex flex-col gap-3.5">
              <div className="grid grid-cols-3 gap-3">
                <div className="rounded-[10px] bg-slate-100 p-3.5 text-center">
                  <div className="text-[11px] uppercase tracking-[0.04em] text-slate-500">Optimistis</div>
                  <div className="tnum text-xl font-bold">{route.durationOptimisticMin} min</div>
                </div>
                <div className="rounded-[10px] bg-blue-100 p-3.5 text-center">
                  <div className="text-[11px] uppercase tracking-[0.04em] text-blue-700">Likely</div>
                  <div className="tnum text-xl font-bold text-blue-700">{route.durationLikelyMin} min</div>
                </div>
                <div className="rounded-[10px] bg-slate-100 p-3.5 text-center">
                  <div className="text-[11px] uppercase tracking-[0.04em] text-slate-500">Pesimistis</div>
                  <div className="tnum text-xl font-bold">{route.durationPessimisticMin} min</div>
                </div>
              </div>
              <div className="text-[11.5px] text-slate-400">
                source=mapkit_traffic_aware · f_time=1 · f_weather=1 · jam_berangkat={departTime}
              </div>
            </div>
          )}

          {activeTab === 'biaya' && (
            <div className="flex flex-col gap-2.5">
              {costRows.map((row) => (
                <div key={row.key}>
                  <div className="mb-1 flex justify-between text-[13px]">
                    <span className="text-slate-700">{row.label}</span>
                    <span className="tnum font-semibold">{row.amount}</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-[3px] bg-slate-100">
                    <div className="h-full bg-brand" style={{ width: row.pctWidth }} />
                  </div>
                </div>
              ))}
              <div className="mt-1.5 flex justify-between border-t border-slate-200 pt-2.5 text-sm font-bold">
                <span>Total</span>
                <span>{fmtRp(route.costRp)}</span>
              </div>
            </div>
          )}

          {activeTab === 'skor' && (
            <div className="flex flex-col gap-3.5">
              {routes.map((r) => (
                <div key={r.id}>
                  <div className="mb-1.5 flex justify-between text-[13px]">
                    <span className="font-semibold" style={{ color: r.color }}>
                      {r.name}
                    </span>
                    <span className="font-bold">{r.totalScore}/100</span>
                  </div>
                  <div className="flex gap-1.5">
                    <div className="flex-1">
                      <div className="h-1.5 overflow-hidden rounded-[3px] bg-slate-100">
                        <div className="h-full bg-green-600" style={{ width: r.freshnessScore + '%' }} />
                      </div>
                      <div className="mt-0.5 text-[10px] text-slate-400">Kesegaran {r.freshnessScore}</div>
                    </div>
                    <div className="flex-1">
                      <div className="h-1.5 overflow-hidden rounded-[3px] bg-slate-100">
                        <div className="h-full bg-brand" style={{ width: r.timeScore + '%' }} />
                      </div>
                      <div className="mt-0.5 text-[10px] text-slate-400">Waktu {r.timeScore}</div>
                    </div>
                    <div className="flex-1">
                      <div className="h-1.5 overflow-hidden rounded-[3px] bg-slate-100">
                        <div className="h-full bg-teal" style={{ width: r.costScore + '%' }} />
                      </div>
                      <div className="mt-0.5 text-[10px] text-slate-400">Biaya {r.costScore}</div>
                    </div>
                  </div>
                </div>
              ))}
              <div className="text-[11.5px] text-slate-400">Bobot aktif: {weightLabel}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
