import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';

// Peta Leaflet — dipakai sebagai penyedia utama, dan sebagai jaring pengaman
// ketika Apple MapKit tidak bisa dipakai (lihat RouteMap.jsx).
//
// PATCH 2026-08-23:
//  [1] Geometri yang digambar sekarang polyline OSRM yang disederhanakan
//      dengan Douglas-Peucker (~11 m) di backend/routing.py, bukan lagi 40
//      titik hasil downsample. Garis mengikuti bentuk jalan, tidak lagi
//      memotong gunung/sawah/laut.
//  [9] Rute terpilih digambar PER SEGMEN dengan warna status kesegarannya
//      (aman/waspada/berisiko) dari backend/engine.py. Legend akhirnya
//      bermakna: sebuah perjalanan bisa berangkat hijau lalu menguning.
//      Rute yang tidak terpilih tetap satu warna identitas supaya peta
//      tidak menjadi pelangi yang membingungkan.
// PATCH 2026-08-23 — peta dasar (tile) kadang gagal dimuat sementara garis rute
// tetap tergambar, sehingga yang terlihat hanya latar kosong berpetak. Dulu
// kegagalan itu tidak terdeteksi sama sekali. Sekarang:
//   1. kegagalan tile dihitung; setelah beberapa kali gagal, penyedia peta
//      otomatis berpindah ke cadangan;
//   2. kalau semua penyedia gagal, muncul keterangan jelas di atas peta —
//      bukan latar kosong tanpa penjelasan.
const TILE_PROVIDERS = [
  {
    name: 'OpenStreetMap',
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; OpenStreetMap contributors',
    maxZoom: 18,
  },
  {
    name: 'Carto Light',
    url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
    subdomains: 'abcd',
    maxZoom: 19,
  },
  {
    name: 'Esri World Street Map',
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles &copy; Esri',
    maxZoom: 19,
  },
];

export default function RouteMapLeaflet({ routes, selectedId, onSelect }) {
  const elRef = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const tileRef = useRef(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  const [providerIdx, setProviderIdx] = useState(0);
  const [tilesBroken, setTilesBroken] = useState(false);

  useEffect(() => {
    if (mapRef.current || !elRef.current) return;
    const map = L.map(elRef.current, { scrollWheelZoom: false });
    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
      tileRef.current = null;
    };
  }, []);

  // Lapisan tile dipasang terpisah supaya bisa diganti tanpa membangun ulang peta.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const provider = TILE_PROVIDERS[providerIdx];
    if (tileRef.current) {
      map.removeLayer(tileRef.current);
      tileRef.current = null;
    }

    let errors = 0;
    let loadedOne = false;
    const layer = L.tileLayer(provider.url, {
      attribution: provider.attribution,
      maxZoom: provider.maxZoom,
      subdomains: provider.subdomains || 'abc',
      crossOrigin: true,
    });

    layer.on('tileload', () => {
      loadedOne = true;
      setTilesBroken(false);
    });

    layer.on('tileerror', () => {
      errors += 1;
      // Beberapa tile gagal itu wajar (di luar cakupan). Kalau tidak ada satu
      // pun yang berhasil setelah 6 kegagalan, penyedia ini dianggap bermasalah.
      if (loadedOne || errors < 6) return;
      if (providerIdx < TILE_PROVIDERS.length - 1) {
        console.warn(
          `[peta] ${provider.name} tidak bisa dimuat, beralih ke ${TILE_PROVIDERS[providerIdx + 1].name}`
        );
        setProviderIdx((i) => i + 1);
      } else {
        setTilesBroken(true);
      }
    });

    layer.addTo(map);
    layer.bringToBack();
    tileRef.current = layer;
  }, [providerIdx]);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;

    layer.clearLayers();
    if (!routes || !routes.length) return;

    let allBounds = [];

    // 1) rute yang TIDAK dipilih — tipis, warna identitas, di lapisan bawah
    routes
      .filter((r) => r.id !== selectedId)
      .forEach((route) => {
        if (!route.coords || route.coords.length < 2) return;
        allBounds = allBounds.concat(route.coords);
        const line = L.polyline(route.coords, {
          color: route.color,
          weight: 4,
          opacity: 0.45,
          dashArray: route.approxGeometry ? '4 6' : '2 8',
        }).addTo(layer);
        line.bindTooltip(`${route.name} — klik untuk memilih`, { sticky: true });
        line.on('click', () => onSelectRef.current && onSelectRef.current(route.id));
      });

    // 2) rute terpilih — tebal, diwarnai per segmen menurut status kesegaran
    const selected = routes.find((r) => r.id === selectedId);
    if (selected && selected.coords?.length >= 2) {
      allBounds = allBounds.concat(selected.coords);

      // garis dasar (halo) supaya potongan berwarna tetap terbaca di atas peta
      L.polyline(selected.coords, {
        color: '#ffffff',
        weight: 11,
        opacity: 0.9,
      }).addTo(layer);

      const slices = selected.statusSlices?.length
        ? selected.statusSlices
        : [{ coords: selected.coords, status: selected.status, statusKey: selected.statusKey }];

      slices.forEach((slice) => {
        const line = L.polyline(slice.coords, {
          color: slice.status?.dot || '#16a34a',
          weight: 7,
          opacity: 0.95,
          dashArray: selected.approxGeometry ? '4 6' : null,
        }).addTo(layer);
        if (slice.tempC != null) {
          line.bindTooltip(
            `Jam ${slice.fromH?.toFixed(1)}–${slice.toH?.toFixed(1)} · ` +
              `${slice.tempC?.toFixed(0)}°C · kesegaran ${slice.pctFresh?.toFixed(0)}% · ` +
              `${slice.status?.label}`,
            { sticky: true }
          );
        }
        line.on('click', () => onSelectRef.current && onSelectRef.current(selected.id));
      });

      const mid = selected.coords[Math.floor(selected.coords.length / 2)];
      L.marker(mid, {
        icon: L.divIcon({
          className: '',
          html:
            '<div style="background:#0d9488;color:#fff;font:700 11px system-ui,sans-serif;padding:4px 10px;border-radius:999px;white-space:nowrap;box-shadow:0 2px 6px rgba(0,0,0,0.25);letter-spacing:0.02em;">' +
            (selected.isBest ? 'TERBAIK' : 'DIPILIH') +
            '</div>',
          iconSize: [0, 0],
        }),
      }).addTo(layer);
    }

    const first = routes.find((r) => r.coords && r.coords.length >= 2);
    if (first) {
      const start = first.coords[0];
      const end = first.coords[first.coords.length - 1];
      const pin = (color) =>
        L.divIcon({
          className: '',
          html:
            '<div style="width:16px;height:16px;border-radius:50% 50% 50% 0;background:' +
            color +
            ';transform:rotate(-45deg);border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,0.4);"></div>',
          iconSize: [16, 16],
          iconAnchor: [8, 16],
        });
      L.marker(start, { icon: pin('#0f172a') }).bindTooltip('Asal').addTo(layer);
      L.marker(end, { icon: pin('#dc2626') }).bindTooltip('Tujuan').addTo(layer);
    }

    if (allBounds.length) {
      map.fitBounds(allBounds, { padding: [30, 30] });
    }
    setTimeout(() => mapRef.current && mapRef.current.invalidateSize(), 50);
  }, [routes, selectedId]);

  const anyApprox = routes?.some((r) => r.approxGeometry);
  const providerName = TILE_PROVIDERS[providerIdx]?.name;

  return (
    <div className="relative h-full w-full">
      <div ref={elRef} className="h-full w-full overflow-hidden rounded-[14px] bg-[#e8ecf0]" />

      {tilesBroken && (
        <div className="pointer-events-none absolute left-2 right-2 top-2 rounded-xl bg-white/95 px-3 py-2 text-[11.5px] leading-snug text-slate-600 shadow">
          <b className="text-ink">Peta dasar tidak bisa dimuat.</b> Garis rute, jarak, dan waktu
          tetap benar — yang gagal hanya gambar petanya. Biasanya karena jaringan memblokir server
          peta, atau ada ekstensi peramban yang mencegatnya.
        </div>
      )}

      {!tilesBroken && providerIdx > 0 && (
        <div className="pointer-events-none absolute left-2 top-2 rounded-lg bg-white/90 px-2 py-1 text-[10.5px] text-slate-500 shadow">
          Peta dasar: {providerName}
        </div>
      )}
      {anyApprox && (
        <div className="pointer-events-none absolute bottom-2 left-2 right-2 rounded-md bg-white/90 px-2.5 py-1.5 text-[10.5px] leading-snug text-slate-500 shadow">
          Jalur putus-putus digambar lurus karena server rute (OSRM) sedang tak terjangkau,
          jadi bentuk jalannya belum tersedia — jarak, ETA, dan biaya tetap dari perhitungan asli.
        </div>
      )}
    </div>
  );
}
