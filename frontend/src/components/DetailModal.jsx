import { useState } from 'react';
import { fmtRp, fmtDur } from '../lib/scoring.js';


const TAB_DEFS = [
  { key: 'alasan', label: 'Alasan' },
  { key: 'suhu', label: 'Kesegaran' },
  { key: 'eta', label: 'Waktu' },
  { key: 'biaya', label: 'Biaya & Tol' },
  { key: 'skor', label: 'Skor' },
];

export default function DetailModal({
  route,
  routes,
  modalRouteId,
  onPickRoute,
  activeTab,
  onPickTab,
  departTime,
  scoring,
  explanation,
  onClose,
}) {
  const [showMethod, setShowMethod] = useState(false);
  if (!route) return null;
  const a = route.assumptions || {};

  return (
    <div
      onClick={onClose}
      className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/40 p-6 backdrop-blur-sm"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="max-h-[86vh] w-full max-w-[720px] overflow-auto rounded-[20px] bg-white shadow-modal"
      >
        {}
        <div className="flex items-start justify-between px-6 pb-3 pt-5">
          <div className="pr-4">
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: route.color }} />
              <h2 className="text-[17px] font-semibold tracking-[-0.01em] text-ink">{route.name}</h2>
            </div>
            {route.summary && (
              <p className="mt-1 text-[12.5px] leading-snug text-slate-400">{route.summary}</p>
            )}
          </div>
          <button
            onClick={onClose}
            className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-fieldbg text-[15px] text-slate-500 transition hover:bg-slate-200"
            aria-label="Tutup"
          >
            ×
          </button>
        </div>

        {}
        <div className="flex flex-wrap gap-1.5 px-6">
          {routes.map((r) => {
            const active = r.id === modalRouteId;
            return (
              <button
                key={r.id}
                onClick={() => onPickRoute(r.id)}
                className={`rounded-full px-3 py-1.5 text-[12.5px] font-medium transition ${
                  active ? 'bg-ink text-white' : 'bg-fieldbg text-slate-600 hover:bg-slate-200'
                }`}
              >
                {r.name}
              </button>
            );
          })}
        </div>

        {}
        <div className="mt-4 flex gap-0.5 border-b border-slate-100 px-6">
          {TAB_DEFS.map((t) => {
            const active = activeTab === t.key;
            return (
              <button
                key={t.key}
                onClick={() => onPickTab(t.key)}
                className={`border-b-2 px-3 py-2.5 text-[13px] font-medium transition ${
                  active ? 'border-brand text-brand' : 'border-transparent text-slate-400 hover:text-slate-600'
                }`}
              >
                {t.label}
              </button>
            );
          })}
        </div>

        <div className="px-6 py-5">
          {}
          {activeTab === 'alasan' && (
            <div className="flex flex-col gap-3">
              {explanation?.reasoning?.length ? (
                <>
                  {explanation.reasoning.map((r, i) => (
                    <div key={i} className="rounded-xl bg-fieldbg px-4 py-3">
                      <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.04em] text-slate-400">
                        {r.aspect}
                      </div>
                      <p className="text-[13.5px] leading-[1.6] text-slate-700">{r.text}</p>
                    </div>
                  ))}
                  {explanation.when_to_pick && (
                    <div className="rounded-xl bg-brand/[0.07] px-4 py-3 text-[13.5px] leading-[1.6] text-slate-700">
                      {explanation.when_to_pick}
                    </div>
                  )}
                  {explanation.advisory?.length > 0 && (
                    <div>
                      <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.04em] text-slate-400">
                        Rujukan penanganan
                      </div>
                      {explanation.advisory.slice(0, 2).map((s, i) => (
                        <p key={i} className="mb-1.5 text-[12.5px] leading-[1.6] text-slate-500">
                          {s.text.slice(0, 240)}
                          {s.text.length > 240 ? '…' : ''}{' '}
                          <span className="font-medium text-slate-600">[{s.source}]</span>
                        </p>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <p className="text-[13.5px] text-slate-400">
                  Penalaran untuk rute ini belum tersedia.
                </p>
              )}
            </div>
          )}

          {}
          {activeTab === 'suhu' && (
            <div className="flex flex-col gap-4">
              <div className="flex items-center gap-3">
                <div
                  className="tnum flex h-16 w-20 flex-shrink-0 flex-col items-center justify-center rounded-xl font-semibold"
                  style={{ background: route.status.bg, color: route.status.fg }}
                >
                  <span className="text-[20px] leading-none">{route.freshnessPct}%</span>
                  <span className="mt-1 text-[9.5px] font-bold uppercase tracking-wide">
                    {route.status.label}
                  </span>
                </div>
                <p className="text-[12.5px] leading-[1.55] text-slate-500">
                  {route.basisHuman}
                  {route.statusThresholds?.berisiko_di_bawah != null && (
                    <>
                      {' '}
                      Batas layak jual <b className="text-ink">{route.statusThresholds.berisiko_di_bawah}%</b>;
                      di bawah <b className="text-ink">{route.statusThresholds.waspada_di_bawah}%</b> dihitung waspada.
                    </>
                  )}
                </p>
              </div>

              <div className="grid grid-cols-3 gap-2.5">
                <Stat label="Risiko busuk" value={`${(route.spoilRisk * 100).toFixed(0)}%`} />
                <Stat
                  label="Sisa umur simpan"
                  value={`${route.remainingShelfLifeH.toFixed(1)} jam`}
                  hint="setelah tiba"
                />
                <Stat
                  label="Layak jual"
                  value={route.isSellable ? 'Ya' : 'Tidak'}
                  tone={route.isSellable ? 'ok' : 'bad'}
                />
              </div>

              {}
              {route.tempSegments?.length > 0 && (
                <div>
                  <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.04em] text-slate-400">
                    Jejak kesegaran per jam
                  </div>
                  <div className="overflow-hidden rounded-xl border border-slate-100">
                    <table className="w-full text-[12.5px]">
                      <thead className="bg-fieldbg text-slate-500">
                        <tr>
                          <Th>Jam ke-</Th>
                          <Th right>Suhu</Th>
                          <Th right>Kesegaran</Th>
                          <Th right>Turun</Th>
                          <Th>Status</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {route.tempSegments.map((s, i) => (
                          <tr key={i} className="border-t border-slate-100">
                            <Td>
                              {s.from_h.toFixed(0)} – {s.to_h.toFixed(1)}
                            </Td>
                            <Td right>{s.temp_c.toFixed(1)}°C</Td>
                            <Td right>{s.pct_fresh_end.toFixed(1)}%</Td>
                            <Td right>
                              <span className="text-slate-400">−{(s.pct_drop ?? 0).toFixed(1)}</span>
                            </Td>
                            <Td>
                              <StatusPill k={s.status} />
                            </Td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              <div className="rounded-xl bg-fieldbg px-4 py-3 text-[12.5px] leading-[1.6] text-slate-600">
                Barang diperkirakan masih layak sampai{' '}
                <b className="text-ink">{route.shelfLifeDeadlineH.toFixed(1)} jam</b> setelah berangkat,
                sedangkan skenario perjalanan terburuk memakan{' '}
                <b className="text-ink">{route.etaPessimisticH.toFixed(1)} jam</b>.{' '}
                {route.meetsDeadline ? (
                  <span className="font-medium text-emerald-700">Masih dalam batas aman.</span>
                ) : (
                  <span className="font-medium text-red-600">Berisiko lewat batas.</span>
                )}
              </div>

              <div>
                <button
                  onClick={() => setShowMethod((v) => !v)}
                  className="text-[12px] font-medium text-brand hover:underline"
                >
                  {showMethod ? 'Sembunyikan detail metode' : 'Lihat detail metode (untuk laporan)'}
                </button>
                {showMethod && (
                  <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded-xl bg-ink p-3 text-[11px] leading-relaxed text-slate-200">
                    {route.basisTechnical}
                  </pre>
                )}
              </div>
            </div>
          )}

          {}
          {activeTab === 'eta' && (
            <div className="flex flex-col gap-4">
              <div className="grid grid-cols-3 gap-2.5">
                <Box label="Paling cepat" value={fmtDur(route.etaOptimisticH)} />
                <Box label="Perkiraan wajar" value={fmtDur(route.etaLikelyH)} highlight />
                <Box label="Paling lambat" value={fmtDur(route.etaPessimisticH)} />
              </div>
              <div className="grid grid-cols-3 gap-2.5">
                <Stat label="Jarak" value={`${route.distanceKm} km`} />
                <Stat
                  label="Kecepatan rata-rata"
                  value={`${route.avgSpeedKmh} km/jam`}
                  hint="jarak ÷ perkiraan wajar"
                />
                <Stat
                  label="Tol / non-tol"
                  value={`${Math.round(route.tollKm)} / ${Math.round(route.nonTollKm)} km`}
                />
              </div>
              <div className="rounded-xl bg-fieldbg px-4 py-3 text-[12.5px] leading-[1.7] text-slate-600">
                <div className="mb-1 font-semibold text-slate-700">Dari mana angka ini?</div>
                Waktu bebas hambatan OSRM dikalikan kepadatan jam berangkat ({departTime}){' '}
                <b className="text-ink">×{a.f_time ?? '-'}</b>, cuaca{' '}
                <b className="text-ink">×{a.f_weather ?? '-'}</b>, dan komposisi jalan{' '}
                <b className="text-ink">×{a.road_penalty ?? '-'}</b>. Rentang cepat/lambat adalah
                −10% dan +25% dari hasilnya.
              </div>
            </div>
          )}

          {}
          {activeTab === 'biaya' && (
            <div className="flex flex-col gap-4">
              {route.tollBreakdown?.length > 0 ? (
                <div className="overflow-hidden rounded-xl border border-slate-100">
                  <table className="w-full text-[12.5px]">
                    <thead className="bg-fieldbg text-slate-500">
                      <tr>
                        <Th>Ruas tol</Th>
                        <Th>Masuk → Keluar</Th>
                        <Th right>Tarif</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {route.tollBreakdown.map((b, i) => (
                        <tr key={i} className="border-t border-slate-100 align-top">
                          <Td>
                            <div className="font-medium text-ink">{b.ruas}</div>
                            <div className="text-[10.5px] text-slate-400">
                              {b.km_di_ruas != null && <>{b.km_di_ruas} km di ruas ini · </>}
                              sistem {b.sistem}
                              {b.perkiraan ? ' · perkiraan' : ' · tarif tervalidasi'}
                            </div>
                            {b.catatan && <div className="text-[10.5px] text-amber-600">{b.catatan}</div>}
                          </Td>
                          <Td>
                            <span className="text-slate-500">
                              {b.gerbang_masuk} → {b.gerbang_keluar}
                            </span>
                          </Td>
                          <Td right>
                            <span className="tnum font-medium text-ink">{fmtRp(b.tarif_rp)}</span>
                          </Td>
                        </tr>
                      ))}
                      <tr className="border-t border-slate-200 bg-fieldbg">
                        <Td colSpan={2}>
                          <span className="font-semibold text-ink">
                            Subtotal tol (gol. {route.tollBreakdown[0]?.golongan})
                          </span>
                        </Td>
                        <Td right>
                          <span className="tnum font-semibold text-ink">{fmtRp(route.costTollRp)}</span>
                        </Td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="rounded-xl bg-emerald-50 px-4 py-3 text-[12.5px] text-emerald-800">
                  Rute ini tidak melewati jalan tol — tidak ada tarif tol yang dikenakan.
                </div>
              )}

              <div className="flex flex-col gap-2.5">
                <CostBar label="Tol" amount={route.costTollRp} total={route.costRp} />
                <CostBar
                  label={`Bahan bakar${route.fuelLiters ? ` (±${route.fuelLiters} liter)` : ''}`}
                  amount={route.costFuelRp}
                  total={route.costRp}
                />
                <div className="mt-1 flex justify-between border-t border-slate-100 pt-2.5 text-[14px] font-semibold text-ink">
                  <span>Total</span>
                  <span className="tnum">{fmtRp(route.costRp)}</span>
                </div>
              </div>

              {route.costBasis && (
                <div className="text-[11px] text-slate-400">Asumsi biaya: {route.costBasis}</div>
              )}
            </div>
          )}

          {}
          {activeTab === 'skor' && (
            <div className="flex flex-col gap-3">
              {scoring && (
                <div className="rounded-xl bg-fieldbg px-4 py-3 text-[12.5px] leading-[1.7] text-slate-600">
                  <div className="mb-1.5 font-semibold text-slate-700">
                    Bobot aktif — prioritas {scoring.preference}
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {scoring.criteria?.map((c) => (
                      <span
                        key={c.key}
                        className="rounded-md bg-white px-2 py-0.5 text-[11.5px] text-slate-600 ring-1 ring-slate-200"
                      >
                        {c.label} <b className="text-ink">{Math.round(c.weight * 100)}%</b>{' '}
                        <span className="text-slate-400">({c.unit})</span>
                      </span>
                    ))}
                  </div>
                  <div className="mt-2">{scoring.note}</div>
                </div>
              )}

              {routes.map((r) => (
                <div key={r.id} className="rounded-xl border border-slate-100 px-4 py-3">
                  <div className="mb-1.5 flex items-center justify-between text-[13.5px]">
                    <span className="font-medium" style={{ color: r.color }}>
                      {r.name}
                    </span>
                    <span className="tnum font-semibold text-ink">
                      {Math.round((1 - r.score) * 100)}/100
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {r.isBest && <Badge tone="teal">Terbaik</Badge>}
                    {r.isPareto ? (
                      <Badge tone="blue">Pareto-optimal</Badge>
                    ) : (
                      <Badge tone="slate">Didominasi</Badge>
                    )}
                    {r.meetsDeadline ? (
                      <Badge tone="ok">Mengejar batas waktu</Badge>
                    ) : (
                      <Badge tone="bad">Lewat batas</Badge>
                    )}
                  </div>
                  {!r.isPareto && r.dominatedReason && (
                    <p className="mt-1.5 text-[11.5px] leading-[1.5] text-slate-400">
                      Kalah dari rute lain — {r.dominatedReason}.
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Th({ children, right }) {
  return (
    <th
      className={`px-3 py-2 text-[10.5px] font-semibold uppercase tracking-wide ${
        right ? 'text-right' : 'text-left'
      }`}
    >
      {children}
    </th>
  );
}

function Td({ children, right, colSpan }) {
  return (
    <td colSpan={colSpan} className={`px-3 py-2 ${right ? 'text-right' : 'text-left'}`}>
      {children}
    </td>
  );
}

function StatusPill({ k }) {
  const map = {
    aman: 'bg-emerald-100 text-emerald-700',
    waspada: 'bg-amber-100 text-amber-700',
    berisiko: 'bg-red-100 text-red-600',
  };
  return (
    <span className={`rounded-md px-1.5 py-0.5 text-[10px] font-semibold uppercase ${map[k] || map.aman}`}>
      {k}
    </span>
  );
}

function Box({ label, value, highlight }) {
  return (
    <div className={`rounded-xl p-3.5 text-center ${highlight ? 'bg-brand/10' : 'bg-fieldbg'}`}>
      <div className={`text-[11px] ${highlight ? 'text-brand' : 'text-slate-500'}`}>{label}</div>
      <div className={`tnum text-[17px] font-semibold ${highlight ? 'text-brand' : 'text-ink'}`}>
        {value}
      </div>
    </div>
  );
}

function CostBar({ label, amount, total }) {
  const pct = total > 0 ? Math.round((amount / total) * 100) : 0;
  return (
    <div>
      <div className="mb-1 flex justify-between text-[13px]">
        <span className="text-slate-600">{label}</span>
        <span className="tnum font-medium text-ink">{fmtRp(amount)}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-fieldbg">
        <div className="h-full rounded-full bg-brand" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function Stat({ label, value, hint, tone }) {
  const color = tone === 'ok' ? 'text-emerald-700' : tone === 'bad' ? 'text-red-600' : 'text-ink';
  return (
    <div className="rounded-xl bg-fieldbg px-3 py-2.5 text-center">
      <div className="text-[10.5px] text-slate-500">{label}</div>
      <div className={`tnum text-[15px] font-semibold ${color}`}>{value}</div>
      {hint && <div className="text-[10px] text-slate-400">{hint}</div>}
    </div>
  );
}

function Badge({ children, tone }) {
  const tones = {
    teal: 'bg-teal text-white',
    blue: 'bg-blue-50 text-blue-700',
    slate: 'bg-fieldbg text-slate-500',
    ok: 'bg-emerald-50 text-emerald-700',
    bad: 'bg-red-50 text-red-600',
  };
  return (
    <span className={`rounded-md px-2 py-0.5 text-[10px] font-semibold ${tones[tone] || tones.slate}`}>
      {children}
    </span>
  );
}
