
export function clamp(v, min, max) {
  return Math.max(min, Math.min(max, v));
}

export function fmtRp(n) {
  return 'Rp' + Math.round(n).toLocaleString('id-ID');
}

export function fmtDur(hours) {
  const totalMin = Math.round(hours * 60);
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  if (h && m) return `${h}j ${m}m`;
  if (h) return `${h} jam`;
  return `${m} mnt`;
}
