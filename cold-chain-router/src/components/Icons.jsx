// Ikon bergaya SF Symbols: stroke tunggal, ujung membulat, berat 1.75.
// Semua ikon mewarisi `currentColor` dan ukurannya diatur lewat prop `size`.

function Svg({ size = 18, children, ...rest }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {children}
    </svg>
  );
}

export const ArrowRight = (p) => (
  <Svg {...p}>
    <path d="M4 12h15" />
    <path d="M13 6l6 6-6 6" />
  </Svg>
);

export const MapPin = (p) => (
  <Svg {...p}>
    <path d="M12 21s7-5.4 7-11a7 7 0 1 0-14 0c0 5.6 7 11 7 11Z" />
    <circle cx="12" cy="10" r="2.5" />
  </Svg>
);

export const Clock = (p) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7.5V12l3 1.8" />
  </Svg>
);

export const Basket = (p) => (
  <Svg {...p}>
    <path d="M4 9.5h16l-1.4 8a2 2 0 0 1-2 1.7H7.4a2 2 0 0 1-2-1.7L4 9.5Z" />
    <path d="M8.5 9.5 11 4.5M15.5 9.5 13 4.5" />
  </Svg>
);

export const ChevronRight = (p) => (
  <Svg {...p}>
    <path d="M9.5 5.5 16 12l-6.5 6.5" />
  </Svg>
);

export const ChevronDown = (p) => (
  <Svg {...p}>
    <path d="M5.5 9.5 12 16l6.5-6.5" />
  </Svg>
);

export const ChartBar = (p) => (
  <Svg {...p}>
    <path d="M5 19V11M12 19V5M19 19v-5" />
  </Svg>
);

export const Sparkles = (p) => (
  <Svg {...p}>
    <path d="M11 4.5 12.6 9l4.4 1.6-4.4 1.6L11 16.7 9.4 12.2 5 10.6 9.4 9 11 4.5Z" />
    <path d="M18 4v3.2M19.6 5.6h-3.2M18.6 15.5v2.4M19.8 16.7h-2.4" />
  </Svg>
);

export const Thermometer = (p) => (
  <Svg {...p}>
    <path d="M14 14.8V5.5a2 2 0 1 0-4 0v9.3a4 4 0 1 0 4 0Z" />
    <path d="M12 9v6.6" />
  </Svg>
);

export const Timer = (p) => (
  <Svg {...p}>
    <circle cx="12" cy="13.5" r="7" />
    <path d="M12 10v3.5l2.4 1.4M9.5 3.5h5" />
  </Svg>
);

export const Wallet = (p) => (
  <Svg {...p}>
    <path d="M4.5 9.5a2 2 0 0 1 2-2h9.5a2 2 0 0 1 2 2v0" />
    <path d="M4.5 9.5v7.5a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-4.5a2 2 0 0 0-2-2h-13" />
    <path d="M15.8 14.2h.6" />
  </Svg>
);

export const Scale = (p) => (
  <Svg {...p}>
    <path d="M12 4.5v15M6.5 19.5h11" />
    <path d="M4 10.5h6l-3-5-3 5ZM14 10.5h6l-3-5-3 5Z" />
  </Svg>
);

export const Brain = (p) => (
  <Svg {...p}>
    <path d="M9.5 5a2.5 2.5 0 0 0-2.4 3.2A2.5 2.5 0 0 0 5.5 12a2.5 2.5 0 0 0 1.6 2.7A2.5 2.5 0 0 0 12 17V6.4A2 2 0 0 0 9.5 5Z" />
    <path d="M14.5 5A2.5 2.5 0 0 1 17 8.2 2.5 2.5 0 0 1 18.5 12a2.5 2.5 0 0 1-1.6 2.7A2.5 2.5 0 0 1 12 17" />
  </Svg>
);

export const Xmark = (p) => (
  <Svg {...p}>
    <path d="M6.8 6.8 17.2 17.2M17.2 6.8 6.8 17.2" />
  </Svg>
);

export const Info = (p) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 11v5.5M12 7.8v.6" />
  </Svg>
);

export const CheckSeal = (p) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="m8.5 12.2 2.4 2.4 4.6-4.9" />
  </Svg>
);
