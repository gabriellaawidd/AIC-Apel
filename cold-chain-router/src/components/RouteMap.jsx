import { useEffect, useRef } from 'react';
import L from 'leaflet';
import { SEGMENT_STATUS_COLOR } from '../lib/data.js';

// Leaflet map that draws all candidate routes, emphasises the selected one,
// and (in heat mode) colours the selected route segment-by-segment by risk.
// Ported from the design's RouteMap.jsx class component to a hook component.
export default function RouteMap({ routes, selectedId, heatMode, onSelect }) {
  const elRef = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  // Initialise the map exactly once.
  useEffect(() => {
    if (mapRef.current || !elRef.current) return;
    const map = L.map(elRef.current, { scrollWheelZoom: false });
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 18,
    }).addTo(map);
    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
    };
  }, []);

  // Redraw whenever the routes or selection change.
  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;

    layer.clearLayers();
    if (!routes || !routes.length) return;

    let allBounds = [];
    routes.forEach((route) => {
      const isSelected = route.id === selectedId;
      allBounds = allBounds.concat(route.coords);

      if (heatMode && isSelected && route.segments) {
        route.segments.forEach((seg) => {
          L.polyline(seg.coords, {
            color: SEGMENT_STATUS_COLOR[seg.status] || route.color,
            weight: 7,
            opacity: 0.95,
          }).addTo(layer);
        });
      } else {
        const line = L.polyline(route.coords, {
          color: route.color,
          weight: isSelected ? 7 : 4,
          opacity: isSelected ? 0.95 : 0.4,
          dashArray: isSelected ? null : '2 8',
        }).addTo(layer);
        line.on('click', () => onSelectRef.current && onSelectRef.current(route.id));
      }

      if (isSelected) {
        const mid = route.coords[Math.floor(route.coords.length / 2)];
        L.marker(mid, {
          icon: L.divIcon({
            className: '',
            html:
              '<div style="background:#0d9488;color:#fff;font:700 11px system-ui,sans-serif;padding:4px 10px;border-radius:999px;white-space:nowrap;box-shadow:0 2px 6px rgba(0,0,0,0.25);letter-spacing:0.02em;">TERBAIK</div>',
            iconSize: [0, 0],
          }),
        }).addTo(layer);
      }
    });

    const start = routes[0].coords[0];
    const end = routes[0].coords[routes[0].coords.length - 1];
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

    if (allBounds.length) {
      map.fitBounds(allBounds, { padding: [30, 30] });
    }
    setTimeout(() => mapRef.current && mapRef.current.invalidateSize(), 50);
  }, [routes, selectedId, heatMode]);

  return <div ref={elRef} className="h-full w-full overflow-hidden rounded-xl bg-slate-200" />;
}
