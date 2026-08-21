// Route, commodity, and scoring data ported verbatim from the Cold Chain
// Router design. Coordinates are [lat, lng] for a Tangerang -> Cimahi corridor.

export const ROUTES_BASE = [
  {
    id: 'A',
    name: 'Rute A — Tol Cipularang',
    color: '#007AFF',
    coords: [
      [-6.1783, 106.6319],
      [-6.2493, 106.9896],
      [-6.3227, 107.3376],
      [-6.4595, 107.4295],
      [-6.5569, 107.4432],
      [-6.73, 107.465],
      [-6.8422, 107.4863],
      [-6.8841, 107.5413],
    ],
    distanceKm: 148,
    durationLikelyMin: 165,
    durationOptimisticMin: 150,
    durationPessimisticMin: 195,
    freshnessBase: 84,
    costRp: 1850000,
    costBreakdown: { bahanBakar: 0.35, tol: 0.25, pendingin: 0.3, lainnya: 0.1 },
    segments: [
      {
        label: 'Tangerang → Karawang Barat',
        coords: [
          [-6.1783, 106.6319],
          [-6.2493, 106.9896],
          [-6.3227, 107.3376],
        ],
        distanceKm: 65,
        avgTempC: 4.5,
        decayPct: 3,
        cumulativePct: 97,
        status: 'green',
      },
      {
        label: 'Karawang Barat → Purwakarta',
        coords: [
          [-6.3227, 107.3376],
          [-6.4595, 107.4295],
          [-6.5569, 107.4432],
        ],
        distanceKm: 35,
        avgTempC: 5,
        decayPct: 4,
        cumulativePct: 93,
        status: 'green',
      },
      {
        label: 'Purwakarta → Padalarang',
        coords: [
          [-6.5569, 107.4432],
          [-6.73, 107.465],
          [-6.8422, 107.4863],
        ],
        distanceKm: 35,
        avgTempC: 7,
        decayPct: 6,
        cumulativePct: 87,
        status: 'yellow',
      },
      {
        label: 'Padalarang → Cimahi',
        coords: [
          [-6.8422, 107.4863],
          [-6.8841, 107.5413],
        ],
        distanceKm: 13,
        avgTempC: 5,
        decayPct: 3,
        cumulativePct: 84,
        status: 'green',
      },
    ],
  },
  {
    id: 'B',
    name: 'Rute B — Puncak–Cianjur',
    color: '#5856D6',
    coords: [
      [-6.1783, 106.6319],
      [-6.4025, 106.8106],
      [-6.7167, 106.9833],
      [-6.8161, 107.1425],
      [-6.8422, 107.4863],
      [-6.8841, 107.5413],
    ],
    distanceKm: 172,
    durationLikelyMin: 230,
    durationOptimisticMin: 205,
    durationPessimisticMin: 275,
    freshnessBase: 69,
    costRp: 1620000,
    costBreakdown: { bahanBakar: 0.38, tol: 0.05, pendingin: 0.37, lainnya: 0.2 },
    segments: [
      {
        label: 'Tangerang → Ciawi',
        coords: [
          [-6.1783, 106.6319],
          [-6.4025, 106.8106],
        ],
        distanceKm: 55,
        avgTempC: 5,
        decayPct: 4,
        cumulativePct: 96,
        status: 'green',
      },
      {
        label: 'Ciawi → Puncak',
        coords: [
          [-6.4025, 106.8106],
          [-6.7167, 106.9833],
        ],
        distanceKm: 25,
        avgTempC: 8,
        decayPct: 8,
        cumulativePct: 88,
        status: 'yellow',
      },
      {
        label: 'Puncak → Cianjur',
        coords: [
          [-6.7167, 106.9833],
          [-6.8161, 107.1425],
        ],
        distanceKm: 45,
        avgTempC: 9,
        decayPct: 10,
        cumulativePct: 78,
        status: 'red',
      },
      {
        label: 'Cianjur → Cimahi',
        coords: [
          [-6.8161, 107.1425],
          [-6.8422, 107.4863],
          [-6.8841, 107.5413],
        ],
        distanceKm: 47,
        avgTempC: 8.5,
        decayPct: 9,
        cumulativePct: 69,
        status: 'red',
      },
    ],
  },
  {
    id: 'C',
    name: 'Rute C — Pantura–Subang',
    color: '#30B0C7',
    coords: [
      [-6.1783, 106.6319],
      [-6.2493, 106.9896],
      [-6.3227, 107.3376],
      [-6.5713, 107.7605],
      [-6.8583, 107.9209],
      [-6.8422, 107.4863],
      [-6.8841, 107.5413],
    ],
    distanceKm: 233,
    durationLikelyMin: 260,
    durationOptimisticMin: 230,
    durationPessimisticMin: 310,
    freshnessBase: 57,
    costRp: 2100000,
    costBreakdown: { bahanBakar: 0.34, tol: 0.18, pendingin: 0.33, lainnya: 0.15 },
    segments: [
      {
        label: 'Tangerang → Karawang Barat',
        coords: [
          [-6.1783, 106.6319],
          [-6.2493, 106.9896],
          [-6.3227, 107.3376],
        ],
        distanceKm: 65,
        avgTempC: 5,
        decayPct: 4,
        cumulativePct: 96,
        status: 'green',
      },
      {
        label: 'Karawang Barat → Subang',
        coords: [
          [-6.3227, 107.3376],
          [-6.5713, 107.7605],
        ],
        distanceKm: 55,
        avgTempC: 9,
        decayPct: 9,
        cumulativePct: 87,
        status: 'yellow',
      },
      {
        label: 'Subang → Sumedang',
        coords: [
          [-6.5713, 107.7605],
          [-6.8583, 107.9209],
        ],
        distanceKm: 40,
        avgTempC: 10,
        decayPct: 12,
        cumulativePct: 75,
        status: 'red',
      },
      {
        label: 'Sumedang → Padalarang',
        coords: [
          [-6.8583, 107.9209],
          [-6.8422, 107.4863],
        ],
        distanceKm: 60,
        avgTempC: 9.5,
        decayPct: 11,
        cumulativePct: 64,
        status: 'red',
      },
      {
        label: 'Padalarang → Cimahi',
        coords: [
          [-6.8422, 107.4863],
          [-6.8841, 107.5413],
        ],
        distanceKm: 13,
        avgTempC: 8,
        decayPct: 7,
        cumulativePct: 57,
        status: 'yellow',
      },
    ],
  },
];

export const COMMODITIES = [
  { id: 'ikan-seafood', label: 'Ikan & Seafood Segar', shelfLifeHours: 8, sensitivity: 1.2, sensitivityLabel: 'Tinggi' },
  { id: 'vaksin-farmasi', label: 'Vaksin & Farmasi', shelfLifeHours: 6, sensitivity: 1.3, sensitivityLabel: 'Sangat Tinggi' },
  { id: 'produk-susu', label: 'Produk Susu', shelfLifeHours: 24, sensitivity: 1.05, sensitivityLabel: 'Sedang' },
  { id: 'sayur-buah', label: 'Sayur & Buah Segar', shelfLifeHours: 36, sensitivity: 1.0, sensitivityLabel: 'Normal' },
  { id: 'daging-beku', label: 'Daging Beku', shelfLifeHours: 72, sensitivity: 0.8, sensitivityLabel: 'Rendah' },
];

export const WEIGHT_PRESETS = {
  'Prioritaskan Kesegaran': { f: 0.6, t: 0.25, c: 0.15 },
  Seimbang: { f: 0.4, t: 0.3, c: 0.3 },
  'Prioritaskan Biaya': { f: 0.3, t: 0.2, c: 0.5 },
};

export const WEIGHT_PRESET_OPTIONS = Object.keys(WEIGHT_PRESETS);

// Warna status memakai system colors iOS (green / orange / red) supaya konsisten
// dengan bahasa visual Apple HIG di seluruh UI.
export const STATUS_META = {
  aman: { label: 'Aman', bg: 'rgba(52,199,89,0.12)', fg: '#1E7B36', dot: '#34C759' },
  waspada: { label: 'Waspada', bg: 'rgba(255,149,0,0.14)', fg: '#9A5B00', dot: '#FF9500' },
  berisiko: { label: 'Berisiko', bg: 'rgba(255,59,48,0.12)', fg: '#B32218', dot: '#FF3B30' },
};

export const COST_LABELS = {
  bahanBakar: 'Bahan Bakar',
  tol: 'Tol',
  pendingin: 'Pendingin (Reefer)',
  lainnya: 'Lainnya',
};

// Segment status colour used by the map heat overlay
export const SEGMENT_STATUS_COLOR = { green: '#34C759', yellow: '#FF9500', red: '#FF3B30' };
