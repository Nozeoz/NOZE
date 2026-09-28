// Builds the Kingsbloom placeholder kit outputs from kit.mjs:
//   svg/<id>.svg   one file per asset, for the prototypes
//   gallery.html   the Asset Atlas page (self-contained; open it in any browser)
// Usage: node art/placeholder/build.mjs [--fragment <file>]
//   --fragment also writes the page without the <html>/<head>/<body> shell, for publishing as an Artifact.
import { ASSETS } from './kit.mjs';
import { mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const T = 128; // kit units per tile: authored at 2×, 1 tile = 64 px at 1080p
const r1 = n => Math.round(n * 10) / 10;
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const b64 = s => Buffer.from(s).toString('base64');
const rng = seed => () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646;

const byId = {};
for (const a of ASSETS) {
  const m = a.svg.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/);
  a.w = +m[1];
  a.h = +m[2];
  byId[a.id] = a;
}
const of = cat => ASSETS.filter(a => a.cat === cat);

// ---------- 1. SVG files ----------
const svgDir = join(HERE, 'svg');
mkdirSync(svgDir, { recursive: true });
for (const f of readdirSync(svgDir)) if (f.endsWith('.svg')) rmSync(join(svgDir, f));
for (const a of ASSETS) writeFileSync(join(svgDir, `${a.id}.svg`), a.svg + '\n');

// ---------- 2. Shared helpers ----------
const sprite = `<svg class="sprite" aria-hidden="true" focusable="false" width="0" height="0"><defs>${ASSETS.map(a =>
  `<image id="i-${a.id}" width="${a.w}" height="${a.h}" href="data:image/svg+xml;base64,${b64(a.svg)}"/>`).join('')}</defs></svg>`;

const art = (a, scale = 1, label = a.label) =>
  `<svg viewBox="0 0 ${a.w} ${a.h}" width="${r1(a.w * scale)}" height="${r1(a.h * scale)}" role="img" aria-label="${esc(label)}"><use href="#i-${a.id}"/></svg>`;
const icon = (id, cls = 'el') => `<svg class="${cls}" viewBox="0 0 ${byId[id].w} ${byId[id].h}" aria-hidden="true"><use href="#i-${id}"/></svg>`;

const MS = { VS: ['vs', 'Needed for the Vertical Slice'], EA: ['ea', 'Needed for Early Access'], '1.0': ['v1', 'Needed for 1.0'] };
const chip = ms => `<span class="chip ${MS[ms][0]}" title="${MS[ms][1]}">${ms}</span>`;

const SHAPES = { terra: 'Square', aqua: 'Circle', ignis: 'Triangle', zephyr: 'Diamond', lumen: 'Star', umbra: 'Crescent', veil: 'Crossed circle' };
const SIZE = a => {
  switch (a.cat) {
    case 'character': return a.id === 'chr_flicker' ? 'In game ≈ 32 px, floating' : 'In game ≈ 64 × 128 px, 2 tiles tall';
    case 'creature': return a.id === 'amb_wispling' ? 'Ambient life, no Pact' : 'Size S · ≈ 48–80 px on screen';
    case 'terrain': return '64 × 64 px tile';
    case 'crop': return { crop_dawnbell: '1 tile · grows in 7 days', crop_mandrake: '1 tile · grows in 8 days' }[a.id] || '1 tile · 64 × 64 px';
    case 'icon': return '64 × 64 px · authored at 128';
    case 'element': return `Shape: ${SHAPES[a.id.replace('ico_el_', '')]}`;
    case 'building': return {
      bld_throne_t0: 'Footprint 3 × 3 tiles', bld_tent: 'Footprint 2 × 2 tiles · 1 bed', bld_hut: 'Footprint 3 × 3 tiles · 2 beds',
      bld_longhouse: 'Footprint 6 × 5 tiles', bld_beacon_t2: 'Footprint 3 × 3 tiles',
    }[a.id];
    case 'prop': return {
      prp_tree_sapling: 'Planted sapling', prp_tree_young: 'Half-grown', prp_tree_round: 'Fully grown · trees are 128–320 px tall',
      prp_pine: 'Trees are 128–320 px tall', prp_mushroom_giant: 'Trees are 128–320 px tall', prp_brazier: 'Footprint 3 × 3 tiles',
      prp_lumen_lamp: 'Light radius 3 tiles; does not extend the Realm',
    }[a.id] || 'Prop · 32–128 px';
    default: return '';
  }
};

function card(a, { scale = 1, ground = 'grass', center = false, lead = '' } = {}) {
  return `<figure class="spec"><div class="stage g-${ground}${center ? ' center' : ''}">${art(a, scale)}</div>` +
    `<figcaption><div class="name"><span>${lead}${esc(a.label)}</span>${chip(a.ms)}</div><code>${a.id}</code>` +
    (a.note ? `<p class="note">${esc(a.note)}</p>` : '') + `<p class="size">${SIZE(a)}</p></figcaption></figure>`;
}

// Scene placement: (fx, fy) is the foot point in tiles, w the on-screen width in tiles.
const put = (id, fx, fy, w, lift = 0, attrs = '') => {
  const a = byId[id], s = (w * T) / a.w;
  return { z: fy + lift, m: `<use href="#i-${id}" transform="translate(${r1(fx * T - (w * T) / 2)} ${r1(fy * T - a.h * s)}) scale(${+s.toFixed(4)})"${attrs}/>` };
};
const layer = items => [...items].sort((p, q) => p.z - q.z).map(i => i.m).join('');
const pat = (id, tile, scale = 1) =>
  `<pattern id="${id}" patternUnits="userSpaceOnUse" width="${T}" height="${T}"${scale !== 1 ? ` patternTransform="scale(${scale})"` : ''}><use href="#i-${tile}"/></pattern>`;
// Smooth curve through points given in tiles (Catmull-Rom as cubic Béziers).
const smooth = pts => {
  const p = pts.map(([x, y]) => [x * T, y * T]);
  let d = `M${r1(p[0][0])} ${r1(p[0][1])}`;
  for (let i = 0; i < p.length - 1; i++) {
    const a = p[i - 1] || p[i], b = p[i], c = p[i + 1], e = p[i + 2] || c;
    d += ` C${r1(b[0] + (c[0] - a[0]) / 6)} ${r1(b[1] + (c[1] - a[1]) / 6)} ${r1(c[0] - (e[0] - b[0]) / 6)} ${r1(c[1] - (e[1] - b[1]) / 6)} ${r1(c[0])} ${r1(c[1])}`;
  }
  return d;
};
const band = (leftPts, rightPts) => `${smooth(leftPts)} ${smooth([...rightPts].reverse()).replace(/^M/, 'L')} Z`;
const trail = (d, wide = 1.25) =>
  `<path d="${d}" fill="none" stroke="#C4AE82" stroke-opacity=".55" stroke-width="${(wide + 0.22) * T}" stroke-linecap="round" stroke-linejoin="round"/>` +
  `<path d="${d}" fill="none" stroke="url(#PATH)" stroke-width="${wide * T}" stroke-linecap="round" stroke-linejoin="round"/>`;
const decals = (rand, n, W, H) => Array.from({ length: n }, () => {
  const x = rand() * W * T, y = rand() * H * T, k = rand();
  if (k < 0.62) return `<g fill="#B6CE6F"><circle cx="${r1(x)}" cy="${r1(y)}" r="9"/><circle cx="${r1(x + 11)}" cy="${r1(y + 3)}" r="8"/><circle cx="${r1(x + 4)}" cy="${r1(y - 8)}" r="8"/></g>`;
  return `<circle cx="${r1(x)}" cy="${r1(y)}" r="4.5" fill="${k < 0.82 ? '#FFFDF6' : '#F3E27A'}" stroke="#98A067" stroke-width="1.5"/>`;
}).join('');

// ---------- 3. The hero scene: the Exile's Camp, Spring 5 ----------
function heroScene() {
  const W = 24, H = 11, rand = rng(4242);
  const bankL = [[19.4, -0.6], [18.8, 2.4], [19.7, 5.0], [19.2, 7.6], [20.0, 11.6]];
  const bankR = bankL.map(([x, y], i) => [x + [2.9, 3.0, 2.8, 3.1, 2.9][i], y]);
  const shift = (pts, dx) => pts.map(([x, y]) => [x + dx, y]);
  const veilEdge = [[1.7, -0.6], [2.5, 2.2], [1.8, 4.6], [2.9, 7.0], [2.1, 9.4], [2.6, 11.6]];
  const objects = [
    put('prp_pine', 1.2, 2.3, 1.8), put('prp_tree_round', 3.3, 2.0, 2.6), put('prp_pine', 5.5, 1.4, 1.7),
    put('prp_tree_round', 7.5, 1.7, 2.4), put('prp_pine', 9.5, 1.2, 1.6), put('prp_tree_young', 10.9, 2.3, 1.4),
    put('prp_pine', 15.6, 1.3, 1.7), put('prp_tree_round', 17.2, 2.2, 2.5), put('prp_pine', 18.2, 1.1, 1.4),
    put('prp_pine', 23.4, 3.4, 1.6), put('prp_fern', 23.0, 6.1, 0.9), put('prp_tree_round', 23.6, 9.2, 2.2),
    put('bld_throne_t0', 12.0, 4.7, 3.0), put('prp_brazier', 14.9, 5.3, 1.5), put('bld_tent', 8.3, 5.1, 2.0),
    put('prp_lumen_lamp', 10.6, 6.4, 0.7), put('prp_stump', 10.0, 9.9, 0.9),
    put('prp_rock', 16.8, 4.4, 0.9), put('prp_rock', 2.0, 10.2, 1.0), put('prp_fern', 1.1, 5.2, 1.0), put('prp_fern', 6.3, 10.7, 0.9),
    put('prp_berry_bush', 16.0, 9.3, 1.3), put('prp_tree_sapling', 14.3, 10.0, 0.7), put('prp_tree_young', 18.0, 10.9, 1.3),
    put('prp_lily_lotus', 21.0, 3.6, 1.0), put('prp_lily_lotus', 21.1, 9.2, 0.9),
    put('prp_veil_crystal', 0.9, 7.2, 1.2), put('prp_veil_crystal', 2.3, 3.6, 0.8),
    put('crop_turnip_1', 3.5, 6.93, 0.92), put('crop_turnip_2', 4.5, 6.93, 0.92), put('crop_turnip_3', 5.5, 6.93, 0.92), put('crop_turnip_4', 6.5, 6.93, 0.92),
    put('crop_turnip_5', 3.5, 7.93, 0.92), put('crop_turnip_5', 4.5, 7.93, 0.92), put('crop_dawnbell', 5.5, 7.93, 0.92), put('crop_mandrake', 6.5, 7.93, 0.92),
    put('chr_sovereign', 8.9, 8.5, 1.28), put('chr_flicker', 9.9, 7.0, 0.5, 2), put('chr_bram', 13.4, 7.6, 1.28),
    put('cre_puddlepup', 7.6, 7.4, 0.95), put('cre_mossbun', 5.4, 9.3, 0.85), put('cre_emberkit', 16.4, 6.2, 0.85), put('cre_jellop', 18.2, 8.4, 0.95),
    put('amb_wispling', 13.6, 3.4, 0.5, 2), put('amb_wispling', 10.4, 3.8, 0.45, 2), put('amb_wispling', 15.9, 7.9, 0.45, 2),
  ];
  return `<svg class="scene-svg" viewBox="0 0 ${W * T} ${H * T}" role="img" aria-label="The Exile's Camp: the Ashen Throne, a brazier, a tent, a turnip plot, the Sovereign, Flicker, Bram, creatures, a river, and the Veil at the west edge"><defs>` +
    pat('h-grass', 'tile_grass') + pat('h-water', 'tile_water') + pat('h-veil', 'tile_veil') + pat('h-tilled', 'tile_tilled') + pat('h-watered', 'tile_watered') +
    pat('h-path', 'tile_path') + `</defs><g id="hero-world">` +
    `<rect width="${W * T}" height="${H * T}" fill="url(#h-grass)"/>` + decals(rand, 70, W, H) +
    `<path d="${smooth(veilEdge)} L-64 ${H * T + 64} L-64 -64 Z" fill="url(#h-veil)"/>` +
    trail(smooth([[11.0, 11.7], [11.2, 9.6], [11.7, 7.6], [12.0, 5.4]])).replace(/#PATH/g, '#h-path') +
    trail(smooth([[11.6, 7.3], [10.4, 6.3], [8.9, 5.5]]), 1.0).replace(/#PATH/g, '#h-path') +
    trail(smooth([[11.3, 8.9], [9.7, 9.1], [7.6, 8.6]]), 1.0).replace(/#PATH/g, '#h-path') +
    `<rect x="${3 * T}" y="${6 * T}" width="${2 * T}" height="${2 * T}" fill="url(#h-tilled)"/><rect x="${5 * T}" y="${6 * T}" width="${2 * T}" height="${2 * T}" fill="url(#h-watered)"/>` +
    `<rect x="${3 * T}" y="${6 * T}" width="${4 * T}" height="${2 * T}" rx="10" fill="none" stroke="#6E4C37" stroke-width="6"/>` +
    `<path d="${band(bankL, bankR)}" fill="url(#h-water)"/>` +
    [bankL, bankR].map(b => `<path d="${smooth(b)}" fill="none" stroke="#3C6D62" stroke-width="12" stroke-linecap="round"/>`).join('') +
    `<path d="${smooth(shift(bankL, 0.14))}" fill="none" stroke="#D9EAE7" stroke-width="6" stroke-linecap="round" opacity=".9"/>` +
    `<path d="${smooth(shift(bankR, -0.14))}" fill="none" stroke="#D9EAE7" stroke-width="6" stroke-linecap="round" opacity=".9"/>` +
    `<ellipse cx="${9.9 * T}" cy="${8.45 * T}" rx="18" ry="6" fill="#2E3327" opacity=".18"/>` +
    layer(objects) + `</g></svg>`;
}

// ---------- 4. The Veil & Beacon demo map (64 × 34 tiles around the Beacon) ----------
function veilMap() {
  const W = 64, H = 34, C = [32, 17], rand = rng(9001);
  const riverX = y => 48.6 + 1.6 * Math.sin(y / 5.2) + 0.5 * Math.sin(y / 1.9);
  const bankL = Array.from({ length: 11 }, (_, i) => [riverX(i * 3.6 - 1), i * 3.6 - 1]);
  const bankR = bankL.map(([x, y]) => [x + 3.1, y]);
  const trails = [
    [[32.3, 18.6], [31.6, 23], [33.0, 28], [32.2, 35.5]],
    [[34.8, 17.8], [39, 18.5], [44, 17.3], [48.4, 17.9]],
    [[24.0, 17.8], [19, 16.5], [12, 17.7], [4, 16.3], [-1.5, 17.1]],
  ];
  const nearTrail = (x, y) => trails.some(tr => tr.some((p, i) => {
    const q = tr[i + 1];
    if (!q) return false;
    const dx = q[0] - p[0], dy = q[1] - p[1];
    const t = Math.max(0, Math.min(1, ((x - p[0]) * dx + (y - p[1]) * dy) / (dx * dx + dy * dy)));
    return Math.hypot(x - p[0] - t * dx, y - p[1] - t * dy) < 1.4;
  }));
  const inRiver = (x, y) => x > riverX(y) - 1.4 && x < riverX(y) + 4.5;
  const dist = (x, y) => Math.hypot(x - C[0], y - C[1]);
  const taken = [];
  const free = (x, y, d) => taken.every(([a, b]) => (a - x) ** 2 + (b - y) ** 2 > d * d);
  const kinds = [['prp_pine', 30, 1.7, 2.2], ['prp_tree_round', 26, 2.2, 2.9], ['prp_tree_young', 9, 1.3, 1.6], ['prp_rock', 10, 0.8, 1.2],
    ['prp_fern', 10, 0.8, 1.1], ['prp_berry_bush', 8, 1.1, 1.4], ['prp_stump', 4, 0.8, 1.0], ['prp_tree_sapling', 3, 0.6, 0.8]];
  const total = kinds.reduce((s, k) => s + k[1], 0);
  const pick = () => { let t = rand() * total; for (const k of kinds) if ((t -= k[1]) < 0) return k; return kinds[0]; };

  const camp = [
    put('bld_longhouse', 26.8, 16.6, 5.2), put('bld_hut', 37.4, 16.2, 2.6), put('bld_tent', 36.5, 20.6, 2.0), put('bld_tent', 26.9, 21.4, 2.0),
    put('prp_lumen_lamp', 30.2, 14.8, 0.7), put('prp_lumen_lamp', 35.1, 18.9, 0.7),
    put('amb_wispling', 30.6, 13.3, 0.5, 2), put('amb_wispling', 34.3, 14.1, 0.45, 2),
    ...['crop_turnip_5', 'crop_turnip_4', 'crop_dawnbell', 'crop_turnip_3', 'crop_mandrake', 'crop_turnip_5', 'crop_turnip_2', 'crop_turnip_4', 'crop_dawnbell', 'crop_turnip_5']
      .map((id, i) => put(id, 29.5 + (i % 5), 19.93 + Math.floor(i / 5), 0.9)),
  ];
  const beacon = {
    z: 17.6,
    m: [put('prp_brazier', 32, 17.6, 1.6), put('bld_beacon_t2', 32, 17.6, 2.0), put('bld_beacon_t2', 32, 17.6, 2.5), put('bld_beacon_t2', 32, 17.6, 3.0)]
      .map((b, i) => b.m.replace('/>', ` data-beacon="${i}"${i === 1 ? '' : ' style="display:none"'}/>`)).join(''),
  };
  const wild = [];
  for (let tries = 0; wild.length < 120 && tries < 5000; tries++) {
    const x = rand() * (W + 1) - 0.5, y = rand() * (H + 1.6);
    if (dist(x, y) < 8.5 || inRiver(x, y) || nearTrail(x, y) || !free(x, y, 1.5)) continue;
    const [id, , a, b] = pick();
    wild.push(put(id, x, y, a + rand() * (b - a)));
    taken.push([x, y]);
  }
  const crystals = [];
  for (let tries = 0; crystals.length < 34 && tries < 5000; tries++) {
    const x = rand() * W, y = rand() * (H + 1);
    if (dist(x, y) < 10.5 || inRiver(x, y) || nearTrail(x, y) || !free(x, y, 1.6)) continue;
    crystals.push(put('prp_veil_crystal', x, y, 0.9 + rand() * 0.6));
    taken.push([x, y]);
  }
  const lilies = [5, 13, 22, 29].map(y => put('prp_lily_lotus', riverX(y) + 1.55, y, 1.0));
  const ground = (grass, id) => `<rect width="${W * T}" height="${H * T}" fill="url(#${grass})"/>` +
    trails.map(tr => trail(smooth(tr), 1.1).replace(/#PATH/g, `#${id}-path`)).join('') +
    `<path d="${band(bankL, bankR)}" fill="url(#${id}-water)"/>` +
    [bankL, bankR].map(b => `<path d="${smooth(b)}" fill="none" stroke="#3C6D62" stroke-width="14" stroke-linecap="round"/>`).join('');
  const defs = id => `<defs>${pat(`${id}-grass`, 'tile_grass', 2)}${pat(`${id}-veil`, 'tile_veil', 2)}${pat(`${id}-water`, 'tile_water', 1.5)}${pat(`${id}-path`, 'tile_path')}${pat(`${id}-tilled`, 'tile_tilled')}</defs>`;
  const vb = `viewBox="0 0 ${W * T} ${H * T}"`;
  const outside = `<svg class="base" ${vb} role="img" aria-label="Map of the Vale: the camp and its Beacon at the centre, forest and a river around it, Veil crystals outside the light">${defs('vo')}` +
    ground('vo-veil', 'vo') + layer([...wild, ...lilies, ...crystals]) + `</svg>`;
  const inside = `<svg class="layer m-in" ${vb} aria-hidden="true">${defs('vi')}` + ground('vi-grass', 'vi') +
    `<rect x="${29 * T}" y="${19 * T}" width="${5 * T}" height="${2 * T}" fill="url(#vi-tilled)" stroke="#6E4C37" stroke-width="8"/>` +
    `<circle cx="${C[0] * T}" cy="${(C[1] + 0.4) * T}" r="${1.4 * T}" fill="#FFC94A" opacity=".12"/>` +
    layer([...wild, ...lilies, ...camp, beacon]) + `</svg>`;
  return { outside, inside };
}

// ---------- 5. Page sections ----------
const PALETTE = [
  ['Meadow grass', [['light', '#D1D987'], ['mid', '#B6CE6F'], ['muted', '#98A067'], ['shade', '#698D66']]],
  ['Foliage & pines', [['light', '#729F8B'], ['dark', '#3C6D62'], ['deepest', '#345F50']]],
  ['Water', [['main', '#95C6C6'], ['light', '#B8DAD9'], ['foam', '#D9EAE7'], ['banks', '#3C6D62']]],
  ['Village stone & paths', [['cream', '#F9EAC5'], ['warm cream', '#F6E5B9'], ['sand path', '#E2CB9D'], ['stone shade', '#B8A689']]],
  ['Wood & village greens', [['bark', '#8E6D56'], ['dark bark', '#4B372B'], ['village green', '#B7B864'], ['deep olive', '#5F552F']]],
  ['Terracotta', [['lit', '#B85A40'], ['shade', '#8C5039'], ['dark', '#5E3827']]],
  ['Accents', [['mushroom gold', '#D7B068'], ['lotus pink', '#F0A7B4'], ['berry red', '#C9483E'], ['lavender', '#9E8AC8']]],
  ['Line darks', [['forest', '#2E3327'], ['village', '#554B2F']]],
];
const RESERVED = [
  ['The Veil', 'linear-gradient(90deg,#6B4FD8,#3FD6C6)', '#6B4FD8 → #3FD6C6', 'The Veil, Veil magic, and Veil-touched things. Nothing else.'],
  ['Heartflame & Lumen', 'linear-gradient(90deg,#FFC94A,#FFF3C4)', '#FFC94A → #FFF3C4', 'Your light, the Beacon, and royal power. Nothing else.'],
  ['Enemy telegraph', '#FF5A3C', '#FF5A3C', 'Warnings for incoming attacks. Nothing else.'],
];
const COUNTS = [
  ['Sworn rigs', 'Rigs', '5', '16', '24'],
  ['Portraits', 'Expressions', '67', '177', '278'],
  ['Creature forms (incl. Guardians)', 'Rigs / sheets', '15', '38', '60'],
  ['Bosses', 'Rigs', '2', '5', '11'],
  ['Terrain tilesets', 'Sets', '6', '8 (+ seasons)', '11'],
  ['Building exteriors', 'Illustrations', '16', '~47', '65'],
  ['Item icons', 'Icons', '~110', '~375', '~560'],
  ['Furniture & decor', 'Objects', '~20', '~70', '~120'],
  ['UI screens', 'Screens', '24', '28', '30'],
  ['VFX', 'Effects', '~77', '~116', '~139'],
];

const head = (id, title, count, text) =>
  `<div class="plate-head"><h2 id="${id}-title">${title}${count ? `<small>${count}</small>` : ''}</h2>${text ? `<p>${text}</p>` : ''}</div>`;

function sectionPalette() {
  return `<section class="plate wrap" id="palette" aria-labelledby="palette-title">` +
    head('palette', 'Palette', 'sampled from the mood references',
      'Locked for real during the Art Style Test. Line art is always a darker hue of the fill it surrounds, never pure black. Three colours are reserved for one job each, so players learn to read them instantly.') +
    `<div class="pal-grid">${PALETTE.map(([g, sw]) => `<div class="pal"><h3>${esc(g)}</h3><ul>${sw.map(([n, c]) =>
      `<li><span class="sw" style="--c:${c}"></span><span>${n}</span><code>${c}</code></li>`).join('')}</ul></div>`).join('')}</div>` +
    `<h3>Reserved</h3><div class="reserved">${RESERVED.map(([n, g, hex, t]) =>
      `<div class="res"><span class="bar" style="--g:${g}"></span><div><b>${esc(n)}</b><code>${hex}</code><p>${t}</p></div></div>`).join('')}</div></section>`;
}

function sectionCharacters() {
  const chars = of('character');
  const lineup = ['chr_sovereign', 'chr_bram', 'chr_linnea', 'chr_rook', 'chr_tamsin', 'chr_flicker'].map(id => {
    const a = byId[id], h = id === 'chr_flicker' ? 30 : 118;
    return `<figure><svg viewBox="0 0 ${a.w} ${a.h}" height="${h}" width="${r1((a.w / a.h) * h)}" role="img" aria-label="${esc(a.label)} silhouette"><use href="#i-${id}" filter="url(#f-sil)"/></svg><figcaption>${esc(a.label.replace('The ', ''))}</figcaption></figure>`;
  }).join('');
  return `<section class="plate wrap" id="characters" aria-labelledby="characters-title">` +
    head('characters', 'Characters', `${chars.length} assets`,
      'Chibi anime, 2.5 to 3 heads tall. An adult stands about 2 tiles tall in game (64 × 128 px at 1080p). Characters get the thickest outline in any scene so they pop off busy ground.') +
    `<div class="grid" style="--min:160px">${chars.map(a => card(a, { scale: a.id === 'chr_flicker' ? 1.5 : 1 })).join('')}</div>` +
    `<div class="silhouette"><div class="sil-row">` +
    `<svg width="0" height="0" aria-hidden="true" style="position:absolute"><filter id="f-sil" color-interpolation-filters="sRGB"><feComponentTransfer in="SourceAlpha" result="a"><feFuncA type="discrete" tableValues="0 0 0 1 1"/></feComponentTransfer><feFlood flood-color="#2B2620"/><feComposite in2="a" operator="in"/></filter></svg>` +
    `${lineup}</div><div><h3>Silhouette check</h3><p>Every Sworn must be recognisable from the silhouette alone, at true scale. These placeholders share one body, so hair and props do all the work. The artist's versions need different body shapes as well.</p></div></div></section>`;
}

function sectionCreatures() {
  const cres = of('creature');
  const lead = a => {
    const el = (a.note.split(' ')[0] || '').toLowerCase();
    return byId[`ico_el_${el}`] ? icon(`ico_el_${el}`) : '';
  };
  return `<section class="plate wrap" id="creatures" aria-labelledby="creatures-title">` +
    head('creatures', 'Creatures', `${cres.length} assets`,
      'Each creature reads as one simple shape in one element colour. Size S creatures are about 48 to 80 px on screen. The caption gives its element, how you form the Pact, and the farm job it takes on.') +
    `<div class="grid" style="--min:160px">${cres.map(a => card(a, { scale: 0.85, lead: lead(a) })).join('')}</div></section>`;
}

function sectionWorld() {
  const tiles = of('terrain').map(a => `<figure class="spec"><div class="stage g-sunk center" style="--stage:170px"><svg viewBox="0 0 256 256" width="128" height="128" role="img" aria-label="${esc(a.label)}, 2 × 2 tiles">` +
    `<use href="#i-${a.id}"/><use href="#i-${a.id}" x="128"/><use href="#i-${a.id}" y="128"/><use href="#i-${a.id}" x="128" y="128"/>` +
    `<path d="M128 0V256M0 128H256" stroke="#FFFFFF" stroke-opacity=".6" stroke-width="2" stroke-dasharray="6 6"/></svg></div>` +
    `<figcaption><div class="name"><span>${esc(a.label)}</span>${chip(a.ms)}</div><code>${a.id}</code>${a.note ? `<p class="note">${esc(a.note)}</p>` : ''}<p class="size">${SIZE(a)}</p></figcaption></figure>`).join('');
  const props = of('prop');
  return `<section class="plate wrap" id="world" aria-labelledby="world-title">` +
    head('world', 'World', `${of('terrain').length + props.length} assets`,
      'Terrain sits on a 64 px grid. Each tile is shown 2 × 2 so the seams are easy to check; the final tiles get 3 to 4 variants each and soft transition edges. Props stand on a soft contact shadow and take their light from the top left.') +
    `<h3>Terrain</h3><div class="grid" style="--min:170px">${tiles}</div>` +
    `<h3>Props</h3><div class="grid" style="--min:150px">${props.map(a => card(a, { scale: 0.78 })).join('')}</div></section>`;
}

function sectionFarming() {
  const stages = [['crop_turnip_1', 'Day 0', 'Planted'], ['crop_turnip_2', 'Day 1', 'Sprout'], ['crop_turnip_3', 'Day 2', 'Young'],
    ['crop_turnip_4', 'Day 3', 'Mature'], ['crop_turnip_5', 'Day 4', 'Ready to harvest']];
  const strip = stages.map(([id, d, l]) => `<figure><div class="soil">${art(byId[id], 1, byId[id].label)}</div><figcaption><b>${d}</b>${l}<code>${id}</code></figcaption></figure>`).join('');
  return `<section class="plate wrap" id="farming" aria-labelledby="farming-title">` +
    head('farming', 'Farming', `${of('crop').length} assets`,
      'Turnip, the 4-day starter crop, one stage per day. Every crop follows the same pattern: planted, growth stages, then a ready stage with a sparkle so a finished field reads at a glance.') +
    `<div class="farm-grid"><div class="strip-wrap"><div class="strip">${strip}</div><p class="size strip-note">Turnip · grows in 4 days · <code>crop_turnip_1…5</code> · ${chip('VS')}</p></div>` +
    ['crop_dawnbell', 'crop_mandrake'].map(id => card(byId[id], { scale: 1.6, ground: 'tilled', center: true })).join('') + `</div></section>`;
}

function sectionBuildings() {
  const blds = of('building');
  return `<section class="plate wrap" id="buildings" aria-labelledby="buildings-title">` +
    head('buildings', 'Buildings', `${blds.length} assets`,
      'Buildings snap to the tile grid, and their footprints include a one-tile walkable apron at the door. The Throne grows in place: the Ashen Throne becomes the Longhouse at the Founding.') +
    `<div class="grid" style="--min:200px;--stage:232px">${blds.map(a => card(a, { scale: Math.min(188 / a.w, 200 / a.h) })).join('')}</div></section>`;
}

function sectionItems() {
  const icons = of('icon'), els = of('element');
  return `<section class="plate wrap" id="items" aria-labelledby="items-title">` +
    head('items', 'Items & elements', `${icons.length + els.length} assets`,
      'Icons are 64 × 64 px, authored at 128, with the same coloured line art and top-left light as the world. Each element pairs a colour with a shape, so it still reads for colour-blind players.') +
    `<h3>Item icons</h3><div class="grid" style="--min:200px;--stage:112px">${icons.map(a => card(a, { ground: 'parch', center: true })).join('')}</div>` +
    `<h3>Elements</h3><div class="grid" style="--min:130px;--stage:112px">${els.map(a => card(a, { ground: 'parch', center: true })).join('')}</div></section>`;
}

const heart = on => `<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M6 10.6 1.7 6.3a2.6 2.6 0 0 1 4.3-3.2 2.6 2.6 0 0 1 4.3 3.2Z" fill="${on ? '#F07C8C' : 'none'}" stroke="${on ? '#FFD0D6' : '#F2CE78'}" stroke-opacity="${on ? 1 : 0.6}" stroke-width="1.2"/></svg>`;
const seal = () => {
  const bumps = Array.from({ length: 11 }, (_, i) => {
    const a = (i / 11) * Math.PI * 2;
    return `<circle cx="${r1(26 + Math.cos(a) * 20)}" cy="${r1(26 + Math.sin(a) * 20)}" r="${i % 3 ? 5 : 6.5}"/>`;
  }).join('');
  return `<svg class="seal" viewBox="0 0 52 52" aria-hidden="true"><g fill="#A33A3A">${bumps}<circle cx="26" cy="26" r="20"/></g>` +
    `<circle cx="26" cy="26" r="13" fill="none" stroke="#7A2323" stroke-width="2"/><path d="M18 31V21l4.5 4.5L26 18l3.5 7.5L34 21v10Z" fill="#E7B3A4"/></svg>`;
};

function sectionUI() {
  const hotbar = [['ico_hoe', ''], ['ico_turnip', '12'], ['ico_healing_herb', '5'], ['ico_vegetable_stew', '2'], ['ico_copper_ore', '18'],
    ['ico_veilglass', '3'], ['ico_twine_sigil', '4'], null, null, null];
  const slots = hotbar.map((s, i) => `<div class="slot${i === 0 ? ' on' : ''}"><b>${(i + 1) % 10}</b>${s ? icon(s[0], 'ico') + (s[1] ? `<span>${s[1]}</span>` : '') : ''}</div>`).join('');
  return `<section class="plate wrap" id="ui" aria-labelledby="ui-title">` +
    head('ui', 'Interface', 'mock-up',
      'Royal Storybook: parchment cards, deep navy panels, gold trim, and wax seals on royal actions like Decrees and Court Day. Shown here over the camp scene, drawn with the same kit.') +
    `<div class="ui"><div class="ui-bg" aria-hidden="true"><svg viewBox="${5 * T} ${2 * T} ${14 * T} ${7.875 * T}" preserveAspectRatio="xMidYMid slice"><use href="#hero-world"/></svg></div>` +
    `<div class="ui-grid">` +
    `<div class="ui-clock"><svg class="dial" viewBox="0 0 46 46" aria-hidden="true"><circle cx="23" cy="23" r="21" fill="#2B3A5C" stroke="#D9A03A" stroke-width="2"/><path d="M5 29h36" stroke="#F2CE78" stroke-opacity=".5" stroke-width="1.5"/><circle cx="33" cy="25" r="6" fill="#FFC94A" stroke="#FFF3C4" stroke-width="1.5"/></svg>` +
    `<div><b>Spring 5 · Fri</b><span class="time">17:20</span></div><div class="gold">${icon('ico_gold', 'coin')}1,240 g</div></div>` +
    `<div class="ui-bars"><div class="bar hp"><span>HP</span><i style="--v:.82"></i></div><div class="bar en"><span>Energy</span><i style="--v:.64"></i></div>` +
    `<div class="bar ex"><span>Exposure</span><i style="--v:.46"></i><em><span class="diamond" aria-hidden="true"></span>46 · Chilled</em></div></div>` +
    `<div class="ui-dialog"><div class="portrait"><svg viewBox="12 8 72 72" role="img" aria-label="Linnea"><use href="#i-chr_linnea"/></svg></div>` +
    `<div><div class="nameplate">Linnea <span class="hearts" aria-label="3 of 10 hearts">${Array.from({ length: 10 }, (_, i) => heart(i < 3)).join('')}</span></div>` +
    `<p class="line">“Chamomile for sleep, yarrow for cuts… and for kings who don't rest, a stern talking-to.”</p>` +
    `<div class="choices"><span class="choice on">“I'll rest tonight. Promise.”</span><span class="choice">“Kings don't nap.”</span></div></div></div>` +
    `<div class="ui-hotbar" aria-label="Hotbar">${slots}</div>` +
    `<article class="ui-petition"><header>${seal()}<div><small>Court Day · petition</small><h4>Repair Request</h4></div></header>` +
    `<p class="from">From <b>Maren Holt</b>, settler · farmer</p><blockquote>“The Hut roof leaks. Can the crown spare 20 Wood?”</blockquote>` +
    `<ul class="opts"><li><b>Grant</b><span>−20 Wood · +Joy</span></li><li><b>Delay</b><span>−Joy</span></li></ul>` +
    `<p class="when">Court Day opens at Village rank. Petitions are data-driven cards: a template plus names, items, and amounts.</p></article>` +
    `</div></div></section>`;
}

function sectionVeil() {
  const { outside, inside } = veilMap();
  const motes = Array.from({ length: 22 }, (_, i) =>
    `<span class="mote" style="--a:${r1(i * 16.36 + (i % 3) * 5)}deg;--o:${[-1.2, 0.6, -0.3, 1.1, -0.8][i % 5]}%;--d:${r1((i % 7) * 0.45)}s"></span>`).join('');
  const tiers = [['T1 Brazier', 10, 'VS'], ['T2 Tower', 18, 'VS'], ['T3 Great Beacon', 28, 'EA'], ['T4 Sunspire', 40, '1.0']];
  return `<section class="plate wrap" id="veil" aria-labelledby="veil-title">` +
    head('veil', 'The Veil', 'interactive',
      'The Beacon\'s light is your Realm. Inside it there is no Exposure and nothing Hollowed spawns, except on Surge nights. Outside, colour drains and Veil soil spreads. Pick a Beacon tier to push the light back, and switch to night to feel the frontier.') +
    `<div class="veil-frame animated is-night" id="veil-frame">${outside}<div class="layer tint m-out"></div>${inside}` +
    `<div class="layer fog m-out"><div class="fog-sheet a" data-fog="a"></div><div class="fog-sheet b" data-fog="b"></div></div>` +
    `<div class="ring" aria-hidden="true"><div class="motes">${motes}</div></div>` +
    `<div class="layer night-dim"></div><div class="layer night-out m-out"></div><div class="layer night-warm"></div>` +
    `<div class="scalebar" aria-hidden="true"><i></i>10 tiles</div></div>` +
    `<div class="controls"><div class="seg" role="group" aria-label="Beacon tier">${tiers.map(([n, r, ms], i) =>
      `<button type="button" id="tier-${i + 1}" data-tier="${i}" aria-pressed="${i === 1}">${n}<small>${r} tiles · ${ms}</small></button>`).join('')}</div>` +
    `<div class="seg" role="group" aria-label="Time of day"><button type="button" id="time-day" data-time="day" aria-pressed="false">Day<small>clear</small></button>` +
    `<button type="button" id="time-night" data-time="night" aria-pressed="true">Night<small>+4 Exposure / 10 min</small></button></div></div>` +
    `<p class="readout" id="veil-readout" aria-live="polite"><strong>T2 · Beacon Tower</strong> Realm radius <strong>18 tiles</strong>, about <strong>1,018</strong> tiles of safe ground.` +
    `<span>Outside the light at night: Exposure climbs +4 every 10 minutes and the Hollowed hunt.</span></p>` +
    `<p class="size">Illustrative map, 64 × 34 tiles around the Beacon. The fog, light edge, and colour loss follow the Veil spec in the Art Direction doc (§8).</p></section>`;
}

function sectionCounts() {
  return `<section class="plate wrap" id="counts" aria-labelledby="counts-title">` +
    head('counts', 'What the artist will draw', 'totals by milestone',
      'The kit stands in for a small slice of the art the game needs. These totals come from the Master Asset List; VS is the Vertical Slice and EA is Early Access.') +
    `<div class="table-wrap"><table><thead><tr><th scope="col">Category</th><th scope="col">Unit</th><th scope="col" class="n">VS</th><th scope="col" class="n">EA</th><th scope="col" class="n">1.0</th></tr></thead><tbody>` +
    COUNTS.map(([c, u, ...n]) => `<tr><th scope="row">${esc(c)}</th><td><small>${u}</small></td>${n.map(v => `<td class="n">${v}</td>`).join('')}</tr>`).join('') +
    `</tbody></table></div></section>`;
}

// ---------- 6. Assemble ----------
const CSS = readFileSync(join(HERE, 'gallery.css'), 'utf8')
  .replace('/*TILES*/', ['grass', 'tilled'].map(t => `--t-${t}:url("data:image/svg+xml;base64,${b64(byId[`tile_${t}`].svg)}");`).join(''));
const JS = readFileSync(join(HERE, 'gallery-client.js'), 'utf8');
const logo = byId.logo_kingsbloom;
const cats = new Set(ASSETS.map(a => a.cat)).size;

const headHtml = `<title>Kingsbloom Asset Atlas</title>
<meta name="description" content="In-house placeholder art for Kingsbloom: ${ASSETS.length} hand-made vector assets, a camp scene, a UI mock-up, and a live Veil demo.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=IBM+Plex+Mono:wght@500;600&family=Nunito:ital,wght@0,400;0,600;0,700;0,800;1,600&display=swap">
<style>${CSS}</style>`;

const bodyHtml = `${sprite}
<header class="top"><div class="wrap"><a class="brand" href="#top" aria-label="Kingsbloom Asset Atlas, back to top"><svg viewBox="0 0 256 256" aria-hidden="true"><use href="#i-logo_kingsbloom"/></svg><b>Kingsbloom</b><span>Asset Atlas</span></a>
<nav class="sections" aria-label="Sections">${[['palette', 'Palette'], ['characters', 'Characters'], ['creatures', 'Creatures'], ['world', 'World'], ['farming', 'Farming'],
  ['buildings', 'Buildings'], ['items', 'Items'], ['ui', 'Interface'], ['veil', 'The Veil'], ['counts', 'Totals']].map(([h, t]) => `<a href="#${h}">${t}</a>`).join('')}</nav></div></header>
<main id="top">
<section class="hero wrap" aria-labelledby="hero-title">
<div class="hero-grid"><div>
<p class="eyebrow">Placeholder art kit · made in-house · never ships</p>
<h1 id="hero-title">Kingsbloom<span>Asset Atlas</span></h1>
<p class="lede">Every asset on this page was drawn in-house as simple vector art in the Kingsbloom style: coloured line art, two-tone cel shading, light from the top left, soft contact shadows. It lets our prototypes look like the game before we hire an artist. The artist replaces all of it, starting with the Art Style Test (Step 13).</p>
<dl class="facts"><div><dt>Assets</dt><dd>${ASSETS.length}</dd></div><div><dt>Categories</dt><dd>${cats}</dd></div><div><dt>Grid</dt><dd>1 tile = 64 px</dd></div><div><dt>Authored at</dt><dd>2× (128 px)</dd></div></dl>
</div>
<figure class="mark">${art(logo, 1, 'Kingsbloom logo: a broken crown with a sprout and a Kingsbloom bud')}<figcaption><code>${logo.id}</code>${chip(logo.ms)}</figcaption></figure>
</div>
<figure class="scene"><div class="frame animated">${heroScene()}<div class="hero-fog" aria-hidden="true"><div class="fog-sheet a" data-fog="a"></div></div></div>
<figcaption class="cap">The Exile's Camp on Spring 5, drawn with kit assets at in-game scale: the Ashen Throne and Heartflame Brazier, Bram (joined on day 3), a turnip plot with Puddlepup on watering duty, Mossbun and Emberkit, Jellop by the river, and the Veil pressing in from the west.</figcaption></figure>
</section>
${sectionPalette()}
${sectionCharacters()}
${sectionCreatures()}
${sectionWorld()}
${sectionFarming()}
${sectionBuildings()}
${sectionItems()}
${sectionUI()}
${sectionVeil()}
${sectionCounts()}
</main>
<footer class="foot"><div class="wrap">
<p><b>Kingsbloom</b> · Project NOZE · placeholder kit v0.1, September 2026</p>
<p>Rebuild this page and the SVG files with <code>node art/placeholder/build.mjs</code>. The art lives in <code>art/placeholder/kit.mjs</code>.</p>
<p>Placeholder art never ships. The two mood references guide the feel only; nothing is traced or copied from them.</p>
</div></footer>
<script>${JS}</script>`;

writeFileSync(join(HERE, 'gallery.html'), `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
${headHtml}
</head>
<body>
${bodyHtml}
</body>
</html>
`);
const fi = process.argv.indexOf('--fragment');
if (fi > 0) writeFileSync(process.argv[fi + 1], `${headHtml}\n${bodyHtml}\n`);
console.log(`Wrote ${ASSETS.length} SVG files and gallery.html (${Math.round(Buffer.byteLength(headHtml + bodyHtml) / 1024)} KB)`);
