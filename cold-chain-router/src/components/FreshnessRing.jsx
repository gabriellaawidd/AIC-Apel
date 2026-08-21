// Cincin progres kesegaran. Warna mengikuti status (aman / waspada / berisiko)
// sehingga informasi tidak disampaikan lewat warna saja — angka persennya
// selalu tampil bersebelahan (HIG: jangan andalkan warna sebagai satu-satunya isyarat).
export default function FreshnessRing({ pct, color, size = 34, stroke = 3.5 }) {
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const filled = Math.max(0, Math.min(100, pct)) / 100;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke="rgba(118,118,128,0.14)"
        strokeWidth={stroke}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={`${circumference * filled} ${circumference}`}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: 'stroke-dasharray 0.45s cubic-bezier(0.32,0.72,0,1)' }}
      />
    </svg>
  );
}
