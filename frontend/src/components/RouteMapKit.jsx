import { useEffect, useRef, useState } from 'react';
import { onMapkitFailure } from '../lib/places.js';

export default function RouteMapKit({ routes, selectedId, onSelect, onFallback }) {
  const elRef = useRef(null);
  const mapRef = useRef(null);
  const onSelectRef = useRef(onSelect);
  const onFallbackRef = useRef(onFallback);
  onSelectRef.current = onSelect;
  onFallbackRef.current = onFallback;

  const [gagal, setGagal] = useState(false);

  // MapKit bisa berubah tidak sah di tengah sesi (token kedaluwarsa, kuota
  // habis). Itu tidak melempar exception, jadi harus didengarkan lewat event.
  useEffect(() => {
    return onMapkitFailure((alasan) => {
      console.warn(`[RouteMapKit] MapKit tidak bisa dipakai (${alasan}) — kembali ke Leaflet`);
      setGagal(true);
      onFallbackRef.current?.();
    });
  }, []);

  useEffect(() => {
    if (mapRef.current || !elRef.current) return;
    const { mapkit } = window;
    if (!mapkit) {
      onFallbackRef.current?.();
      return;
    }

    let map;
    try {
      map = new mapkit.Map(elRef.current, {
        showsMapTypeControl: false,
        showsUserLocationControl: false,
        showsScale: mapkit.FeatureVisibility?.Adaptive,
        isRotationEnabled: false,
        colorScheme: mapkit.Map.ColorSchemes?.Light,
      });
    } catch (e) {
      console.warn('[RouteMapKit] gagal membuat peta, kembali ke Leaflet:', e);
      setGagal(true);
      onFallbackRef.current?.();
      return;
    }

    map.addEventListener('select', (ev) => {
      const id = ev?.overlay?.data?.routeId;
      if (id && onSelectRef.current) onSelectRef.current(id);
    });

    mapRef.current = map;
    return () => {
      try {
        map.destroy();
      } catch {
      }
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const { mapkit } = window;
    if (!map || !mapkit || !routes?.length) return;

    const koor = (pair) => new mapkit.Coordinate(pair[0], pair[1]);
    const garis = (coords, opsi, data) => {
      const o = new mapkit.PolylineOverlay(coords.map(koor), {
        style: new mapkit.Style({ lineJoin: 'round', lineCap: 'round', ...opsi }),
      });
      if (data) o.data = data;
      return o;
    };

    try {
      map.removeOverlays(map.overlays);
      map.removeAnnotations(map.annotations);
    } catch {
    }

    const overlays = [];
    const annotations = [];
    let semuaTitik = [];

    routes
      .filter((r) => r.id !== selectedId)
      .forEach((route) => {
        if (!route.coords || route.coords.length < 2) return;
        semuaTitik = semuaTitik.concat(route.coords);
        overlays.push(
          garis(
            route.coords,
            {
              strokeColor: route.color,
              lineWidth: 4,
              strokeOpacity: 0.45,
              lineDash: route.approxGeometry ? [4, 6] : [2, 8],
            },
            { routeId: route.id }
          )
        );
      });

    const selected = routes.find((r) => r.id === selectedId);
    if (selected && selected.coords?.length >= 2) {
      semuaTitik = semuaTitik.concat(selected.coords);

      overlays.push(
        garis(selected.coords, { strokeColor: '#ffffff', lineWidth: 11, strokeOpacity: 0.9 })
      );

      const slices = selected.statusSlices?.length
        ? selected.statusSlices
        : [{ coords: selected.coords, status: selected.status }];

      slices.forEach((slice) => {
        if (!slice.coords || slice.coords.length < 2) return;
        overlays.push(
          garis(
            slice.coords,
            {
              strokeColor: slice.status?.dot || '#16a34a',
              lineWidth: 7,
              strokeOpacity: 0.95,
              ...(selected.approxGeometry ? { lineDash: [4, 6] } : {}),
            },
            { routeId: selected.id }
          )
        );
      });

      const mid = selected.coords[Math.floor(selected.coords.length / 2)];
      annotations.push(
        new mapkit.Annotation(
          koor(mid),
          () => {
            const el = document.createElement('div');
            el.style.cssText =
              'background:#0d9488;color:#fff;font:700 11px system-ui,sans-serif;' +
              'padding:4px 10px;border-radius:999px;white-space:nowrap;' +
              'box-shadow:0 2px 6px rgba(0,0,0,0.25);letter-spacing:0.02em;';
            el.textContent = selected.isBest ? 'TERBAIK' : 'DIPILIH';
            return el;
          },
          { anchorOffset: new DOMPoint(0, -2) }
        )
      );
    }

    const first = routes.find((r) => r.coords && r.coords.length >= 2);
    if (first) {
      const pin = (pair, warna, judul) =>
        new mapkit.Annotation(
          koor(pair),
          () => {
            const el = document.createElement('div');
            el.style.cssText =
              'width:16px;height:16px;border-radius:50% 50% 50% 0;background:' +
              warna +
              ';transform:rotate(-45deg);border:2px solid #fff;' +
              'box-shadow:0 1px 4px rgba(0,0,0,0.4);';
            return el;
          },
          { title: judul, anchorOffset: new DOMPoint(0, -8) }
        );
      annotations.push(pin(first.coords[0], '#0f172a', 'Asal'));
      annotations.push(pin(first.coords[first.coords.length - 1], '#dc2626', 'Tujuan'));
    }

    try {
      if (overlays.length) map.addOverlays(overlays);
      if (annotations.length) map.addAnnotations(annotations);

      if (semuaTitik.length) {
        let utara = -90, selatan = 90, timur = -180, barat = 180;
        for (const [lat, lon] of semuaTitik) {
          if (lat > utara) utara = lat;
          if (lat < selatan) selatan = lat;
          if (lon > timur) timur = lon;
          if (lon < barat) barat = lon;
        }
        const padLat = Math.max((utara - selatan) * 0.12, 0.02);
        const padLon = Math.max((timur - barat) * 0.12, 0.02);
        map.region = new mapkit.BoundingRegion(
          utara + padLat, timur + padLon, selatan - padLat, barat - padLon
        ).toCoordinateRegion();
      }
    } catch (e) {
      console.warn('[RouteMapKit] gagal menggambar rute, kembali ke Leaflet:', e);
      setGagal(true);
      onFallbackRef.current?.();
    }
  }, [routes, selectedId]);

  const anyApprox = routes?.some((r) => r.approxGeometry);

  if (gagal) return null;

  return (
    <div className="relative h-full w-full">
      <div ref={elRef} className="h-full w-full overflow-hidden rounded-xl bg-slate-200" />
      {anyApprox && (
        <div className="pointer-events-none absolute bottom-2 left-2 right-2 rounded-md bg-white/90 px-2.5 py-1.5 text-[10.5px] leading-snug text-slate-500 shadow">
          Jalur putus-putus digambar lurus karena server rute (OSRM) sedang tak terjangkau,
          jadi bentuk jalannya belum tersedia — jarak, ETA, dan biaya tetap dari perhitungan asli.
        </div>
      )}
    </div>
  );
}
