import { WEIGHT_PRESET_OPTIONS } from '../lib/data.js';
import { fmtRp, fmtDur } from '../lib/scoring.js';

// Right-hand "Options" card from the lo-fi: the ranked list of route options.
// Each row shows a freshness % chip, route name, distance/time chips, and cost,
// with a BEST badge on the winning route. Clicking a row selects it on the map;
// the "Detail" button opens the full breakdown modal.
export default function OptionsPanel({
  routes,
  selectedId,
  onSelect,
  onOpenDetail,
  weightPreset,
  onWeightPreset,
  threshold,
  onThreshold,
  fallback,
}) {
  return (
    <section className="rounded-[14px] bg-white px-6 py-5 shadow-card">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="text-xs font-bold uppercase tracking-[0.08em] text-brand">Route Option</div>
        <select
          value={weightPreset}
          onChange={(e) => onWeightPreset(e.target.value)}
          className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[12px] text-slate-700"
          title="Prioritas optimasi"
        >
          {WEIGHT_PRESET_OPTIONS.map((w) => (
            <option key={w} value={w}>
              {w}
            </option>
          ))}
        </select>
      </div>

      {/* Minimum-freshness threshold control */}
      <div className="mb-4">
        <label className="mb-1.5 block text-[11px] text-slate-500">
          Ambang Kesegaran Minimum: <span className="font-semibold text-slate-700">{threshold}%</span>
        </label>
        <input
          type="range"
          min="50"
          max="95"
          step="1"
          value={threshold}
          onChange={(e) => onThreshold(Number(e.target.value))}
          className="w-full"
        />
      </div>

      <div className="flex flex-col gap-3">
        {routes.map((r, i) => {
          const active = r.id === selectedId;
          return (
            <div
              key={r.id}
              role="button"
              tabIndex={0}
              onClick={() => onSelect(r.id)}
              onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelect(r.id)}
              className="cursor-pointer rounded-xl border-[1.5px] p-3 transition-shadow hover:shadow-card"
              style={{
                borderColor: active ? r.color : '#e2e8f0',
                background: active ? '#f8fafc' : '#fff',
              }}
            >
              {/* Row header: label + BEST */}
              <div className="mb-2 flex items-center gap-2">
                <span className="text-[11px] font-semibold uppercase tracking-[0.05em] text-slate-400">
                  Route #{i + 1}
                </span>
                {r.isBest && (
                  <span className="rounded-full bg-teal px-2 py-0.5 text-[10px] font-bold tracking-[0.05em] text-white">
                    BEST
                  </span>
                )}
              </div>

              <div className="flex items-center gap-3">
                {/* Freshness % box */}
                <div
                  className="tnum flex h-[58px] w-[64px] flex-shrink-0 flex-col items-center justify-center rounded-[10px] font-bold"
                  style={{ background: r.status.bg, color: r.status.fg }}
                >
                  <span className="text-xl leading-none">{r.freshnessPct}%</span>
                </div>

                {/* Name + chips */}
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="inline-block h-2.5 w-2.5 flex-shrink-0 rounded-full" style={{ background: r.color }} />
                    <span className="truncate text-[13.5px] font-semibold text-slate-900">{r.name}</span>
                  </div>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    <Chip>{r.distanceKm} km</Chip>
                    <Chip>{fmtDur(r.durationLikelyMin)}</Chip>
                  </div>
                </div>

                {/* Cost + detail */}
                <div className="flex flex-shrink-0 flex-col items-end gap-1.5">
                  <span className="tnum text-[14px] font-bold text-slate-900">{fmtRp(r.costRp)}</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onOpenDetail(r.id);
                    }}
                    className="rounded-md border border-slate-200 px-2 py-1 text-[11px] font-semibold text-brand hover:bg-slate-50"
                  >
                    Detail ›
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {fallback && (
        <div className="mt-3 rounded-lg bg-red-100 px-3 py-2.5 text-[12px] text-red-700">
          Tidak ada rute memenuhi ambang {threshold}% — menampilkan opsi risiko terendah.
        </div>
      )}
    </section>
  );
}

function Chip({ children }) {
  return (
    <span className="tnum rounded-md bg-slate-100 px-2 py-0.5 text-[11.5px] font-medium text-slate-600">
      {children}
    </span>
  );
}
