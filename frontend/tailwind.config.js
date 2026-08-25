/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Brand palette lifted directly from the Cold Chain Router design
        navy: '#0f2f5c',
        brand: '#2a78d6',
        teal: '#0d9488',
        // [4 · 2026-08-23] Palet netral mengikuti Apple HIG: teks nyaris hitam
        // (bukan hitam pekat), dan field abu-abu lembut ala kontrol sistem iOS.
        ink: '#1c1c1e',
        fieldbg: '#f2f2f7',
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          "'SF Pro Text'",
          "'Segoe UI'",
          'Helvetica',
          'Arial',
          'sans-serif',
        ],
      },
      boxShadow: {
        // Bayangan HIG: sangat tipis, dua lapis, tanpa kesan mengambang berlebihan
        card: '0 1px 2px rgba(15,23,42,0.05), 0 6px 20px rgba(15,23,42,0.05)',
        modal: '0 24px 70px rgba(0,0,0,0.28)',
        pop: '0 8px 30px rgba(15,23,42,0.14)',
        seg: '0 1px 3px rgba(15,23,42,0.12)',
      },
    },
  },
  plugins: [],
}
