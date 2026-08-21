import { useEffect, useRef } from 'react';
import { COST_LABELS } from '../lib/data.js';
import { fmtRp, fmtDur } from '../lib/scoring.js';
import InfoTip from './InfoTip.jsx';
import FreshnessRing from './FreshnessRing.jsx';
import { Xmark, Thermometer, Timer, Wallet, Scale } from './Icons.jsx';

const TABS = [
  { key: 'suhu', label: 'Suhu', icon: Thermometer },
  { key: 'eta', label: 'ETA', icon: Timer },
  { key: 'biaya', label: 'Biaya', icon: Wallet },
  { key: 'banding', label: 'Banding', icon: Scale },
];

// Penjelasan tiap metrik ETA — muncul lewat tombol "?" di sebelah judul kartu.
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

const SEG_COLOR = { green: '#34C759', yellow: '#FF9500', red: '#FF3B30' };

export default function RouteSheet({
  route,
  routes,
  modalRouteId,
  onPickRoute,
  activeTab,
  onPickTab,
  departTime,
  onClose,
}) {
  const closeRef = useRef(null);

  // Esc menutup, fokus pindah ke tombol tutup, dan scroll halaman dikunci.
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    closeRef.current?.focus();
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

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
      className="fixed inset-0 z-[2000] flex items-end justify-center sm:items-center sm:p-6"
      role="presentation"
    >
      {/* Lapisan peredup + blur dibuat terpisah, BUKAN sebagai induk panel.
          Elemen ber-backdrop-filter membentuk stacking context tersendiri, dan
          di WebKit panel anak yang punya transform + overflow-hidden + radius
          bisa kehilangan latar belakangnya di dalamnya. */}
      <div className="absolute inset-0 animate-fadeIn bg-black/25 backdrop-blur-[2px]" />

      <div
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={`Detail ${route.name}`}
        // Warna latar ditulis eksplisit agar tidak bergantung pada variabel
        // opacity Tailwind yang bisa terwarisi dari pembungkus.
        style={{ backgroundColor: '#FFFFFF' }}
        className="relative flex max-h-[88vh] w-full max-w-[640px] animate-sheetIn flex-col overflow-hidden rounded-t-sheet shadow-sheet sm:max-h-[84vh] sm:rounded-sheet"
      >
        {/* Grabber — afordans tarik-tutup khas sheet iOS */}
        <div className="flex justify-center pb-1 pt-2.5 sm:hidden">
          <span className="h-[5px] w-9 rounded-full bg-fill" />
        </div>

        {/* Header */}
        <header className="flex items-start justify-between gap-4 px-5 pb-4 pt-3 sm:pt-5">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span
                className="h-2.5 w-2.5 flex-shrink-0 rounded-full"
                style={{ background: route.color }}
                aria-hidden="true"
              />
              <h2 className="truncate text-title3 font-semibold text-label">{route.name}</h2>
            </div>
            <p className="mt-1 text-footnote text-label-secondary">
              Kesegaran {route.freshnessPct}% · {route.distanceKm} km ·{' '}
              {fmtDur(route.durationLikelyMin)}
            </p>
          </div>
          <button
            ref={closeRef}
            onClick={onClose}
            aria-label="Tutup"
            className="focus-ring flex h-[30px] w-[30px] flex-shrink-0 items-center justify-center rounded-full bg-fill-tertiary text-label-secondary transition-colors hover:bg-fill-secondary"
          >
            <Xmark size={16} />
          </button>
        </header>

        {/* Pemilih rute */}
        <div className="flex gap-2 px-5 pb-3">
          {routes.map((r) => {
            const active = r.id === modalRouteId;
            return (
              <button
                key={r.id}
                onClick={() => onPickRoute(r.id)}
                aria-pressed={active}
                className="focus-ring rounded-full px-3 py-1.5 text-footnote font-semibold transition-colors"
                style={{
                  background: active ? r.color : 'rgba(118,118,128,0.12)',
                  color: active ? '#fff' : 'rgba(60,60,67,0.60)',
                }}
              >
                Rute {r.id}
              </button>
            );
          })}
        </div>

        {/* Segmented control */}
        <div className="px-5">
          <div className="flex rounded-[10px] bg-fill-tertiary p-[3px]" role="tablist">
            {TABS.map((t) => {
              const active = activeTab === t.key;
              return (
                <button
                  key={t.key}
                  role="tab"
                  aria-selected={active}
                  onClick={() => onPickTab(t.key)}
                  className={`focus-ring flex flex-1 items-center justify-center gap-1.5 rounded-[8px] py-[7px] text-footnote font-medium transition-all duration-200 ${
                    active ? 'bg-surface text-label shadow-raised' : 'text-label-secondary'
                  }`}
                >
                  <t.icon size={15} />
                  {t.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Isi tab */}
        <div className="flex-1 overflow-auto px-5 pb-7 pt-4">
          {activeTab === 'suhu' && <SuhuTab route={route} />}
          {activeTab === 'eta' && <EtaTab route={route} departTime={departTime} />}
          {activeTab === 'biaya' && <BiayaTab route={route} costRows={costRows} />}
          {activeTab === 'banding' && <BandingTab routes={routes} activeId={modalRouteId} />}
        </div>
      </div>
    </div>
  );
}

function SuhuTab({ route }) {
  return (
    <div>
      <p className="mb-3 text-footnote text-label-secondary">
        Model dekomposisi: Ratkowsky (laju reaksi) dikombinasikan dengan RRS (Remaining Relative
        Shelf-life) per segmen.
      </p>
      <ul className="overflow-hidden rounded-[14px] bg-fill-quaternary">
        {route.segments.map((seg, i) => (
          <li
            key={i}
            className={`flex items-center gap-3 px-4 py-3 ${i > 0 ? 'border-t border-separator' : ''}`}
          >
            <span
              className="h-2.5 w-2.5 flex-shrink-0 rounded-full"
              style={{ background: SEG_COLOR[seg.status] }}
              aria-hidden="true"
            />
            <div className="min-w-0 flex-1">
              <p className="truncate text-callout text-label">{seg.label}</p>
              <p className="tnum mt-0.5 text-footnote text-label-secondary">
                {seg.distanceKm} km · {seg.avgTempC}°C rata-rata
              </p>
            </div>
            <div className="flex-shrink-0 text-right">
              <p className="tnum text-callout font-semibold text-label">{seg.cumulativePct}%</p>
              <p className="tnum mt-0.5 text-footnote text-ios-red">−{seg.decayPct}%</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function EtaTab({ route, departTime }) {
  return (
    <div>
      <div className="grid grid-cols-3 gap-2.5">
        {ETA_CARDS.map((c, i) => (
          <div
            key={c.key}
            className={`rounded-[14px] p-3.5 text-center ${
              c.accent ? 'bg-ios-blue/10' : 'bg-fill-quaternary'
            }`}
          >
            <div
              className={`flex items-center justify-center gap-0.5 text-caption ${
                c.accent ? 'text-ios-blue' : 'text-label-secondary'
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
            <p
              className={`tnum mt-1 text-title2 font-semibold ${c.accent ? 'text-ios-blue' : 'text-label'}`}
            >
              {route[c.field]}
              <span className="ml-1 text-footnote font-normal">mnt</span>
            </p>
          </div>
        ))}
      </div>
      <div className="mt-3.5 flex items-center gap-1 text-caption text-label-tertiary">
        <span className="tnum">
          source=mapkit_traffic_aware · f_time=1 · f_weather=1 · jam_berangkat={departTime}
        </span>
        <InfoTip label="Parameter sumber" align="right">
          Rentang ETA berasal dari MapKit yang sadar lalu lintas. <b>f_time</b> dan <b>f_weather</b>{' '}
          adalah faktor pengali waktu dan cuaca — nilai 1 berarti tidak ada penyesuaian tambahan di
          luar data lalu lintas.
        </InfoTip>
      </div>
    </div>
  );
}

function BiayaTab({ route, costRows }) {
  return (
    <div className="overflow-hidden rounded-[14px] bg-fill-quaternary">
      {costRows.map((row, i) => (
        <div
          key={row.key}
          className={`flex items-baseline justify-between gap-3 px-4 py-3 ${
            i > 0 ? 'border-t border-separator' : ''
          }`}
        >
          <span className="text-callout text-label">{row.label}</span>
          <span className="flex items-baseline gap-3">
            <span className="tnum text-footnote text-label-tertiary">{row.pct}%</span>
            <span className="tnum w-[108px] text-right text-callout font-medium text-label">
              {row.amount}
            </span>
          </span>
        </div>
      ))}
      <div className="flex items-baseline justify-between gap-3 border-t-2 border-separator px-4 py-3.5">
        <span className="text-callout font-semibold text-label">Total</span>
        <span className="tnum w-[108px] text-right text-headline font-semibold text-label">
          {fmtRp(route.costRp)}
        </span>
      </div>
    </div>
  );
}

function BandingTab({ routes, activeId }) {
  const best = {
    fresh: Math.max(...routes.map((r) => r.freshnessPct)),
    dur: Math.min(...routes.map((r) => r.durationLikelyMin)),
    dist: Math.min(...routes.map((r) => r.distanceKm)),
    cost: Math.min(...routes.map((r) => r.costRp)),
  };

  const rows = [
    { label: 'Kesegaran', get: (r) => `${r.freshnessPct}%`, isBest: (r) => r.freshnessPct === best.fresh },
    { label: 'Waktu', get: (r) => fmtDur(r.durationLikelyMin), isBest: (r) => r.durationLikelyMin === best.dur },
    { label: 'Jarak', get: (r) => `${r.distanceKm} km`, isBest: (r) => r.distanceKm === best.dist },
    { label: 'Biaya', get: (r) => fmtRp(r.costRp), isBest: (r) => r.costRp === best.cost },
  ];

  return (
    <div>
      {/* Kepala kolom: cincin kesegaran per rute */}
      <div className="grid grid-cols-[72px_repeat(3,1fr)] items-end gap-2 pb-3">
        <span />
        {routes.map((r) => (
          <div key={r.id} className="flex flex-col items-center gap-1.5">
            <FreshnessRing pct={r.freshnessPct} color={r.status.dot} size={40} stroke={4} />
            <span
              className={`text-footnote font-semibold ${r.id === activeId ? 'text-label' : 'text-label-secondary'}`}
            >
              Rute {r.id}
            </span>
          </div>
        ))}
      </div>

      <div className="overflow-hidden rounded-[14px] bg-fill-quaternary">
        {rows.map((row, i) => (
          <div
            key={row.label}
            className={`grid grid-cols-[72px_repeat(3,1fr)] items-center gap-2 px-4 py-3 ${
              i > 0 ? 'border-t border-separator' : ''
            }`}
          >
            <span className="text-footnote text-label-secondary">{row.label}</span>
            {routes.map((r) => (
              <span
                key={r.id}
                className={`tnum text-center text-footnote ${
                  row.isBest(r) ? 'font-semibold text-label' : 'text-label-secondary'
                }`}
              >
                {row.get(r)}
              </span>
            ))}
          </div>
        ))}
      </div>
      <p className="mt-3 text-caption text-label-tertiary">
        Angka tebal menandai nilai terbaik pada barisnya.
      </p>
    </div>
  );
}
