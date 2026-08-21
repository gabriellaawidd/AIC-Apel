// MapKit JS loader + Search helpers.
//
// Token: taruh JWT-nya di .env sebagai VITE_MAPKIT_TOKEN.
// Kalau token di-sign server-side (disarankan, karena JWT punya masa berlaku),
// isi VITE_MAPKIT_TOKEN_URL — endpoint yang mengembalikan token mentah (text/plain
// atau JSON {"token": "..."}). URL menang di atas token statis.
const STATIC_TOKEN = import.meta.env.VITE_MAPKIT_TOKEN;
const TOKEN_URL = import.meta.env.VITE_MAPKIT_TOKEN_URL;

const MAPKIT_SRC = 'https://cdn.apple-mapkit.com/mk/5.x.x/mapkit.core.js';

// Bias pencarian ke wilayah Indonesia (tanpa geolokasi browser).
// Center kira-kira di Laut Jawa supaya seluruh kepulauan tercakup.
export const INDONESIA_CENTER = { latitude: -2.5, longitude: 118.0 };
export const INDONESIA_SPAN = { latitudeDelta: 22, longitudeDelta: 46 };

// Bias yang lebih rapat untuk Jawa — dipakai sebagai region default pencarian
// supaya hasil terdekat muncul lebih dulu untuk koridor Jabodetabek–Jabar.
export const JAWA_CENTER = { latitude: -6.9, longitude: 108.0 };
export const JAWA_SPAN = { latitudeDelta: 6, longitudeDelta: 10 };

let loadPromise = null;

async function fetchToken() {
  if (TOKEN_URL) {
    const res = await fetch(TOKEN_URL, { credentials: 'omit' });
    if (!res.ok) throw new Error(`Gagal ambil token MapKit (${res.status})`);
    const ct = res.headers.get('content-type') || '';
    if (ct.includes('application/json')) {
      const body = await res.json();
      return body.token || body.jwt || body.accessToken;
    }
    return (await res.text()).trim();
  }
  return STATIC_TOKEN;
}

export function hasMapkitConfig() {
  return Boolean(TOKEN_URL || STATIC_TOKEN);
}

// Muat mapkit.core.js sekali, init dengan authorizationCallback, resolve ke window.mapkit.
export function loadMapkit() {
  if (loadPromise) return loadPromise;

  loadPromise = new Promise((resolve, reject) => {
    if (!hasMapkitConfig()) {
      reject(new Error('VITE_MAPKIT_TOKEN atau VITE_MAPKIT_TOKEN_URL belum diisi'));
      return;
    }

    const init = () => {
      try {
        window.mapkit.init({
          authorizationCallback: (done) => {
            fetchToken()
              .then((t) => done(t))
              .catch((err) => reject(err));
          },
          language: 'id',
        });
        resolve(window.mapkit);
      } catch (err) {
        reject(err);
      }
    };

    if (window.mapkit && window.mapkit.Search) {
      init();
      return;
    }

    const existing = document.querySelector(`script[src="${MAPKIT_SRC}"]`);
    if (existing) {
      existing.addEventListener('load', init, { once: true });
      existing.addEventListener('error', () => reject(new Error('Gagal memuat MapKit JS')), {
        once: true,
      });
      return;
    }

    const script = document.createElement('script');
    script.src = MAPKIT_SRC;
    script.crossOrigin = 'anonymous';
    script.async = true;
    // libraries=services memuat mapkit.Search / Geocoder tanpa memuat renderer peta.
    script.dataset.libraries = 'services';
    script.dataset.callback = '__initMapKitBridge';
    window.__initMapKitBridge = init;
    script.onerror = () => reject(new Error('Gagal memuat MapKit JS'));
    document.head.appendChild(script);
  }).catch((err) => {
    loadPromise = null; // biar bisa dicoba lagi
    throw err;
  });

  return loadPromise;
}

// mapkit.CoordinateRegion untuk membatasi/membias hasil pencarian.
export function regionFor(mapkit, center = JAWA_CENTER, span = JAWA_SPAN) {
  return new mapkit.CoordinateRegion(
    new mapkit.Coordinate(center.latitude, center.longitude),
    new mapkit.CoordinateSpan(span.latitudeDelta, span.longitudeDelta),
  );
}

// Bentuk seragam untuk hasil autocomplete, apa pun variannya.
export function normalizeResult(raw) {
  const lines = raw.displayLines && raw.displayLines.length ? raw.displayLines : null;
  const title = lines ? lines[0] : raw.name || raw.title || '';
  const subtitle = lines && lines.length > 1 ? lines.slice(1).join(', ') : raw.formattedAddress || '';
  const coord = raw.coordinate;

  return {
    id: raw.muid || raw._wpURL || `${title}|${subtitle}`,
    title,
    subtitle,
    label: subtitle ? `${title}, ${subtitle}` : title,
    coordinate: coord ? { latitude: coord.latitude, longitude: coord.longitude } : null,
    raw,
  };
}
