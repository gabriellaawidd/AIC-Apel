import { fmtRp, fmtDur } from '../lib/scoring.js';

export default function RouteOptions({
  routes,
  selectedId,
  onSelect,
  onOpenDetail,
  onCompare,
  preferenceOptions,
  preference,
  onPreference,
  loading,
  summary,
}) {
  return (
    <section className="rounded-2xl bg-white p-5 shadow-card">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-[17px] font-semibold tracking-[-0.01em] text-ink">Opsi Rute</h2>
        {loading && <span className="text-[11px] text-slate-400">menghitung…</span>}
      </div>

      {}
      <div className="mb-4 flex rounded-[10px] bg-fieldbg p-0.5">
        {(preferenceOptions || []).map((p) => {
          const active = p.key === preference;
          return (
            <button
              key={p.key}
              type="button"
              disabled={loading}
              title={p.hint}
              onClick={() => onPreference(p.key)}
              className={`flex-1 rounded-[8px] px-2 py-1.5 text-[12.5px] font-medium transition ${
                active ? 'bg-white text-ink shadow-seg' : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {SHORT_LABEL[p.key] || p.label}
            </button>
          );
        })}
      </div>

      {}
      <div className="grid grid-cols-[1fr_auto_auto_16px] items-center gap-3 border-b border-slate-100 pb-2 text-[11px] font-medium uppercase tracking-[0.04em] text-slate-400">
        <span>Rute</span>
        <span className="text-center">Kesegaran</span>
        <span className="text-right">Biaya</span>
        <span />
      </div>

      <ul>
        {routes.map((r, i) => {
          const active = r.id === selectedId;
          return (
            <li key={r.id}>
              <button
                type="button"
                onClick={() => onSelect(r.id)}
                className={`grid w-full grid-cols-[1fr_auto_auto_16px] items-center gap-3 rounded-xl px-2 py-3 text-left transition ${
                  active ? 'bg-brand/[0.06]' : 'hover:bg-slate-50'
                }`}
              >
                <span className="min-w-0">
                  <span className="flex items-center gap-2">
                    <span
                      className="h-2.5 w-2.5 flex-shrink-0 rounded-full"
                      style={{ background: r.color }}
                    />
                    <span className="truncate text-[14.5px] font-semibold text-ink">{r.name}</span>
                    {r.isBest && <Pill tone="green">Terbaik</Pill>}
                    {!r.meetsDeadline && <Pill tone="red">Lewat batas</Pill>}
                  </span>
                  <span className="mt-0.5 block truncate pl-[18px] text-[12.5px] text-slate-400">
                    Rute {String.fromCharCode(65 + i)} · {r.distanceKm} km · {fmtDur(r.etaLikelyH)} ·{' '}
                    {r.avgSpeedKmh} km/j
                  </span>
                </span>

                <Donut pct={r.freshnessPct} color={r.status.dot} />

                <span className="tnum rounded-full bg-fieldbg px-2.5 py-1 text-[13px] font-medium text-ink">
                  {fmtRp(r.costRp)}
                </span>

                <span
                  role="presentation"
                  onClick={(e) => {
                    e.stopPropagation();
                    onOpenDetail(r.id);
                  }}
                  className="cursor-pointer text-slate-300 transition hover:text-slate-500"
                  title="Lihat detail perhitungan"
                >
                  {Chevron}
                </span>
              </button>
            </li>
          );
        })}
      </ul>

      <button
        type="button"
        onClick={onCompare}
        className="mt-1 flex w-full items-center gap-2.5 rounded-xl border-t border-slate-100 px-2 py-3.5 text-left transition hover:bg-slate-50"
      >
        <span className="text-brand">{BarsIcon}</span>
        <span className="flex-1 text-[14.5px] text-ink">Bandingkan rute</span>
        <span className="text-slate-300">{Chevron}</span>
      </button>

      {summary && (
        <div className="mt-5">
          <div className="mb-2 text-[12px] text-slate-400">Ringkasan rute terpilih</div>
          <div className="grid grid-cols-3 gap-2.5">
            <Tile label="Status">
              <span
                className="rounded-md px-1.5 py-0.5 text-[13px] font-semibold"
                style={{ background: summary.status.bg, color: summary.status.fg }}
              >
                {summary.status.label}
              </span>
            </Tile>
            <Tile label="Jam berisiko">
              <span className="tnum text-[15px] font-semibold text-ink">
                {summary.riskyHours}
                <span className="text-slate-400">/{summary.totalHours}</span>
              </span>
            </Tile>
            <Tile label="Suhu puncak">
              <span className="tnum text-[15px] font-semibold text-ink">{summary.peakTemp}°C</span>
            </Tile>
          </div>
        </div>
      )}
    </section>
  );
}

const SHORT_LABEL = { balanced: 'Seimbang', cheap: 'Biaya', fast: 'Kecepatan' };

function Tile({ label, children }) {
  return (
    <div className="rounded-xl bg-fieldbg px-3 py-2.5">
      <div className="mb-1 text-[11px] text-slate-400">{label}</div>
      {children}
    </div>
  );
}

function Pill({ children, tone }) {
  const tones = {
    green: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
    red: 'bg-red-50 text-red-600 ring-red-200',
  };
  return (
    <span
      className={`flex-shrink-0 rounded-md px-1.5 py-px text-[10.5px] font-semibold ring-1 ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

export function Donut({ pct, color, size = 38 }) {
  const r = (size - 5) / 2;
  const c = 2 * Math.PI * r;
  const dash = (Math.max(0, Math.min(100, pct)) / 100) * c;
  return (
    <span className="flex items-center gap-2">
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#eef1f5" strokeWidth="4" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${c - dash}`}
        />
      </svg>
      <span className="tnum w-9 text-[14px] font-semibold text-ink">{pct}%</span>
    </span>
  );
}

const Chevron = (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <path d="M6 3.5 10.5 8 6 12.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
  </svg>
);

const BarsIcon = (
  <svg width="17" height="17" viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <rect x="2" y="8" width="3" height="6" rx="1" fill="currentColor" />
    <rect x="6.5" y="4" width="3" height="10" rx="1" fill="currentColor" />
    <rect x="11" y="6" width="3" height="8" rx="1" fill="currentColor" />
  </svg>
);
