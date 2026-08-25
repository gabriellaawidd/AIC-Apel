import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // PENTING 2026-08-25 — Vite 5.4.12+ menyaring header Host sebagai fitur
    // keamanan: permintaan dengan hostname di luar daftar ini ditolak dengan
    // "Blocked request. This host is not allowed", walaupun hostname-nya sudah
    // diarahkan ke 127.0.0.1 lewat /etc/hosts.
    //
    // `mapkit-aic.com` didaftarkan karena token MapKit JS proyek ini dikunci
    // ke domain tersebut (klaim `origin` di dalam token). Membuka aplikasi
    // lewat http://mapkit-aic.com:5173 membuat origin halaman cocok dengan
    // token, sehingga Apple Maps mau dipakai. Untuk localhost biasa, MapKit
    // ditolak dan peta otomatis memakai OpenStreetMap — lihat lib/places.js.
    // Vite secara bawaan hanya mengikat diri ke "localhost", yang di macOS
    // kerap berarti IPv6 (::1) saja. Hostname buatan di /etc/hosts diarahkan
    // ke IPv4 127.0.0.1, sehingga koneksinya ditolak (ERR_CONNECTION_REFUSED)
    // meski DNS-nya sudah benar. `host: true` membuat Vite mendengarkan di
    // semua antarmuka, termasuk 127.0.0.1.
    host: true,
    allowedHosts: ['dev.mapkit-aic.com', 'mapkit-aic.com', 'localhost', '127.0.0.1'],

    // Backend (FastAPI/uvicorn, see ../backend/api.py) is started automatically
    // by `npm run dev` (see package.json's dev script + scripts/dev-backend.mjs).
    // Proxying /api here means the frontend code never needs to know the
    // backend's host/port, and there's no CORS to worry about in dev.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
