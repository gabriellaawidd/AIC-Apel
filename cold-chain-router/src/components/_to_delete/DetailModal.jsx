import { COST_LABELS, STATUS_META } from '../lib/data.js';
import { fmtRp } from '../lib/scoring.js';
import InfoTip from './InfoTip.jsx';

const TAB_DEFS = [
  { key: 'suhu', label: 'Suhu & Spoilage' },
  { key: 'eta', label: 'ETA' },
  { key: 'biaya', label: 'Biaya' },
];

// Penjelasan tiap metrik ETA — muncul lewat ikon "?" di sebelah judul kartu.
const ETA_CARDS = [
  {
    key: 'optimistis',
    label: 'Optimistis',
    field: 'durationOptimisticMin',
    info: 'Skenario lalu lintas lancar (≈persentil 10): jalan bebas hambatan, tanpa antrean muat/bongkar di luar rencana. Batas bawah waktu tempuh yang masih realistis.',
  },
  {
    key: 'likely',
    label: 'Likely',
    field: 'durationLikelyMin',
    info: 'Estimasi utama yang dipakai model kesegaran (≈persentil 50). Diambil dari lalu lintas MapKit sadar-waktu pada jam berangkat yang dipilih, sudah termasuk perlambatan rutin di rute ini.',
    accent: true,
  },
  {
    key: 'pesimistis',
    label: 'Pesimistis',
    field: 'durationPessimisticMin',
    info: 'Skenario buruk (≈persentil 90): macet padat, cuaca, atau tertahan di titik transit. Dipakai untuk uji ketahanan — idealnya kesegaran tetap di atas ambang meski pada skenario ini.',
  },
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
  onClose,
}) {
  if (!route) return null;

  const costRows = Object.entries(route.costBreakdown).map(([k, v]) => ({
    key: k,
    label: COST_LABELS[k],
    pct: Math.round(v * 100),
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
            <div className="text-xs text-slate-400">Detail perhitungan kesegaran, ETA, dan biaya</div>
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
                {ETA_CARDS.map((c, i) => (
                  <div
                    key={c.key}
                    className={`rounded-[10px] p-3.5 text-center ${c.accent ? 'bg-blue-100' : 'bg-slate-100'}`}
                  >
                    <div
                      className={`flex items-center justify-center gap-1 text-[11px] uppercase tracking-[0.04em] ${
                        c.accent ? 'text-blue-700' : 'text-slate-500'
                      }`}
                    >
                      <span>{c.label}</span>
                      <InfoTip
                        label={c.label}
                        align={i === 0 ? 'left' : i === ETA_CARDS.length - 1 ? 'right' : 'center'}
                      >
                        {c.info}
                      </InfoTip>
                    </div>
                    <div className={`tnum text-xl font-bold ${c.accent ? 'text-blue-700' : ''}`}>
                      {route[c.field]} min
                    </div>
                  </div>
                ))}
              </div>
              <div className="flex items-center gap-1.5 text-[11.5px] text-slate-400">
                <span>
                  source=mapkit_traffic_aware · f_time=1 · f_weather=1 · jam_berangkat={departTime}
                </span>
                <InfoTip label="Parameter sumber" align="right">
                  Rentang ETA berasal dari MapKit yang sadar lalu lintas. <b>f_time</b> dan{' '}
                  <b>f_weather</b> adalah faktor pengali waktu dan cuaca — nilai 1 berarti tidak ada
                  penyesuaian tambahan di luar data lalu lintas.
                </InfoTip>
              </div>
            </div>
          )}

          {activeTab === 'biaya' && (
            <div className="flex flex-col">
              {costRows.map((row) => (
                <div
                  key={row.key}
                  className="flex items-baseline justify-between gap-3 border-b border-slate-100 py-2.5 text-[13px]"
                >
                  <span className="text-slate-700">{row.label}</span>
                  <span className="flex items-baseline gap-2.5">
                    <span className="tnum text-[11.5px] text-slate-400">{row.pct}%</span>
                    <span className="tnum w-[104px] text-right font-semibold">{row.amount}</span>
                  </span>
                </div>
              ))}
              <div className="flex items-baseline justify-between gap-3 border-t-2 border-slate-200 pt-3 text-sm font-bold">
                <span>Total</span>
                <span className="tnum w-[104px] text-right">{fmtRp(route.costRp)}</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
