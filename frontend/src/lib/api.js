
const BASE = '/api';

async function request(path, options) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
  } catch (err) {
    throw new Error(
      'Tidak bisa menghubungi backend di /api. Pastikan `npm run dev` masih berjalan — ' +
        'ia menjalankan server backend (uvicorn) otomatis bersama Vite. ' +
        `(${err.message})`
    );
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return res.json();
}

export function fetchMeta() {
  return request('/meta');
}

export function planTrip(payload) {
  return request('/plan', { method: 'POST', body: JSON.stringify(payload) });
}

export function geocode(q, signal) {
  return request(`/geocode?q=${encodeURIComponent(q)}`, { signal });
}

export function fetchMapkitToken() {
  return request('/mapkit-token');
}

export function explainPlan(payload) {
  return request('/explain', {
    method: 'POST',
    body: JSON.stringify({ payload, use_llm: true }),
  });
}
