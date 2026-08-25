export default function InsightCard({
  insight,
  loading,
  llmUsed,
  fromBackend,
  error,
  routeName,
  routeColor,
  isBest,
}) {
  const explanation = insight?.explanation || [];
  const recommendations = insight?.recommendations || [];
  if (!explanation.length && !recommendations.length && !loading) return null;

  return (
    <section className="overflow-hidden rounded-2xl bg-gradient-to-br from-[#eef4ff] via-[#f0f5ff] to-[#eefaf4] p-6 shadow-card">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[17px] font-semibold tracking-[-0.01em] text-ink">Insight</h2>
          {
}
          {routeName && (
            <div className="mt-1 flex items-center gap-1.5">
              <span
                className="h-2 w-2 flex-shrink-0 rounded-full"
                style={{ background: routeColor || '#94a3b8' }}
              />
              <span className="text-[12.5px] text-slate-500">{routeName}</span>
              {isBest && (
                <span className="rounded-md bg-white/70 px-1.5 py-px text-[10px] font-semibold text-emerald-700">
                  Terbaik
                </span>
              )}
            </div>
          )}
        </div>
        <span className="text-brand/70">{SparkIcon}</span>
      </div>

      {loading ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <SkeletonBlock />
          <SkeletonBlock />
        </div>
      ) : (
        <div className="grid gap-x-10 gap-y-6 sm:grid-cols-2">
          <div>
            <h3 className="mb-3 text-[13.5px] font-semibold text-ink">Penjelasan</h3>
            <ul className="flex flex-col gap-2.5">
              {explanation.map((item, i) => (
                <li key={i} className="flex gap-2.5">
                  <Dot tone="slate" />
                  <p className="text-[13.5px] leading-[1.6] text-slate-600">
                    <span className="font-semibold text-ink">{item.label}</span>
                    {' — '}
                    {item.text}
                  </p>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h3 className="mb-3 text-[13.5px] font-semibold text-ink">Rekomendasi</h3>
            <ul className="flex flex-col gap-2.5">
              {recommendations.map((text, i) => (
                <li key={i} className="flex gap-2.5">
                  <Dot tone="blue" />
                  <p className="text-[13.5px] leading-[1.6] text-slate-600">{text}</p>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      <div className="mt-6 flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <span className="flex items-center gap-1.5 rounded-full bg-white/80 px-3 py-1.5 text-[12px] font-medium text-brand shadow-sm">
          {RagIcon} RAG Context
        </span>
        <span className="text-[12px] text-slate-400">
          {!fromBackend
            ? 'Ringkasan cadangan dari sisi klien'
            : llmUsed
            ? 'Angka dari pipeline M1–M3, kalimat dihaluskan LLM'
            : 'Angka dan kalimat dari pipeline M1–M3 (tanpa LLM)'}
        </span>
        {error && (
          <span className="w-full text-[11.5px] leading-snug text-amber-700">{error}</span>
        )}
      </div>
    </section>
  );
}

function Dot({ tone }) {
  return (
    <span
      className={`mt-[7px] h-1.5 w-1.5 flex-shrink-0 rounded-full ${
        tone === 'blue' ? 'bg-brand/60' : 'bg-slate-300'
      }`}
    />
  );
}

function SkeletonBlock() {
  return (
    <div className="flex flex-col gap-2">
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-3 animate-pulse rounded bg-white/70" style={{ width: `${90 - i * 12}%` }} />
      ))}
    </div>
  );
}

const SparkIcon = (
  <svg width="18" height="18" viewBox="0 0 20 20" fill="none" aria-hidden="true">
    <path
      d="M10 2.5 11.4 7 16 8.4 11.4 9.8 10 14.3 8.6 9.8 4 8.4 8.6 7 10 2.5Z"
      fill="currentColor"
    />
    <path d="M15.5 13 16.2 15 18 15.6 16.2 16.2 15.5 18 14.9 16.2 13 15.6 14.9 15 15.5 13Z" fill="currentColor" />
  </svg>
);

const RagIcon = (
  <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <path d="M4 2.5v11M12 2.5v11" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    <path d="M8 4.5v7" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
  </svg>
);
