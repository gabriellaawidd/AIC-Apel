// Pure scoring + narration logic ported from the design's DCLogic component.
// Kept framework-agnostic so it can be unit-reasoned and driven from a hook.

import { ROUTES_BASE, COMMODITIES, WEIGHT_PRESETS, STATUS_META } from './data.js';

export function clamp(v, min, max) {
  return Math.max(min, Math.min(max, v));
}

export function fmtRp(n) {
  return 'Rp' + Math.round(n).toLocaleString('id-ID');
}

// Format a duration in minutes as "2j 45m" / "3 jam" / "28 mnt".
export function fmtDur(min) {
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  if (h && m) return `${h}j ${m}m`;
  if (h) return `${h} jam`;
  return `${m} mnt`;
}

export function statusFor(pct) {
  if (pct >= 80) return STATUS_META.aman;
  if (pct >= 70) return STATUS_META.waspada;
  return STATUS_META.berisiko;
}

// Score every route against the current commodity, weight preset, and threshold.
export function computeScored({ commodityId, weightPreset, threshold }) {
  const commodity = COMMODITIES.find((c) => c.id === commodityId) || COMMODITIES[3];
  const preset = WEIGHT_PRESETS[weightPreset] || WEIGHT_PRESETS['Seimbang'];

  const withFreshness = ROUTES_BASE.map((r) => ({
    ...r,
    freshnessPct: clamp(Math.round(r.freshnessBase - (commodity.sensitivity - 1) * 40), 0, 100),
  }));

  const minCost = Math.min(...withFreshness.map((r) => r.costRp));
  const maxCost = Math.max(...withFreshness.map((r) => r.costRp));
  const minDur = Math.min(...withFreshness.map((r) => r.durationLikelyMin));
  const maxDur = Math.max(...withFreshness.map((r) => r.durationLikelyMin));

  const scored = withFreshness.map((r) => {
    const timeScore =
      maxDur === minDur ? 100 : Math.round((100 * (maxDur - r.durationLikelyMin)) / (maxDur - minDur));
    const costScore =
      maxCost === minCost ? 100 : Math.round((100 * (maxCost - r.costRp)) / (maxCost - minCost));
    const freshnessScore = r.freshnessPct;
    const totalScore = Math.round(preset.f * freshnessScore + preset.t * timeScore + preset.c * costScore);
    const meetsThreshold = r.freshnessPct >= threshold;
    return { ...r, timeScore, costScore, freshnessScore, totalScore, meetsThreshold, status: statusFor(r.freshnessPct) };
  });

  const qualifying = scored.filter((r) => r.meetsThreshold);
  const pool = qualifying.length ? qualifying : scored;
  const bestId = pool.reduce((best, r) => (r.totalScore > best.totalScore ? r : best), pool[0]).id;

  return { scored, bestId, fallback: qualifying.length === 0, commodity, preset };
}

// Human-readable "why this route" narration (the RAG output block).
export function buildReasoning({ scored, bestId, fallback, commodity, threshold }) {
  const best = scored.find((r) => r.id === bestId);
  const others = scored.filter((r) => r.id !== bestId).sort((a, b) => b.totalScore - a.totalScore);
  const lines = [];

  if (fallback) {
    lines.push(
      `Tidak ada rute yang memenuhi ambang kesegaran minimum ${threshold}% untuk komoditas ${commodity.label}. ${best.name} dipilih sebagai opsi risiko terendah dengan kesegaran ${best.freshnessPct}%.`
    );
  } else {
    lines.push(
      `${best.name} dipilih sebagai rute terbaik dengan skor gabungan ${best.totalScore}/100 — kesegaran ${best.freshnessPct}% (di atas ambang ${threshold}%), waktu tempuh ${Math.round(best.durationLikelyMin / 6) / 10} jam, dan biaya ${fmtRp(best.costRp)}.`
    );
  }

  const closest = others[0];
  if (closest) {
    const diff = best.totalScore - closest.totalScore;
    const reason =
      best.freshnessPct > closest.freshnessPct
        ? 'kesegaran kargo lebih terjaga'
        : best.costRp < closest.costRp
        ? 'biaya lebih rendah'
        : 'waktu tempuh lebih singkat';
    lines.push(`Dibandingkan ${closest.name} (skor ${closest.totalScore}), selisihnya ${diff} poin — terutama karena ${reason}.`);
  }

  const worstSeg = best.segments.slice().sort((a, b) => b.decayPct - a.decayPct)[0];
  lines.push(
    `Titik risiko tertinggi pada rute ini ada di segmen ${worstSeg.label} (suhu rata-rata ${worstSeg.avgTempC}°C, penurunan kesegaran ${worstSeg.decayPct}%).`
  );
  return lines;
}

// Actionable handling advice (the "Saran" block).
export function buildSaran({ scored, bestId, commodity, departTime }) {
  const best = scored.find((r) => r.id === bestId);
  const saran = [];

  const midSeg = best.segments[Math.floor(best.segments.length / 2)];
  saran.push(`Berangkat pukul ${departTime} atau lebih awal untuk menghindari kepadatan di segmen ${midSeg.label}.`);
  saran.push(
    `Untuk komoditas ${commodity.label} (shelf-life ${commodity.shelfLifeHours} jam), periksa suhu reefer setiap ${Math.max(1, Math.floor(commodity.shelfLifeHours / 4))} jam selama perjalanan.`
  );

  const risky = best.segments.filter((s) => s.status !== 'green');
  if (risky.length) {
    saran.push(
      `Waspadai ${risky.length} segmen berisiko (${risky.map((s) => s.label).join(', ')}) — pertimbangkan isi ulang nitrogen cair atau es kering di rest area terdekat.`
    );
  } else {
    saran.push('Seluruh segmen rute ini berstatus aman — tidak diperlukan tindakan tambahan.');
  }

  const cheapest = scored.slice().sort((a, b) => a.costRp - b.costRp)[0];
  if (cheapest.id !== bestId) {
    saran.push(
      `Jika biaya menjadi prioritas utama, ${cheapest.name} lebih hemat ${fmtRp(best.costRp - cheapest.costRp)}, namun kesegaran turun ke sekitar ${cheapest.freshnessPct}%.`
    );
  }
  return saran;
}
