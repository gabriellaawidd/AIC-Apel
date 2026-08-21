import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { loadMapkit, regionFor, normalizeResult, hasMapkitConfig } from './mapkit.js';

// Hook autocomplete alamat berbasis mapkit.Search.
// - query di-debounce (default 220 ms)
// - hasil dibias ke region Indonesia/Jawa dan dibatasi ke negara ID
// - resolvePlace() melengkapi koordinat untuk hasil yang belum punya coordinate
export function useMapkitSearch(query, { debounceMs = 220, limit = 6, enabled = true } = {}) {
  const [ready, setReady] = useState(false);
  const [error, setError] = useState(hasMapkitConfig() ? null : 'token');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);

  const searchRef = useRef(null);
  const mapkitRef = useRef(null);
  const seqRef = useRef(0);

  // Init sekali saat komponen pertama memakai hook ini.
  useEffect(() => {
    if (!enabled || !hasMapkitConfig()) return;
    let cancelled = false;

    loadMapkit()
      .then((mapkit) => {
        if (cancelled) return;
        mapkitRef.current = mapkit;
        searchRef.current = new mapkit.Search({
          region: regionFor(mapkit),
          limitToCountries: 'ID',
          getsUserLocation: false,
          language: 'id',
        });
        setReady(true);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || 'MapKit gagal dimuat');
      });

    return () => {
      cancelled = true;
    };
  }, [enabled]);

  // Autocomplete ter-debounce.
  useEffect(() => {
    if (!enabled || !ready || !searchRef.current) return;
    const q = (query || '').trim();
    if (q.length < 2) {
      setResults([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    const seq = ++seqRef.current;
    const timer = setTimeout(() => {
      searchRef.current.autocomplete(
        q,
        (err, data) => {
          if (seq !== seqRef.current) return; // hasil basi, abaikan
          setLoading(false);
          if (err) {
            setResults([]);
            return;
          }
          const items = (data.results || []).map(normalizeResult).filter((r) => r.title);
          setResults(items.slice(0, limit));
        },
        { includeAddresses: true, includePointsOfInterest: true, includeQueries: false },
      );
    }, debounceMs);

    return () => clearTimeout(timer);
  }, [query, ready, enabled, debounceMs, limit]);

  // Hasil autocomplete kadang belum bawa koordinat — lengkapi lewat search().
  const resolvePlace = useCallback((item) => {
    if (!item) return Promise.resolve(null);
    if (item.coordinate || !searchRef.current) return Promise.resolve(item);

    return new Promise((resolve) => {
      searchRef.current.search(item.raw, (err, data) => {
        if (err || !data || !data.places || !data.places.length) {
          resolve(item);
          return;
        }
        const place = data.places[0];
        resolve({
          ...item,
          coordinate: place.coordinate
            ? { latitude: place.coordinate.latitude, longitude: place.coordinate.longitude }
            : null,
          label: place.formattedAddress || item.label,
        });
      });
    });
  }, []);

  const clear = useCallback(() => {
    seqRef.current++;
    setResults([]);
    setLoading(false);
  }, []);

  return useMemo(
    () => ({ ready, error, loading, results, resolvePlace, clear }),
    [ready, error, loading, results, resolvePlace, clear],
  );
}
