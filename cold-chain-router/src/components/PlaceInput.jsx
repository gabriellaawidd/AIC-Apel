import { useEffect, useRef, useState } from 'react';
import { useMapkitSearch } from '../lib/useMapkitSearch.js';
import { FIELD_SHELL, FIELD_INPUT, FieldIcon } from './Field.jsx';
import { CheckSeal } from './Icons.jsx';

// Input alamat dengan saran otomatis dari MapKit Search.
// value  : { label, coordinate } | null
// onChange: dipanggil saat user memilih saran (atau mengetik bebas)
export default function PlaceInput({ value, onChange, placeholder, ariaLabel, icon, id }) {
  const [text, setText] = useState(value?.label || '');
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const wrapRef = useRef(null);
  const skipNextQuery = useRef(false);

  const { ready, error, loading, results, resolvePlace, clear } = useMapkitSearch(
    skipNextQuery.current ? '' : text,
  );

  // Sinkron kalau value diganti dari luar.
  useEffect(() => {
    if (value?.label && value.label !== text) {
      skipNextQuery.current = true;
      setText(value.label);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value?.label]);

  // Tutup dropdown saat klik di luar.
  useEffect(() => {
    const onDoc = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  const pick = async (item) => {
    skipNextQuery.current = true;
    setText(item.label);
    setOpen(false);
    clear();
    const resolved = await resolvePlace(item);
    setText(resolved.label);
    onChange({ label: resolved.label, coordinate: resolved.coordinate });
  };

  const onKeyDown = (e) => {
    if (!open || !results.length) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlight((h) => (h + 1) % results.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlight((h) => (h - 1 + results.length) % results.length);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      pick(results[highlight]);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  const showList = open && (loading || results.length > 0);

  return (
    <div ref={wrapRef} className="relative">
      <div className={FIELD_SHELL}>
        {icon && <FieldIcon as={icon} />}
        <input
          id={id}
          type="text"
          role="combobox"
          aria-expanded={showList}
          aria-autocomplete="list"
          aria-label={ariaLabel}
          autoComplete="off"
          value={text}
          placeholder={placeholder}
          onChange={(e) => {
            skipNextQuery.current = false;
            setText(e.target.value);
            setHighlight(0);
            setOpen(true);
            onChange({ label: e.target.value, coordinate: null });
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          className={FIELD_INPUT}
        />
        {/* Koordinat sudah terkunci dari MapKit */}
        {value?.coordinate && !showList && (
          <span
            className="flex-shrink-0 text-ios-green"
            title={`${value.coordinate.latitude.toFixed(4)}, ${value.coordinate.longitude.toFixed(4)}`}
            aria-label="Koordinat terkunci"
          >
            <CheckSeal size={17} />
          </span>
        )}
      </div>

      {showList && (
        <ul
          role="listbox"
          className="absolute left-0 right-0 top-[calc(100%+6px)] z-[1500] max-h-[264px] animate-fadeIn overflow-auto rounded-[14px] border border-separator bg-surface/95 p-1 shadow-popover backdrop-blur-xl"
        >
          {loading && results.length === 0 && (
            <li className="px-3 py-2.5 text-footnote text-label-tertiary">Mencari…</li>
          )}
          {results.map((r, i) => (
            <li key={r.id} role="option" aria-selected={i === highlight}>
              <button
                type="button"
                onMouseEnter={() => setHighlight(i)}
                onClick={() => pick(r)}
                className={`block w-full rounded-[10px] px-3 py-2 text-left transition-colors ${
                  i === highlight ? 'bg-fill-tertiary' : 'bg-transparent'
                }`}
              >
                <span className="block truncate text-callout text-label">{r.title}</span>
                {r.subtitle && (
                  <span className="block truncate text-footnote text-label-secondary">{r.subtitle}</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}

      {error && open && text.length >= 2 && (
        <p className="mt-1.5 text-caption text-ios-orange">
          {error === 'token'
            ? 'Saran alamat nonaktif — isi VITE_MAPKIT_TOKEN di .env'
            : `Saran alamat nonaktif — ${error}`}
        </p>
      )}
      {!ready && !error && text.length >= 2 && (
        <p className="mt-1.5 text-caption text-label-tertiary">Menyiapkan MapKit…</p>
      )}
    </div>
  );
}
