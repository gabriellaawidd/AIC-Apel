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
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          "'Segoe UI'",
          'Helvetica',
          'Arial',
          'sans-serif',
        ],
      },
      boxShadow: {
        card: '0 1px 3px rgba(15,23,42,0.08)',
        modal: '0 20px 60px rgba(0,0,0,0.3)',
      },
    },
  },
  plugins: [],
}
