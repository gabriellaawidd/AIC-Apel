import FreshnessRing from './FreshnessRing.jsx';
import { ChevronRight, ChartBar } from './Icons.jsx';
import { fmtRp, fmtDur } from '../lib/scoring.js';

// Kisi kolom bersama untuk header dan setiap baris, supaya selalu sejajar.
const GRID = 'grid grid-cols-[1fr_auto_28px] sm:grid-cols-[1fr_84px_112px_28px]';

// Daftar opsi rute bergaya list iOS: satu baris per rute, kolom rapi,
// dan tombol pengungkap detail (chevron) terpisah dari aksi pilih baris.
export default function RouteOptions({ routes, selectedId, onSelect, onOpenDetail, onCompare }) {
  const selected = routes.find((r) => r.id === selectedId) || routes[0];
  const riskySegments = selected.segments.filter((s) => s.status !== 'green').length;
  const peakTemp = Math.max(...selected.segments.map((s) => s.avgTempC));

  return (
    <section
      className="flex h-full flex-col rounded-card bg-surface p-5 shadow-card"
      aria-labelledby="route-options-title"
    >
      <h2 id="route-options-title" className="mb-4 text-title3 font-semibold text-label">
        Opsi Rute
      </h2>

      {/* Header kolom — kolom Biaya baru muncul saat ada ruang; di layar sempit
          harganya ikut di baris kedua nama rute. */}
      <div className={`${GRID} items-center gap-3 px-2 pb-2`}>
        <span className="text-footnote text-label-secondary">Rute</span>
        <span className="text-footnote text-label-secondary">Kesegaran</span>
        <span className="hidden text-right text-footnote text-label-secondary sm:block">Biaya</span>
        <span />
      </div>

      <ul className="border-t border-separator">
        {routes.map((r) => {
          const active = r.id === selectedId;
          return (
            <li key={r.id} className="border-b border-separator">
              <div
                className={`${GRID} items-center gap-3 rounded-[12px] px-2 transition-colors ${
                  active ? 'bg-ios-blue/[0.06]' : 'bg-transparent'
                }`}
              >
                {/* Kolom rute — seluruh area ini memilih rute di peta */}
                <button
                  type="button"
                  onClick={() => onSelect(r.id)}
                  aria-pressed={active}
                  className="focus-ring flex min-h-[56px] min-w-0 items-center gap-2.5 rounded-[10px] py-2 text-left"
                >
                  <span
                    className="h-2.5 w-2.5 flex-shrink-0 rounded-full"
                    style={{ background: r.color }}
                    aria-hidden="true"
                  />
                  <span className="min-w-0">
                    <span className="flex items-center gap-1.5">
                      <span className="truncate text-callout font-medium text-label">
                        {r.shortName || r.name}
                      </span>
                      {r.isBest && (
                        <span className="flex-shrink-0 rounded-full bg-ios-green/15 px-1.5 py-0.5 text-caption2 font-semibold text-[#1E7B36]">
                          Terbaik
                        </span>
                      )}
                    </span>
                    <span className="mt-0.5 block truncate text-footnote text-label-secondary">
                      Rute {r.id} · {r.distanceKm} km · {fmtDur(r.durationLikelyMin)}
                    </span>
                    {/* Di layar sempit kolom Biaya disembunyikan, jadi harganya
                        turun ke barisnya sendiri agar tetap terbaca utuh. */}
                    <span className="tnum mt-1 block text-footnote font-medium text-label sm:hidden">
                      {fmtRp(r.costRp)}
                    </span>
                  </span>
                </button>

                {/* Kesegaran */}
                <div className="flex items-center gap-2">
                  <FreshnessRing pct={r.freshnessPct} color={r.status.dot} />
                  <span className="tnum text-callout font-medium text-label">{r.freshnessPct}%</span>
                </div>

                {/* Biaya */}
                <div className="hidden justify-end sm:flex">
                  <span className="tnum rounded-full bg-fill-tertiary px-2.5 py-1 text-footnote font-medium text-label">
                    {fmtRp(r.costRp)}
                  </span>
                </div>

                {/* Pengungkap detail */}
                <button
                  type="button"
                  onClick={() => onOpenDetail(r.id)}
                  aria-label={`Lihat detail ${r.name}`}
                  className="focus-ring -mr-1 flex h-11 w-11 items-center justify-center rounded-full text-label-tertiary transition-colors hover:bg-fill-quaternary hover:text-label-secondary"
                >
                  <ChevronRight size={18} />
                </button>
              </div>
            </li>
          );
        })}
      </ul>

      {/* Aksi sekunder */}
      <button
        type="button"
        onClick={onCompare}
        className="focus-ring mt-3 flex min-h-[48px] w-full items-center gap-3 rounded-[12px] px-2 text-left transition-colors hover:bg-fill-quaternary"
      >
        <span className="text-ios-blue">
          <ChartBar size={18} />
        </span>
        <span className="flex-1 text-callout text-label">Bandingkan rute</span>
        <span className="text-label-tertiary">
          <ChevronRight size={18} />
        </span>
      </button>

      {/* Ringkasan rute terpilih — mengisi sisa tinggi kartu dan menjawab
          "apa konsekuensi pilihan ini" tanpa harus membuka sheet. */}
      <div className="mt-auto pt-5">
        <h3 className="mb-2 text-footnote text-label-secondary">Ringkasan rute terpilih</h3>
        <div className="grid grid-cols-3 gap-2">
          <Stat label="Status">
            <span
              className="rounded-full px-2 py-0.5 text-footnote font-semibold"
              style={{ background: selected.status.bg, color: selected.status.fg }}
            >
              {selected.status.label}
            </span>
          </Stat>
          <Stat label="Segmen berisiko">
            <span className="tnum text-headline font-semibold text-label">
              {riskySegments}
              <span className="text-footnote font-normal text-label-secondary">
                /{selected.segments.length}
              </span>
            </span>
          </Stat>
          <Stat label="Suhu puncak">
            <span className="tnum text-headline font-semibold text-label">{peakTemp}°C</span>
          </Stat>
        </div>
      </div>
    </section>
  );
}

function Stat({ label, children }) {
  return (
    <div className="flex flex-col items-start gap-1.5 rounded-[12px] bg-fill-quaternary px-3 py-2.5">
      <span className="text-caption text-label-secondary">{label}</span>
      {children}
    </div>
  );
}
