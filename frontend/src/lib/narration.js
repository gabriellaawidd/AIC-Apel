
import { fmtRp, fmtDur } from './scoring.js';

function score100(o) {
  return o?.score == null ? 0 : Math.round((1 - o.score) * 100);
}

export function buildFallbackInsight(payload, routeId) {
  if (!payload?.options?.length) return null;
  const best = payload.options.find((o) => o.is_best) || payload.options[0];
  const subject = payload.options.find((o) => o.route_id === routeId) || best;
  const isBest = subject.route_id === best.route_id;
  const others = payload.options.filter((o) => o.route_id !== subject.route_id);
  const rival = isBest
    ? others.length
      ? others.reduce((a, b) => (a.score <= b.score ? a : b))
      : null
    : best;
  const cheapest = payload.options.reduce((a, b) =>
    a.cost_rp.total <= b.cost_rp.total ? a : b
  );
  const segs = subject.quality.segments || [];
  const worst = segs.length
    ? segs.reduce((a, b) => ((a.pct_drop || 0) >= (b.pct_drop || 0) ? a : b))
    : null;

  const angka =
    `kesegaran ${Math.round(subject.quality.pct_fresh_on_arrival)}%, waktu tempuh ` +
    `${fmtDur(subject.eta_hours.likely)}, biaya ${fmtRp(subject.cost_rp.total)}.`;

  const explanation = [
    isBest
      ? {
          label: 'Rute terpilih',
          text: `${subject.name} dipilih sebagai rute terbaik dengan skor gabungan ${score100(
            subject
          )}/100 — ${angka}`,
        }
      : {
          label: 'Rute yang sedang dilihat',
          text: `${subject.name} — skor gabungan ${score100(subject)}/100, ${angka} Ini bukan rekomendasi utama untuk prioritas yang sedang aktif.`,
        },
  ];
  if (rival) {
    explanation.push({
      label: 'Pembanding',
      text: `Dibandingkan ${rival.name} (skor ${score100(rival)}), selisihnya ${Math.abs(
        score100(subject) - score100(rival)
      )} poin.`,
    });
  }
  if (worst) {
    explanation.push({
      label: 'Titik risiko',
      text:
        `Penurunan kesegaran terbesar pada jam ke-${Math.round(worst.from_h)}–${Math.round(
          worst.to_h
        )} (suhu ${Math.round(worst.temp_c)}°C, turun ${worst.pct_drop} poin).`,
    });
  }

  const recommendations = [];
  const risky = segs.filter((s) => s.status !== 'aman');
  if (risky.length) {
    recommendations.push(
      `Pantau suhu kargo pada ${risky.length} jam perjalanan berstatus waspada/berisiko, mulai jam ke-${Math.round(
        risky[0].from_h
      )}.`
    );
  } else {
    recommendations.push('Seluruh jam perjalanan berstatus aman — ikuti prosedur pemeriksaan standar.');
  }
  if (!subject.quality.is_sellable) {
    recommendations.push(
      'Kesegaran saat tiba di bawah ambang layak jual — pertimbangkan truk berpendingin atau kargo yang lebih segar saat muat.'
    );
  }
  if (!isBest) {
    const dBiaya = subject.cost_rp.total - best.cost_rp.total;
    const dMenit = Math.abs((subject.eta_hours.likely - best.eta_hours.likely) * 60);
    recommendations.push(
      dBiaya < 0
        ? `Memilih rute ini menghemat ${fmtRp(-dBiaya)} dibanding rute terbaik, dengan tambahan waktu sekitar ${Math.round(
            dMenit
          )} menit.`
        : `Rute ini ${fmtRp(dBiaya)} lebih mahal dibanding rute terbaik — pakai hanya bila rute utama terganggu.`
    );
  } else if (cheapest.route_id !== subject.route_id) {
    recommendations.push(
      `Jika biaya jadi prioritas, ${cheapest.name} lebih hemat ${fmtRp(
        subject.cost_rp.total - cheapest.cost_rp.total
      )}, namun kesegaran turun ke ${Math.round(cheapest.quality.pct_fresh_on_arrival)}%.`
    );
  }

  return {
    route_id: subject.route_id,
    route_name: subject.name,
    is_best: isBest,
    explanation,
    recommendations,
  };
}

export function buildFallbackExplanations(payload) {
  if (!payload?.options?.length) return [];
  return payload.options.map((o) => ({
    route_id: o.route_id,
    name: o.name,
    headline: o.summary || '',
    reasoning: [
      {
        aspect: 'Waktu tempuh',
        text:
          `${fmtDur(o.eta_hours.likely)} untuk ${o.distance_km} km (sekitar ${o.avg_speed_kmh} km/jam), ` +
          `rentang ${fmtDur(o.eta_hours.optimistic)}–${fmtDur(o.eta_hours.pessimistic)}.`,
      },
      {
        aspect: 'Kesegaran kargo',
        text:
          `Saat tiba ${o.quality.pct_fresh_on_arrival.toFixed(1)}% — status ` +
          `${(o.quality.status || '').toUpperCase()}, sisa umur simpan ` +
          `${o.quality.remaining_shelf_life_h_after_arrival.toFixed(1)} jam. ` +
          (o.quality.basis_human || ''),
      },
      {
        aspect: 'Biaya',
        text:
          `Total ${fmtRp(o.cost_rp.total)} — BBM ${fmtRp(o.cost_rp.fuel)}` +
          (o.cost_rp.toll
            ? ` dan tol ${fmtRp(o.cost_rp.toll)} untuk ${o.cost_rp.toll_breakdown?.length || 0} ruas.`
            : ', tanpa biaya tol.'),
      },
      {
        aspect: 'Posisi dalam peringkat',
        text: o.is_best
          ? `Terpilih sebagai rute terbaik (skor gabungan ${score100(o)}/100).`
          : o.is_pareto_optimal
          ? `Pareto-optimal, tetapi kalah skor (${score100(o)}/100) pada prioritas saat ini.`
          : `Didominasi rute lain — ${o.dominated_reason || 'kalah di semua kriteria'}.`,
      },
    ],
    when_to_pick: '',
    advisory: [],
  }));
}
