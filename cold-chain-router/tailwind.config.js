/** @type {import('tailwindcss').Config} */

// Apple-inspired design system for ColdChain AI.
// Mengambil prinsip dari Apple HIG:
// - clear visual hierarchy
// - restrained use of color
// - generous spacing
// - subtle surfaces and separators
// - system-first typography
// - semantic colors for status and data

export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],

  theme: {
    extend: {
      colors: {
        // ============================================================
        // BRAND / PRIMARY
        // ============================================================

        primary: {
          DEFAULT: '#007AFF',
          hover: '#0066D6',
          pressed: '#0055B8',
          light: '#EAF3FF',
        },

        // ============================================================
        // SEMANTIC COLORS
        // ============================================================

        success: {
          DEFAULT: '#34C759',
          light: '#EAF9EE',
          dark: '#248A3D',
        },

        warning: {
          DEFAULT: '#FF9500',
          light: '#FFF4E5',
          dark: '#C93400',
        },

        danger: {
          DEFAULT: '#FF3B30',
          light: '#FFF0EF',
          dark: '#D70015',
        },

        // AI / RAG accent
        ai: {
          DEFAULT: '#5AC8FA',
          light: '#EFFAFF',
          dark: '#007AFF',
        },

        // ============================================================
        // NEUTRALS
        // ============================================================

        canvas: '#F5F5F7',

        surface: {
          DEFAULT: '#FFFFFF',
          secondary: '#F9F9FB',
          tertiary: '#F2F2F7',
        },

        // ============================================================
        // TEXT HIERARCHY
        // ============================================================

        label: {
          DEFAULT: '#1D1D1F',
          secondary: '#6E6E73',
          tertiary: '#8E8E93',
          disabled: '#AEAEB2',
        },

        // ============================================================
        // UI FILLS
        // ============================================================

        fill: {
          DEFAULT: 'rgba(120, 120, 128, 0.16)',
          hover: 'rgba(120, 120, 128, 0.20)',
          secondary: 'rgba(120, 120, 128, 0.12)',
          tertiary: 'rgba(120, 120, 128, 0.08)',
          quaternary: 'rgba(120, 120, 128, 0.05)',
        },

        // Borders / dividers
        separator: {
          DEFAULT: '#D2D2D7',
          light: 'rgba(60, 60, 67, 0.12)',
          strong: 'rgba(60, 60, 67, 0.20)',
        },

        // ============================================================
        // MAP / ROUTE COLORS
        // ============================================================

        route: {
          DEFAULT: '#007AFF',
          selected: '#0066D6',
          alternative: '#8E8E93',
          origin: '#34C759',
          destination: '#FF3B30',
          waypoint: '#FF9500',
        },

        // ============================================================
        // APPLE SYSTEM COLOR REFERENCES
        // ============================================================

        ios: {
          blue: '#007AFF',
          indigo: '#5856D6',
          purple: '#AF52DE',
          pink: '#FF2D55',
          red: '#FF3B30',
          orange: '#FF9500',
          yellow: '#FFCC00',
          green: '#34C759',
          mint: '#00C7BE',
          teal: '#30B0C7',
          cyan: '#32ADE6',
          gray: '#8E8E93',
        },
      },

      // ==============================================================
      // TYPOGRAPHY
      // ==============================================================

      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          '"SF Pro Display"',
          '"SF Pro Text"',
          '"Segoe UI"',
          'Roboto',
          'Helvetica',
          'Arial',
          'sans-serif',
        ],
      },

      fontSize: {
        // Dashboard page title
        display: [
          '32px',
          {
            lineHeight: '38px',
            letterSpacing: '-0.022em',
            fontWeight: '700',
          },
        ],

        // Large section heading
        title: [
          '24px',
          {
            lineHeight: '30px',
            letterSpacing: '-0.019em',
            fontWeight: '600',
          },
        ],

        title2: [
          '20px',
          {
            lineHeight: '25px',
            letterSpacing: '-0.016em',
            fontWeight: '600',
          },
        ],

        title3: [
          '17px',
          {
            lineHeight: '22px',
            letterSpacing: '-0.014em',
            fontWeight: '600',
          },
        ],

        // Important UI text
        headline: [
          '16px',
          {
            lineHeight: '21px',
            letterSpacing: '-0.012em',
            fontWeight: '600',
          },
        ],

        // Normal body
        body: [
          '15px',
          {
            lineHeight: '21px',
            letterSpacing: '-0.008em',
            fontWeight: '400',
          },
        ],

        callout: [
          '15px',
          {
            lineHeight: '20px',
            letterSpacing: '-0.008em',
            fontWeight: '500',
          },
        ],

        subhead: [
          '14px',
          {
            lineHeight: '19px',
            letterSpacing: '-0.006em',
            fontWeight: '400',
          },
        ],

        footnote: [
          '13px',
          {
            lineHeight: '18px',
            fontWeight: '400',
          },
        ],

        caption: [
          '12px',
          {
            lineHeight: '16px',
            fontWeight: '400',
          },
        ],

        caption2: [
          '11px',
          {
            lineHeight: '14px',
            fontWeight: '500',
          },
        ],
      },

      // ==============================================================
      // BORDER RADIUS
      // ==============================================================

      borderRadius: {
        sm: '8px',
        field: '12px',
        card: '16px',
        sheet: '20px',
        modal: '20px',
        pill: '9999px',
      },

      // ==============================================================
      // SHADOWS
      // ==============================================================

      boxShadow: {
        // Default card — very subtle
        card: '0 1px 2px rgba(0, 0, 0, 0.04), 0 4px 16px rgba(0, 0, 0, 0.04)',

        // Elevated card
        elevated:
          '0 2px 6px rgba(0, 0, 0, 0.06), 0 8px 24px rgba(0, 0, 0, 0.06)',

        // Dropdown / popover
        popover:
          '0 8px 32px rgba(0, 0, 0, 0.12), 0 2px 8px rgba(0, 0, 0, 0.06)',

        // Modal
        modal:
          '0 16px 48px rgba(0, 0, 0, 0.16), 0 4px 12px rgba(0, 0, 0, 0.08)',

        // Focus state
        focus: '0 0 0 3px rgba(0, 122, 255, 0.20)',
      },

      // ==============================================================
      // TRANSITIONS
      // ==============================================================

      transitionTimingFunction: {
        ios: 'cubic-bezier(0.32, 0.72, 0, 1)',
        smooth: 'cubic-bezier(0.25, 0.1, 0.25, 1)',
      },

      // ==============================================================
      // ANIMATIONS
      // ==============================================================

      keyframes: {
        fadeIn: {
          from: {
            opacity: '0',
          },
          to: {
            opacity: '1',
          },
        },

        slideUp: {
          from: {
            opacity: '0',
            transform: 'translateY(8px)',
          },
          to: {
            opacity: '1',
            transform: 'translateY(0)',
          },
        },

        scaleIn: {
          from: {
            opacity: '0',
            transform: 'scale(0.98)',
          },
          to: {
            opacity: '1',
            transform: 'scale(1)',
          },
        },
      },

      animation: {
        fadeIn: 'fadeIn 0.2s ease-out',
        slideUp: 'slideUp 0.3s cubic-bezier(0.32, 0.72, 0, 1)',
        scaleIn: 'scaleIn 0.2s ease-out',
      },
    },
  },

  plugins: [],
}