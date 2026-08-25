import { useEffect, useState } from 'react';
import { initMapkit, onMapkitFailure } from '../lib/places.js';
import RouteMapKit from './RouteMapKit.jsx';
import RouteMapLeaflet from './RouteMapLeaflet.jsx';

// Pemilih penyedia peta.
//
// PERBAIKAN 2026-08-25 — dua masalah pada versi sebelumnya:
//
//  1. Selama menunggu jawaban MapKit, komponen menampilkan kotak abu-abu
//     kosong. Kalau MapKit tidak pernah menjawab, kotak itu tinggal selamanya.
//  2. `initMapkit()` dulu mengembalikan "siap" begitu skrip termuat, padahal
//     kegagalan otorisasi MapKit datang belakangan lewat event. Akibatnya
//     RouteMapKit dipakai, peta terbentuk, garis rute tergambar — tetapi ubin
//     petanya tidak pernah datang. Yang terlihat: latar krem berpetak
//     bertuliskan "Legal", tanpa satu pun permintaan tile di tab Network.
//
// Sekarang urutannya dibalik: Leaflet ditampilkan LEBIH DULU supaya peta selalu
// muncul, lalu ditingkatkan ke Apple Maps hanya setelah MapKit benar-benar
// mengonfirmasi dirinya siap. Kalau MapKit gagal di tengah jalan, kita turun
// lagi ke Leaflet.
export default function RouteMap(props) {
  const [penyedia, setPenyedia] = useState('osm');

  useEffect(() => {
    let hidup = true;
    initMapkit()
      .then((siap) => hidup && siap && setPenyedia('apple'))
      .catch(() => {});
    const lepas = onMapkitFailure(() => hidup && setPenyedia('osm'));
    return () => {
      hidup = false;
      lepas();
    };
  }, []);

  if (penyedia === 'apple') {
    return <RouteMapKit {...props} onFallback={() => setPenyedia('osm')} />;
  }
  return <RouteMapLeaflet {...props} />;
}
