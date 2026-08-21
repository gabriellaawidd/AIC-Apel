import { Sparkles, Brain } from './Icons.jsx';

const REASONING_LEADS = ['Rute terpilih', 'Pembanding', 'Titik risiko'];

// Kartu Insight — satu-satunya permukaan berwarna di halaman, sehingga
// keluaran AI langsung terbaca berbeda dari data faktual di kartu lain.
// Melebar penuh dan terbagi dua kolom di layar lebar agar baris teks tetap
// pendek (HIG: panjang baris nyaman ±60–75 karakter).
export default function InsightsCard({ reasoning, saran }) {
  return (
    <section
      className="relative overflow-hidden rounded-card bg-gradient-to-br from-[#E9F2FF] via-[#EDF5FF] to-[#E4F6F1] p-5 sm:p-6"
      aria-labelledby="insights-title"
    >
      <div className="flex items-start justify-between gap-4">
        <h2 id="insights-title" className="text-title3 font-semibold text-label">
          Insight
        </h2>
        <span className="text-ios-blue" aria-hidden="true">
          <Sparkles size={24} />
        </span>
      </div>

      <div className="mt-4 grid gap-x-10 gap-y-5 lg:grid-cols-2">
        <div>
          <h3 className="text-headline font-semibold text-label">Penjelasan</h3>
          <ul className="mt-2.5 flex flex-col gap-2.5">
            {reasoning.map((line, i) => (
              <li key={`r-${i}`} className="flex gap-2.5 text-subhead leading-[1.5] text-label">
                <span className="mt-[7px] h-1.5 w-1.5 flex-shrink-0 rounded-full bg-label-tertiary" />
                <span>
                  <span className="font-semibold">{REASONING_LEADS[i] || 'Catatan'}</span>
                  <span className="text-label-secondary"> — {line}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h3 className="text-headline font-semibold text-label">Rekomendasi</h3>
          <ul className="mt-2.5 flex flex-col gap-2.5">
            {saran.map((line, i) => (
              <li
                key={`s-${i}`}
                className="flex gap-2.5 text-subhead leading-[1.5] text-label-secondary"
              >
                <span className="mt-[7px] h-1.5 w-1.5 flex-shrink-0 rounded-full bg-ios-blue/60" />
                <span>{line}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-white/60 pt-4">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-surface/80 px-2.5 py-1.5 text-footnote font-medium text-ios-blue backdrop-blur-sm">
          <Brain size={15} />
          RAG Context
        </span>
        <span className="text-caption text-label-secondary">Bersumber dari analisis LLM-RAG</span>
      </div>
    </section>
  );
}
