import { useEffect, useRef, useState } from 'react';
import { searchPlaces, initMapkit, providerName } from '../lib/places.js';

export default function PlaceInput({ value, onChange, placeholder, icon }) {
  const [text, setText] = useState(value?.label || '');
  const [hits, setHits] = useState([]);
  const [provider, setProvider] = useState(providerName());
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  // Alasan dari server kalau daftar saran kosong (mis. Nominatim menolak).
  const [galat, setGalat] = useState('');
  const [highlight, setHighlight] = useState(0);
  const boxRef = useRef(null);
  const abortRef = useRef(null);

  useEffect(() => {
    initMapkit().then(() => setProvider(providerName()));
  }, []);

  useEffect(() => {
    setText(value?.label || '');
  }, [value?.label]);

  useEffect(() => {
    const onDocClick = (e) => {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);

  useEffect(() => {
    const q = text.trim();
    if (q.length < 3 || q === value?.label) {
      setHits([]);
      return;
    }
    const timer = setTimeout(async () => {
      abortRef.current?.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      setLoading(true);
      try {
        const res = await searchPlaces(q, ctrl.signal);
        setHits(res.results);
        setProvider(res.provider);
        setGalat(res.error || '');
        setHighlight(0);
        setOpen(true);
      } catch {
        setHits([]);
      } finally {
        setLoading(false);
      }
    }, 350);
    return () => clearTimeout(timer);
  }, [text, value?.label]);

  const pick = (hit) => {
    onChange({ label: hit.label, lon: hit.lon, lat: hit.lat, address: hit.address, key: hit.key });
    setText(hit.label);
    setOpen(false);
  };

  const onKeyDown = (e) => {
    if (!open || !hits.length) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlight((h) => Math.min(h + 1, hits.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlight((h) => Math.max(h - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      pick(hits[highlight]);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  return (
    <div ref={boxRef} className="relative">
      <div className="flex items-center gap-2.5 rounded-xl bg-fieldbg px-3.5 py-3 ring-1 ring-transparent transition focus-within:bg-white focus-within:ring-brand/40">
        <span className="flex-shrink-0 text-slate-400">{icon}</span>
        <input
          type="text"
          value={text}
          placeholder={placeholder}
          onChange={(e) => setText(e.target.value)}
          onFocus={() => hits.length && setOpen(true)}
          onKeyDown={onKeyDown}
          autoComplete="off"
          className="w-full bg-transparent text-[15px] text-ink outline-none placeholder:text-slate-400"
        />
        {loading && <Spinner />}
      </div>

      {open && (
        <ul className="absolute z-[1200] mt-1.5 max-h-72 w-full overflow-auto rounded-2xl border border-black/5 bg-white/95 py-1.5 shadow-pop backdrop-blur">
          {hits.length === 0 && !loading && (
            <li className="px-4 py-3 text-[13px] text-slate-400">
              {galat
                ? `Layanan pencarian lokasi bermasalah: ${galat}`
                : 'Tidak ada tempat yang cocok. Tambahkan nama kota, misalnya “Caringin Bandung”.'}
            </li>
          )}
          {hits.map((hit, i) => (
            <li key={hit.key || `${hit.lat},${hit.lon}`}>
              <button
                type="button"
                onMouseEnter={() => setHighlight(i)}
                onClick={() => pick(hit)}
                className={`flex w-full items-start gap-2.5 px-4 py-2.5 text-left transition ${
                  i === highlight ? 'bg-slate-100' : 'bg-transparent'
                }`}
              >
                <span className="mt-0.5 flex-shrink-0 text-slate-300">{PinIcon}</span>
                <span className="min-w-0">
                  <span className="block truncate text-[14px] font-medium text-ink">{hit.label}</span>
                  {hit.address && (
                    <span className="block truncate text-[12px] text-slate-400">{hit.address}</span>
                  )}
                </span>
              </button>
            </li>
          ))}
          <li className="border-t border-slate-100 px-4 pb-0.5 pt-2 text-[11px] text-slate-400">
            Saran lokasi dari {provider}
          </li>
        </ul>
      )}
    </div>
  );
}

function Spinner() {
  return (
    <span className="h-3.5 w-3.5 flex-shrink-0 animate-spin rounded-full border-2 border-slate-300 border-t-transparent" />
  );
}

const PinIcon = (
  <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <path
      d="M8 1.5c-2.5 0-4.5 2-4.5 4.5 0 3.2 4.5 8 4.5 8s4.5-4.8 4.5-8c0-2.5-2-4.5-4.5-4.5Z"
      stroke="currentColor"
      strokeWidth="1.3"
    />
    <circle cx="8" cy="6" r="1.6" fill="currentColor" />
  </svg>
);
