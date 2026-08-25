
import { STATUS_META } from './data.js';

export const ROUTE_COLORS = ['#2a78d6', '#7c3aed', '#0d9488', '#ea580c', '#0891b2'];

export function statusFor(key) {
  return STATUS_META[key] || STATUS_META.aman;
}

function fanOutCoords(origin, destination, index, total) {
  const lat1 = origin.lat;
  const lon1 = origin.lon;
  const lat2 = destination.lat;
  const lon2 = destination.lon;
  if (total <= 1) return [[lat1, lon1], [lat2, lon2]];

  const dx = lon2 - lon1;
  const dy = lat2 - lat1;
  const norm = Math.hypot(dx, dy) || 1;
  const perpLat = dx / norm;
  const perpLon = -dy / norm;
  const spread = 0.06;
  const offset = (index - (total - 1) / 2) * spread;

  const midLat = (lat1 + lat2) / 2 + perpLat * offset;
  const midLon = (lon1 + lon2) / 2 + perpLon * offset;

  return [
    [lat1, lon1],
    [midLat, midLon],
    [lat2, lon2],
  ];
}

function sliceByStatus(coords, segments) {
  if (!coords || coords.length < 2) return [];
  if (!segments || !segments.length) return [];

  const totalH = segments[segments.length - 1].to_h || 1;
  const n = coords.length;
  const out = [];
  segments.forEach((seg) => {
    const from = Math.floor(((seg.from_h || 0) / totalH) * (n - 1));
    const to = Math.ceil(((seg.to_h || 0) / totalH) * (n - 1));
    const part = coords.slice(Math.max(0, from), Math.min(n, to + 1));
    if (part.length >= 2) {
      out.push({
        coords: part,
        status: statusFor(seg.status),
        statusKey: seg.status,
        tempC: seg.temp_c,
        fromH: seg.from_h,
        toH: seg.to_h,
        pctFresh: seg.pct_fresh_end,
      });
    }
  });
  return out;
}

export function toDisplayRoutes(payload) {
  if (!payload?.options?.length) return [];
  const origin = payload.request_echo?.origin;
  const destination = payload.request_echo?.destination;
  const total = payload.options.length;

  return payload.options.map((o, i) => {
    const freshnessPct = Math.round(o.quality.pct_fresh_on_arrival);
    const hasGeometry = Array.isArray(o.geometry) && o.geometry.length >= 2;
    const coords = hasGeometry
      ? o.geometry.map(([lon, lat]) => [lat, lon])
      : origin && destination
      ? fanOutCoords(origin, destination, i, total)
      : [];

    const segments = o.quality.segments || [];

    return {
      id: o.route_id,
      name: o.name,
      summary: o.summary || '',
      color: ROUTE_COLORS[i % ROUTE_COLORS.length],
      coords,
      statusSlices: hasGeometry ? sliceByStatus(coords, segments) : [],
      approxGeometry: !hasGeometry,
      distanceKm: o.distance_km,
      usesToll: o.uses_toll,
      tollKm: o.toll_km ?? 0,
      nonTollKm: o.non_toll_km ?? 0,
      tollRoadNames: o.toll_road_names || [],
      tollSegments: o.toll_segments || [],
      avgSpeedKmh: o.avg_speed_kmh ?? 0,
      etaOptimisticH: o.eta_hours.optimistic,
      etaLikelyH: o.eta_hours.likely,
      etaPessimisticH: o.eta_hours.pessimistic,
      costTollRp: o.cost_rp.toll,
      costFuelRp: o.cost_rp.fuel,
      costRp: o.cost_rp.total,
      tollBreakdown: o.cost_rp.toll_breakdown || [],
      fuelLiters: o.cost_rp.fuel_liters ?? null,
      costBasis: o.cost_rp.basis || '',
      freshnessPct,
      remainingShelfLifeH: o.quality.remaining_shelf_life_h_after_arrival,
      spoilRisk: o.quality.spoil_risk,
      isSellable: o.quality.is_sellable,
      basisHuman: o.quality.basis_human || '',
      basisTechnical: o.quality.basis || '',
      statusThresholds: o.quality.status_thresholds || {},
      tempSegments: segments,
      score: o.score,
      isBest: o.is_best,
      isPareto: o.is_pareto_optimal,
      dominatedByRouteId: o.dominated_by_route_id,
      dominatedReason: o.dominated_reason,
      meetsDeadline: o.meets_deadline,
      shelfLifeDeadlineH: o.shelf_life_deadline_h_since_departure,
      assumptions: o.assumptions || {},
      status: statusFor(o.quality.status),
      statusKey: o.quality.status,
    };
  });
}
