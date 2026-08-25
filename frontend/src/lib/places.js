
import { geocode, fetchMapkitToken } from './api.js';

const MAPKIT_SRC = 'https://cdn.apple-mapkit.com/mk/5.x.x/mapkit.js';

const ID_REGION = { lat: -2.5, lon: 118.0, latSpan: 20.0, lonSpan: 50.0 };

let mapkitState = 'idle';        // idle | loading | ready | unavailable
let mapkitReady = null;
const pemantauGagal = new Set(); // dipanggil kalau MapKit gagal SETELAH siap

// Dipakai komponen peta: daftarkan tindakan bila MapKit ternyata tidak sah
// (token kedaluwarsa, domain belum diizinkan) supaya bisa pindah ke Leaflet.
export function onMapkitFailure(fn) {
  pemantauGagal.add(fn);
  return () => pemantauGagal.delete(fn);
}

export function mapkitUsable() {
  return mapkitState === 'ready';
}

function loadScript(src) {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) return resolve();
    const el = document.createElement('script');
    el.src = src;
    el.crossOrigin = 'anonymous';
    el.async = true;
    el.onload = () => resolve();
    el.onerror = () => reject(new Error('gagal memuat MapKit JS'));
    document.head.appendChild(el);
  });
}

export function initMapkit() {
  if (mapkitReady) return mapkitReady;
  mapkitState = 'loading';
  mapkitReady = (async () => {
    try {
      const info = await fetchMapkitToken();
      console.log(
        `[MapKit] token dari backend: enabled=${info?.enabled} origin="${info?.origin ?? '-'}" ` +
          `expired=${info?.expired} | origin halaman="${window.location.origin}"`
      );
      if (!info?.enabled || !info.token) {
        mapkitState = 'unavailable';
        return false;
      }
      await loadScript(MAPKIT_SRC);

      // PERBAIKAN 2026-08-25 — `mapkit.init()` SELALU tampak berhasil.
      // Kegagalan otorisasi (token kedaluwarsa, atau Maps ID belum
      // mengizinkan domain seperti http://localhost:5173) baru muncul
      // ASINKRON lewat event, bukan sebagai exception. Karena dulu tidak
      // ditunggu, aplikasi mengira MapKit siap; peta terbentuk, garis rute
      // tergambar, tetapi ubin petanya tidak pernah datang — yang terlihat
      // hanya latar krem berpetak dengan tulisan "Legal".
      // Sekarang kita menunggu konfirmasi nyata dari MapKit.
      // MapKit menolak halaman yang origin-nya tidak cocok dengan klaim
      // `origin` di token. Dibandingkan di sini supaya pesan kegagalannya
      // menyebut sebab sebenarnya, bukan sekadar "Unauthorized".
      if (info.origin) {
        const asal = window.location.origin;                 // mis. http://localhost:5173
        const hostHalaman = window.location.hostname;   // mis. dev.mapkit-aic.com
        // Klaim origin bisa berupa domain persis ("mapkit-aic.com") ATAU
        // wildcard ("*.mapkit-aic.com"). Wildcard cocok dengan SUBDOMAIN saja —
        // "dev.mapkit-aic.com" cocok, "mapkit-aic.com" polos tidak.
        // Versi sebelumnya hanya membandingkan sama-persis, sehingga token
        // wildcard selalu dianggap tidak cocok dan MapKit tidak pernah dicoba.
        const cocok = info.origin.startsWith('*.')
          ? hostHalaman.endsWith(info.origin.slice(1)) &&
            hostHalaman !== info.origin.slice(2)
          : hostHalaman === info.origin;
        if (!cocok) {
          console.warn(
            `[MapKit] token dikunci ke "${info.origin}", sedangkan halaman ini ` +
            `dibuka di "${asal}". Apple akan menolaknya, jadi peta memakai ` +
            `OpenStreetMap. Perbaikan: ` +
            (info.origin.startsWith('*.')
              ? `buka lewat subdomain, mis. http://dev${info.origin.slice(1)}:5173 ` +
                `(arahkan ke 127.0.0.1 di /etc/hosts)`
              : `buka lewat domain ${info.origin}, atau buat token tanpa pembatasan domain`)
          );
          mapkitState = 'unavailable';
          return false;
        }
      }
      if (info.expired) {
        console.warn('[MapKit] token sudah kedaluwarsa — peta memakai OpenStreetMap.');
        mapkitState = 'unavailable';
        return false;
      }

      const mk = window.mapkit;
      const siap = await new Promise((resolve) => {
        let selesai = false;
        const tutup = (hasil, alasan) => {
          if (selesai) return;
          selesai = true;
          if (!hasil) console.warn(`[MapKit] tidak dipakai: ${alasan}`);
          resolve(hasil);
        };

        // Catat SEMUA kabar dari MapKit, bukan hanya yang kita harapkan.
        // Dua kali diagnosis sebelumnya meleset karena kita cuma melihat
        // status yang diasumsikan; sekarang apa pun yang dikirim MapKit
        // tercetak apa adanya di konsol.
        const t0 = Date.now();
        const jejak = (nama, ev) =>
          console.log(
            `[MapKit] +${Date.now() - t0}ms  event="${nama}"  status="${ev?.status}"`,
            ev
          );

        const onConfig = (ev) => {
          jejak('configuration-change', ev);
          if (ev?.status === 'Initialized' || ev?.status === 'Refreshed') tutup(true, '');
        };
        const onError = (ev) => {
          jejak('error', ev);
          const alasan = ev?.status || 'error tidak dikenal';
          mapkitState = 'unavailable';
          pemantauGagal.forEach((fn) => {
            try { fn(alasan); } catch { /* abaikan */ }
          });
          tutup(false, alasan);
        };

        mk.addEventListener('configuration-change', onConfig);
        mk.addEventListener('error', onError);
        mapkitErrorHandler = onError;   // tetap dipantau setelah init

        try {
          mk.init({
            authorizationCallback: (done) => done(info.token),
            language: 'id',
          });
        } catch (e) {
          tutup(false, e.message);
        }

        // Jaring pengaman: kalau tidak ada kabar sama sekali dalam 4 detik,
        // anggap MapKit tidak bisa dipakai daripada menampilkan peta kosong.
        // 4 detik ternyata bisa terlalu singkat pada jaringan lambat; MapKit
        // perlu mengambil konfigurasi dari server Apple lebih dulu.
        setTimeout(
          () => tutup(false, 'tidak ada konfirmasi dalam 8 detik (tidak ada event sama sekali)'),
          8000
        );
      });

      if (!siap) {
        mapkitState = 'unavailable';
        return false;
      }
      console.log(
        `[MapKit] siap — peta memakai Apple Maps (origin halaman "${window.location.origin}")`
      );
      mapkitState = 'ready';
      return true;
    } catch {
      mapkitState = 'unavailable';
      return false;
    }
  })();
  return mapkitReady;
}

export function providerName() {
  return mapkitState === 'ready' ? 'Apple Maps' : 'OpenStreetMap';
}

function mapkitRegion() {
  const { mapkit } = window;
  return new mapkit.CoordinateRegion(
    new mapkit.Coordinate(ID_REGION.lat, ID_REGION.lon),
    new mapkit.CoordinateSpan(ID_REGION.latSpan, ID_REGION.lonSpan)
  );
}

function normalizeMapkit(item, i) {
  const coord = item.coordinate || item.location;
  if (!coord) return null;
  const lines = item.displayLines || [];
  return {
    key: `mk:${i}:${coord.latitude.toFixed(5)},${coord.longitude.toFixed(5)}`,
    label: lines[0] || item.name || item.title || 'Tanpa nama',
    address: lines.slice(1).join(', ') || item.formattedAddress || '',
    lat: coord.latitude,
    lon: coord.longitude,
  };
}

function mapkitAutocomplete(query) {
  return new Promise((resolve) => {
    try {
      const search = new window.mapkit.Search({ region: mapkitRegion(), language: 'id' });
      search.autocomplete(query, (error, data) => {
        if (error || !data?.results) return resolve([]);
        resolve(
          data.results
            .map((r, i) => normalizeMapkit(r, i))
            .filter(Boolean)
            .slice(0, 6)
        );
      });
    } catch {
      resolve([]);
    }
  });
}

export async function searchPlaces(query, signal) {
  const q = (query || '').trim();
  if (q.length < 3) return { results: [], provider: providerName() };

  if (mapkitState === 'idle') await initMapkit();
  if (mapkitState === 'loading') await mapkitReady;

  if (mapkitState === 'ready') {
    const hits = await mapkitAutocomplete(q);
    if (hits.length) return { results: hits, provider: 'Apple Maps' };
  }

  try {
    const res = await geocode(q, signal);
    return {
      results: res.results || [],
      provider: res.source === 'photon' ? 'OpenStreetMap (Photon)' : 'OpenStreetMap',
      error: res.error || '',
    };
  } catch {
    return { results: [], provider: providerName() };
  }
}
