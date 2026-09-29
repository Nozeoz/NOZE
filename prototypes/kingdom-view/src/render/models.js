// Procedural low-poly models for every building and prop. Placeholder art in the spirit of the
// Dawnmere Vale palette: cream plaster, dark timber, terracotta and thatch, warm lantern glass.
// Each model has a solid part (lit, casts shadows) and a glow part (lanterns, windows, bulbs),
// plus the lights, chimney smoke and flames the renderer should attach. Models face +z.
import { Kit, hashRand } from './kit.js';
import { P, AWNINGS, BANNERS, FLOWERS, HUT_ROOFS, GOODS_COLORS } from './palette.js';

const WIN = 2.4; // window glow intensity
const GLASS = 3.2; // lantern glass

function M() { return { s: new Kit(), g: new Kit(), lights: [], smoke: [], flames: [] }; }

function timberWalls(m, w, h, d, { y = 0, z = 0, wall = P.plaster, beam = P.woodDark } = {}) {
  m.s.box(w, h, d, wall, { y, z });
  const t = 0.07;
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) m.s.box(t, h, t, beam, { x: sx * (w / 2), z: z + sz * (d / 2), y });
  for (const sz of [-1, 1]) {
    m.s.box(w + t, t, t, beam, { y: y + h - t, z: z + sz * (d / 2) });
    m.s.box(w + t, t * 0.8, t, beam, { y: y + h * 0.42, z: z + sz * (d / 2) });
  }
  for (const sx of [-1, 1]) m.s.box(t, t, d + t, beam, { y: y + h - t, x: sx * (w / 2), z });
}

function windowAt(m, x, y, z, { w = 0.28, h = 0.26, face = 'front', frame = P.woodDark } = {}) {
  if (face === 'front') {
    m.g.box(w, h, 0.03, P.window, { x, y, z, intensity: WIN });
    m.s.box(w + 0.06, 0.04, 0.05, frame, { x, y: y - 0.02, z });
    m.s.box(0.035, h, 0.045, frame, { x, y, z: z + 0.012 });
    m.s.box(w, 0.03, 0.045, frame, { x, y: y + h / 2 - 0.015, z: z + 0.012 });
  } else {
    m.g.box(0.03, h, w, P.window, { x, y, z, intensity: WIN });
    m.s.box(0.05, 0.04, w + 0.06, frame, { x, y: y - 0.02, z });
    m.s.box(0.045, h, 0.035, frame, { x: x + (x > 0 ? 0.012 : -0.012), y, z });
  }
}

function door(m, x, z, { w = 0.34, h = 0.62, color = P.woodDark } = {}) {
  m.s.box(w, h, 0.05, color, { x, y: 0.2, z });
  m.s.box(0.05, 0.05, 0.02, P.gold, { x: x + w * 0.3, y: 0.2 + h * 0.45, z: z + 0.03 });
}

function lantern(m, x, y, z, r = 1.6) {
  m.s.box(0.13, 0.03, 0.13, P.iron, { x, y: y + 0.16, z });
  m.s.hip(0.16, 0.16, 0.08, P.iron, { x, y: y + 0.19, z });
  m.g.box(0.1, 0.15, 0.1, P.heartflame, { x, y, z, intensity: GLASS });
  m.lights.push({ x, y: y + 0.08, z, r });
}

function chimney(m, x, z, top, { w = 0.24 } = {}) {
  m.s.box(w, top, w, P.stoneShade, { x, z, y: 0.2 });
  m.s.box(w + 0.06, 0.06, w + 0.06, P.stoneGrey, { x, z, y: top + 0.2 });
  m.smoke.push({ x, y: top + 0.32, z });
}

// ─── lights and paths ────────────────────────────────────────────────────────
export function lamp() {
  const m = M();
  m.s.box(0.3, 0.12, 0.3, P.stoneShade);
  m.s.cyl(0.045, 0.06, 1.4, 6, P.iron, { y: 0.12 });
  m.s.box(0.3, 0.04, 0.04, P.iron, { y: 1.46 });
  const top = 1.34;
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) m.s.box(0.025, 0.26, 0.025, P.iron, { x: sx * 0.1, z: sz * 0.1, y: top });
  m.s.hip(0.3, 0.3, 0.14, P.iron, { y: top + 0.26 });
  m.s.sphere(0.03, P.gold, { y: top + 0.43 });
  m.g.box(0.17, 0.22, 0.17, P.heartflame, { y: top + 0.02, intensity: GLASS });
  m.lights.push({ x: 0, y: top + 0.12, z: 0, r: 3.6, main: true });
  return m;
}

export function stringLights() {
  const m = M();
  const ends = [-1.3, 1.3];
  for (const z of ends) {
    m.s.box(0.16, 0.08, 0.16, P.stoneShade, { z });
    m.s.cyl(0.035, 0.045, 2.0, 6, P.woodDark, { z, y: 0.08 });
  }
  const pts = [];
  for (let i = 0; i <= 12; i++) {
    const t = i / 12;
    const z = -1.3 + 2.6 * t;
    const y = 2.02 - 0.34 * Math.sin(Math.PI * t);
    pts.push([0, y, z]);
  }
  for (let i = 0; i < pts.length - 1; i++) m.s.beam(pts[i], pts[i + 1], 0.012, P.lineForest, 4);
  for (let i = 1; i < pts.length - 1; i += 1) {
    const [x, y, z] = pts[i];
    m.g.sphere(0.055, i % 3 === 0 ? P.heartCream : P.heartflame, { x, y: y - 0.07, z, intensity: GLASS }, 6, 5);
  }
  for (const z of [-1, 0, 1]) m.lights.push({ x: 0, y: 1.75, z, r: 2.3, main: z === 0 });
  return m;
}

// ─── market and work ─────────────────────────────────────────────────────────
function goodsDisplay(m, goods, x, y, z) {
  const R = hashRand(goods.length * 7 + 3);
  if (goods === 'harvest') {
    m.s.box(0.34, 0.12, 0.26, P.wood, { x, y, z });
    for (let i = 0; i < 6; i++) {
      const px = x - 0.11 + (i % 3) * 0.11;
      const pz = z - 0.05 + Math.floor(i / 3) * 0.1;
      m.s.sphere(0.055, '#EFE6F2', { x: px, y: y + 0.14, z: pz }, 6, 5);
      m.s.sphere(0.03, '#9E6BB0', { x: px, y: y + 0.17, z: pz }, 5, 4);
      m.s.cone(0.03, 0.08, 4, '#6FA35A', { x: px, y: y + 0.18, z: pz });
    }
  } else if (goods === 'grain') {
    m.s.box(0.34, 0.08, 0.26, P.woodLight, { x, y, z });
    for (let i = 0; i < 4; i++) m.s.sphere(0.07, '#C98B4F', { x: x - 0.1 + (i % 2) * 0.2, y: y + 0.12, z: z - 0.05 + Math.floor(i / 2) * 0.1, sx: 1.4, sy: 0.8 }, 7, 5);
  } else if (goods === 'catch') {
    m.s.box(0.36, 0.1, 0.26, P.wood, { x, y, z });
    m.s.box(0.32, 0.03, 0.22, '#DDEFF2', { x, y: y + 0.1, z });
    for (let i = 0; i < 3; i++) {
      m.s.sphere(0.05, '#9FC3D1', { x: x - 0.1 + i * 0.1, y: y + 0.16, z, sx: 2.2, sy: 0.7, ry: 0.3 * i }, 6, 4);
    }
  } else if (goods === 'stew') {
    m.s.cyl(0.13, 0.11, 0.14, 8, P.iron, { x, y, z });
    m.g.cyl(0.115, 0.115, 0.02, 8, '#E08A45', { x, y: y + 0.13, z, intensity: 1.6 });
    m.smoke.push({ x, y: y + 0.25, z, small: true });
  } else if (goods === 'tonic') {
    for (let i = 0; i < 5; i++) {
      const c = ['#9E8AC8', '#7FC4A0', '#E8A0C0', '#9E8AC8', '#7FB2C4'][i];
      m.s.cyl(0.035, 0.04, 0.12, 6, '#E9EEF0', { x: x - 0.16 + i * 0.08, y, z: z + (R() - 0.5) * 0.08 });
      m.g.cyl(0.03, 0.035, 0.07, 6, c, { x: x - 0.16 + i * 0.08, y: y + 0.01, z: z + (R() - 0.5) * 0.08, intensity: 1.3 });
    }
  }
}

export function stall(variant = 0, goods = 'harvest') {
  const m = M();
  const awn = AWNINGS[variant % AWNINGS.length];
  m.s.box(1.8, 0.55, 0.42, P.wood, { z: 0.16 });
  m.s.box(1.9, 0.06, 0.52, P.woodDark, { z: 0.16, y: 0.55 });
  for (const x of [-0.6, 0, 0.6]) m.s.box(0.04, 0.4, 0.02, P.woodDark, { x, y: 0.1, z: 0.38 });
  // back shelf with more goods
  m.s.box(1.6, 0.7, 0.2, P.woodDark, { z: -0.36 });
  m.s.box(1.6, 0.04, 0.26, P.wood, { z: -0.33, y: 0.7 });
  for (const sx of [-0.88, 0.88]) {
    m.s.box(0.07, 1.62, 0.07, P.woodDark, { x: sx, z: -0.42 });
    m.s.box(0.07, 1.3, 0.07, P.woodDark, { x: sx, z: 0.44 });
  }
  // striped, sloping awning
  const stripes = 7;
  const slope = Math.atan2(0.34, 1.0);
  for (let i = 0; i < stripes; i++) {
    const x = -0.95 + (1.9 / stripes) * (i + 0.5);
    m.s.box(1.9 / stripes + 0.005, 0.035, 1.06, i % 2 ? P.canvas : awn, { x, y: 1.44, z: 0.02, rx: slope });
  }
  // scalloped valance
  for (let i = 0; i < stripes; i++) {
    const x = -0.95 + (1.9 / stripes) * (i + 0.5);
    m.s.box(1.9 / stripes, 0.14, 0.02, i % 2 ? P.canvas : awn, { x, y: 1.14, z: 0.53 });
  }
  goodsDisplay(m, goods, -0.45, 0.61, 0.18);
  goodsDisplay(m, goods, 0.35, 0.61, 0.18);
  goodsDisplay(m, goods, 0, 0.74, -0.33);
  lantern(m, 0.72, 1.02, 0.5, 1.6);
  m.s.beam([0.72, 1.3, 0.5], [0.72, 1.2, 0.5], 0.01, P.iron, 4);
  return m;
}

export function fieldTurnip() {
  const m = M();
  m.s.box(2.9, 0.07, 2.9, P.soil);
  const R = hashRand(11);
  for (const z of [-1.05, -0.35, 0.35, 1.05]) {
    m.s.box(2.7, 0.07, 0.3, P.soilRidge, { z, y: 0.07 });
    for (let i = 0; i < 7; i++) {
      const x = -1.2 + i * 0.4 + (R() - 0.5) * 0.08;
      m.s.sphere(0.075, '#EFE6F2', { x, y: 0.16, z }, 6, 5);
      m.s.sphere(0.045, '#9E6BB0', { x, y: 0.2, z }, 5, 4);
      for (let k = 0; k < 3; k++) m.s.cone(0.05, 0.24, 4, k % 2 ? P.leafA : P.leafB, { x: x + Math.cos(k * 2.1) * 0.04, y: 0.19, z: z + Math.sin(k * 2.1) * 0.04, rx: Math.cos(k * 2.1) * 0.5, rz: Math.sin(k * 2.1) * 0.5 });
    }
  }
  // scarecrow
  m.s.cyl(0.03, 0.03, 1.1, 5, P.woodDark, { x: 1.25, z: -1.25 });
  m.s.beam([0.95, 0.78, -1.25], [1.55, 0.78, -1.25], 0.025, P.woodDark);
  m.s.box(0.3, 0.34, 0.16, '#A4583E', { x: 1.25, y: 0.55, z: -1.25 });
  m.s.sphere(0.12, '#E6CFA0', { x: 1.25, y: 1.02, z: -1.25 }, 7, 6);
  m.s.cyl(0.26, 0.26, 0.03, 10, P.thatch, { x: 1.25, y: 1.1, z: -1.25 });
  m.s.cone(0.14, 0.16, 8, P.thatch, { x: 1.25, y: 1.12, z: -1.25 });
  return m;
}

export function fieldWheat() {
  const m = M();
  m.s.box(2.9, 0.07, 2.9, P.soil);
  const R = hashRand(29);
  for (let i = 0; i < 64; i++) {
    const x = -1.25 + (i % 8) * 0.36 + (R() - 0.5) * 0.12;
    const z = -1.25 + Math.floor(i / 8) * 0.36 + (R() - 0.5) * 0.12;
    const h = 0.5 + R() * 0.2;
    for (let k = 0; k < 3; k++) {
      const a = k * 2.1 + R();
      m.s.box(0.025, h, 0.025, k % 2 ? '#D9B85C' : '#C9A24A', { x: x + Math.cos(a) * 0.05, z: z + Math.sin(a) * 0.05, y: 0.07, rx: Math.sin(a) * 0.12, rz: Math.cos(a) * 0.12 });
      m.s.box(0.05, 0.12, 0.05, '#E8C872', { x: x + Math.cos(a) * 0.05 + Math.cos(a) * 0.012 * h, z: z + Math.sin(a) * 0.05, y: 0.07 + h - 0.02 });
    }
  }
  return m;
}

export function fishery() {
  const m = M();
  m.s.box(1.2, 0.14, 1.1, P.stoneShade, { x: -0.3, z: -0.3 });
  m.s.box(1.0, 0.75, 0.9, P.woodLight, { x: -0.3, z: -0.3, y: 0.14 });
  for (let i = 0; i < 5; i++) m.s.box(1.02, 0.03, 0.92, P.wood, { x: -0.3, z: -0.3, y: 0.2 + i * 0.14 });
  m.s.roof(1.3, 1.25, 0.6, P.terracottaShade, { x: -0.3, z: -0.3, y: 0.88 });
  door(m, -0.3, 0.16, { h: 0.55 });
  windowAt(m, 0.21, 0.5, -0.3, { face: 'side', w: 0.22, h: 0.2 });
  lantern(m, 0.05, 0.72, 0.2, 1.4);
  // drying rack with fish
  for (const x of [0.25, 0.85]) m.s.cyl(0.03, 0.03, 0.9, 5, P.woodDark, { x, z: 0.55 });
  m.s.beam([0.25, 0.86, 0.55], [0.85, 0.86, 0.55], 0.02, P.woodDark);
  for (let i = 0; i < 4; i++) m.s.sphere(0.05, '#9FC3D1', { x: 0.33 + i * 0.15, y: 0.72, z: 0.55, sx: 0.7, sy: 2 }, 5, 4);
  // barrel and nets
  m.s.cyl(0.14, 0.12, 0.34, 8, P.wood, { x: 0.65, z: -0.55 });
  m.s.cyl(0.145, 0.145, 0.03, 8, P.iron, { x: 0.65, z: -0.55, y: 0.24 });
  m.s.ico(0.18, '#8A9A7A', { x: 0.55, y: 0.06, z: -0.1, sy: 0.35 });
  return m;
}

export function cookhouse() {
  const m = M();
  m.s.box(2.8, 0.2, 1.7, P.stoneShade, { z: -0.1 });
  timberWalls(m, 2.5, 1.0, 1.4, { y: 0.2 });
  m.s.roof(2.9, 1.95, 0.95, P.terracotta, { y: 1.2, z: -0.1 });
  m.s.box(2.95, 0.06, 0.08, P.terracottaDark, { y: 1.2, z: 0.87 });
  chimney(m, 0.85, -0.35, 1.75, { w: 0.34 });
  door(m, -0.25, 0.71, { w: 0.4, h: 0.66 });
  windowAt(m, 0.5, 0.62, 0.71);
  windowAt(m, -0.85, 0.62, 0.71);
  // cauldron over a little fire
  m.s.cyl(0.2, 0.15, 0.24, 9, P.iron, { x: 0.95, y: 0.12, z: 0.82 });
  m.g.cyl(0.18, 0.18, 0.02, 9, '#E08A45', { x: 0.95, y: 0.35, z: 0.82, intensity: 1.5 });
  for (const a of [0, 2.1, 4.2]) m.s.beam([0.95 + Math.cos(a) * 0.26, 0, 0.82 + Math.sin(a) * 0.26], [0.95, 0.5, 0.82], 0.02, P.woodDark);
  m.flames.push({ x: 0.95, y: 0.02, z: 0.82, s: 0.35 });
  m.lights.push({ x: 0.95, y: 0.3, z: 0.82, r: 2 });
  m.smoke.push({ x: 0.95, y: 0.45, z: 0.82, small: true });
  // crates
  m.s.box(0.32, 0.3, 0.32, P.woodLight, { x: -1.1, z: 0.82 });
  return m;
}

export function tent() {
  const m = M();
  m.s.roof(1.5, 1.4, 1.05, P.canvas, { ry: Math.PI / 2 });
  m.s.roof(1.52, 0.4, 0.3, '#5E8F86', { ry: Math.PI / 2, y: 0.76, sx: 1, sz: 1 });
  m.s.roof(0.02, 0.9, 0.7, '#3A302A', { ry: Math.PI / 2, z: 0.75 });
  for (const z of [-0.76, 0.76]) m.s.cyl(0.025, 0.025, 1.15, 5, P.woodDark, { z });
  m.s.box(0.5, 0.06, 0.3, '#8C6A4E', { x: 0.5, z: 0.6 });
  lantern(m, -0.55, 0.28, 0.72, 1.1);
  m.s.cyl(0.02, 0.02, 0.3, 4, P.woodDark, { x: -0.55, z: 0.72 });
  return m;
}

export function hut(variant = 0) {
  const m = M();
  const roof = HUT_ROOFS[variant % HUT_ROOFS.length];
  m.s.box(1.7, 0.22, 1.6, P.stoneShade);
  timberWalls(m, 1.46, 0.95, 1.36, { y: 0.22 });
  m.s.roof(1.9, 1.85, 0.95, roof, { y: 1.17 });
  if (variant % HUT_ROOFS.length === 0) m.s.roof(1.94, 0.35, 0.18, '#B89048', { y: 1.93 });
  chimney(m, 0.45, -0.32, 1.55);
  door(m, -0.3, 0.7);
  windowAt(m, 0.35, 0.6, 0.7);
  windowAt(m, 0.74, 0.6, -0.2, { face: 'side', w: 0.24, h: 0.22 });
  // flower box
  m.s.box(0.36, 0.08, 0.1, P.wood, { x: 0.35, y: 0.42, z: 0.76 });
  const R = hashRand(variant + 5);
  for (let i = 0; i < 4; i++) m.s.sphere(0.04, FLOWERS[Math.floor(R() * 4)], { x: 0.22 + i * 0.09, y: 0.53, z: 0.77 }, 5, 4);
  m.lights.push({ x: 0.35, y: 0.6, z: 0.9, r: 1.5 });
  return m;
}

// ─── decor ───────────────────────────────────────────────────────────────────
export function flowers(variant = 0) {
  const m = M();
  m.s.box(0.82, 0.1, 0.82, P.soil);
  for (const [x, z, w, d] of [[0, 0.41, 0.9, 0.08], [0, -0.41, 0.9, 0.08], [0.41, 0, 0.08, 0.9], [-0.41, 0, 0.08, 0.9]]) m.s.box(w, 0.14, d, P.stoneShade, { x, z });
  const R = hashRand(variant * 13 + 1);
  const main = FLOWERS[variant % FLOWERS.length];
  for (let i = 0; i < 11; i++) {
    const x = (R() - 0.5) * 0.6;
    const z = (R() - 0.5) * 0.6;
    const h = 0.14 + R() * 0.12;
    m.s.cone(0.07, 0.16, 5, P.leafB, { x, z, y: 0.08 });
    m.s.cyl(0.012, 0.012, h, 4, P.leafA, { x, z, y: 0.1 });
    m.s.ico(0.075 + R() * 0.03, i % 4 === 3 ? '#FFF6E6' : main, { x, z, y: 0.12 + h });
  }
  return m;
}

export function tree(variant = 0) {
  const m = M();
  const v = variant % 3;
  if (v === 0) {
    m.s.cyl(0.07, 0.11, 0.85, 6, P.woodDark);
    m.s.ico(0.5, P.leafB, { y: 1.12 }, 1);
    m.s.ico(0.36, P.leafA, { x: 0.25, y: 1.35, z: 0.1 }, 1);
    m.s.ico(0.32, P.leafC, { x: -0.2, y: 1.42, z: -0.12 }, 1);
  } else if (v === 1) {
    m.s.cyl(0.05, 0.08, 1.2, 6, '#ECE6D6');
    for (const y of [0.35, 0.62, 0.9]) m.s.box(0.1, 0.03, 0.09, '#3A3A36', { y, x: 0.02 });
    m.s.ico(0.36, '#A5C46A', { y: 1.35, sy: 1.4 }, 1);
    m.s.ico(0.26, '#B7D27A', { x: 0.18, y: 1.1, sy: 1.2 }, 1);
  } else {
    m.s.cyl(0.06, 0.1, 0.8, 6, '#5B4034');
    m.s.ico(0.46, '#F2B3C2', { y: 1.08 }, 1);
    m.s.ico(0.32, '#E89AAE', { x: -0.24, y: 1.28, z: 0.08 }, 1);
    m.s.ico(0.3, '#F7C9D3', { x: 0.2, y: 1.36, z: -0.1 }, 1);
  }
  return m;
}

export function bench() {
  const m = M();
  m.s.box(0.82, 0.06, 0.3, P.wood, { y: 0.3 });
  m.s.box(0.82, 0.24, 0.05, P.wood, { y: 0.4, z: -0.15, rx: -0.12 });
  for (const x of [-0.34, 0.34]) for (const z of [-0.1, 0.1]) m.s.box(0.06, 0.3, 0.06, P.woodDark, { x, z });
  return m;
}

export function banner(variant = 0) {
  const m = M();
  const cloth = BANNERS[variant % BANNERS.length];
  m.s.box(0.2, 0.1, 0.2, P.stoneShade);
  m.s.cyl(0.035, 0.04, 1.95, 6, P.woodDark, { y: 0.1 });
  m.s.sphere(0.06, P.gold, { y: 2.08 });
  m.s.beam([-0.3, 1.9, 0], [0.3, 1.9, 0], 0.02, P.woodDark);
  m.s.box(0.52, 0.9, 0.03, cloth, { y: 0.98, z: 0.04 });
  m.s.box(0.18, 0.18, 0.03, cloth, { x: -0.13, y: 0.86, z: 0.04, rz: Math.PI / 4 });
  m.s.box(0.18, 0.18, 0.03, cloth, { x: 0.13, y: 0.86, z: 0.04, rz: Math.PI / 4 });
  // the Kingsbloom crest: a gold bloom over a gold bar
  m.s.box(0.3, 0.035, 0.01, P.gold, { y: 1.35, z: 0.06 });
  for (const [x, y] of [[0, 1.6], [-0.08, 1.52], [0.08, 1.52], [0, 1.44]]) m.s.sphere(0.055, P.gold, { x, y, z: 0.06, sz: 0.3 }, 7, 5);
  return m;
}

export function hedge() {
  const m = M();
  m.s.box(0.86, 0.5, 0.86, '#4E7A48');
  const R = hashRand(4);
  for (let i = 0; i < 6; i++) m.s.ico(0.2, i % 2 ? '#5C8A52' : '#4E7A48', { x: (R() - 0.5) * 0.6, y: 0.52, z: (R() - 0.5) * 0.6, sy: 0.6 }, 0);
  return m;
}

export function crates() {
  const m = M();
  m.s.box(0.36, 0.34, 0.36, P.woodLight, { x: -0.18, z: 0.1 });
  m.s.box(0.3, 0.28, 0.3, P.wood, { x: -0.16, z: 0.08, y: 0.34, ry: 0.4 });
  m.s.box(0.37, 0.04, 0.05, P.woodDark, { x: -0.18, z: 0.29, y: 0.14 });
  m.s.cyl(0.15, 0.13, 0.4, 8, P.wood, { x: 0.22, z: -0.14 });
  for (const y of [0.08, 0.3]) m.s.cyl(0.155, 0.155, 0.025, 8, P.iron, { x: 0.22, z: -0.14, y });
  m.s.sphere(0.07, '#E0A040', { x: 0.2, y: 0.44, z: -0.1 }, 6, 5);
  return m;
}

export function well() {
  const m = M();
  m.s.cyl(0.38, 0.4, 0.42, 10, P.stoneCream);
  m.s.cyl(0.3, 0.3, 0.02, 10, '#2B3A3A', { y: 0.4 });
  for (const x of [-0.33, 0.33]) m.s.box(0.06, 1.05, 0.06, P.woodDark, { x, y: 0.4 });
  m.s.roof(0.9, 0.7, 0.34, P.terracotta, { y: 1.38 });
  m.s.beam([-0.33, 1.12, 0], [0.33, 1.12, 0], 0.03, P.wood);
  m.s.cyl(0.08, 0.07, 0.12, 7, P.wood, { y: 0.75 });
  m.s.beam([0, 1.1, 0], [0, 0.87, 0], 0.006, '#6A5A48', 3);
  return m;
}

export function fountain() {
  const m = M();
  m.s.cyl(0.92, 0.96, 0.34, 16, P.stoneCream);
  m.s.cyl(0.8, 0.8, 0.03, 16, P.water, { y: 0.28 });
  m.g.cyl(0.78, 0.78, 0.01, 16, P.waterLight, { y: 0.305, intensity: 0.5 });
  m.s.cyl(0.13, 0.16, 0.72, 8, P.stoneWarm, { y: 0.3 });
  m.s.cyl(0.36, 0.18, 0.14, 12, P.stoneCream, { y: 0.96 });
  m.g.cyl(0.3, 0.3, 0.01, 12, P.waterLight, { y: 1.1, intensity: 0.6 });
  for (const [x, y] of [[0, 1.26], [-0.07, 1.2], [0.07, 1.2], [0, 1.14]]) m.s.sphere(0.06, P.gold, { x, y }, 7, 5);
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2;
    m.s.box(0.02, 0.26, 0.02, '#CFE8EA', { x: Math.cos(a) * 0.3, y: 0.82, z: Math.sin(a) * 0.3, rx: Math.sin(a) * 0.9, rz: -Math.cos(a) * 0.9 });
  }
  return m;
}

// ─── fixed buildings from Chapter 1 ──────────────────────────────────────────
export function beacon(tier = 1) {
  const m = M();
  if (tier < 2) {
    m.s.box(1.9, 0.14, 1.9, P.stoneShade);
    m.s.box(1.45, 0.14, 1.45, P.stoneCream, { y: 0.14 });
    m.s.cyl(0.32, 0.42, 0.72, 8, P.stoneWarm, { y: 0.28 });
    m.s.cyl(0.58, 0.3, 0.3, 10, P.iron, { y: 0.98 });
    m.s.torus(0.58, 0.035, P.gold, { y: 1.28, rx: Math.PI / 2 }, 5, 16);
    m.flames.push({ x: 0, y: 1.2, z: 0, s: 1, main: true });
    m.lights.push({ x: 0, y: 1.6, z: 0, r: 5.5, main: true, strong: true });
  } else {
    m.s.box(1.95, 0.16, 1.95, P.stoneShade);
    m.s.box(1.6, 0.16, 1.6, P.stoneCream, { y: 0.16 });
    m.s.box(0.9, 1.2, 0.9, P.stoneWarm, { y: 0.32 });
    for (const sx of [-1, 1]) for (const sz of [-1, 1]) m.s.box(0.14, 1.24, 0.14, P.stoneShade, { x: sx * 0.45, z: sz * 0.45, y: 0.32 });
    m.s.box(1.1, 0.12, 1.1, P.stoneCream, { y: 1.52 });
    m.s.cyl(0.7, 0.36, 0.36, 12, P.iron, { y: 1.64 });
    m.s.torus(0.7, 0.04, P.gold, { y: 2.0, rx: Math.PI / 2 }, 5, 18);
    m.g.box(0.3, 0.4, 0.02, P.heartflame, { y: 0.7, z: 0.46, intensity: 2 });
    m.flames.push({ x: 0, y: 1.9, z: 0, s: 1.35, main: true });
    for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
      m.s.cyl(0.08, 0.1, 0.4, 6, P.iron, { x: sx * 0.82, z: sz * 0.82, y: 0.16 });
      m.flames.push({ x: sx * 0.82, y: 0.52, z: sz * 0.82, s: 0.3 });
    }
    m.lights.push({ x: 0, y: 2.3, z: 0, r: 8, main: true, strong: true });
  }
  return m;
}

export function throne() {
  const m = M();
  m.s.box(1.95, 0.16, 1.95, P.stoneShade);
  m.s.box(1.55, 0.16, 1.55, P.stoneCream, { y: 0.16 });
  m.s.box(1.1, 0.14, 1.0, P.stoneGrey, { y: 0.32 });
  m.s.box(0.82, 0.42, 0.6, '#9F968A', { y: 0.46 });
  m.s.box(0.86, 0.06, 0.64, P.stoneCream, { y: 0.86 });
  m.s.box(0.82, 0.95, 0.18, '#9F968A', { y: 0.88, z: -0.3 });
  m.s.box(0.4, 0.3, 0.18, '#9F968A', { x: -0.2, y: 1.83, z: -0.3, rz: 0.12 });
  m.s.box(0.3, 0.22, 0.2, '#958B7F', { x: 0.55, y: 0.32, z: 0.62, rz: 0.5, ry: 0.4 });
  for (const sx of [-0.47, 0.47]) m.s.box(0.12, 0.3, 0.6, '#958B7F', { x: sx, y: 0.88 });
  m.s.box(0.26, 0.26, 0.06, P.gold, { y: 1.45, z: -0.2, rz: Math.PI / 4 });
  for (const [x, z, h] of [[-0.8, -0.8, 1.2], [0.8, -0.8, 0.7]]) {
    m.s.cyl(0.14, 0.16, h, 8, P.stoneCream, { x, z, y: 0.16 });
    m.s.box(0.36, 0.1, 0.36, P.stoneShade, { x, z, y: 0.16 });
  }
  const R = hashRand(3);
  for (let i = 0; i < 7; i++) m.s.ico(0.12 + R() * 0.08, i % 2 ? '#7C9A5A' : '#6E8F52', { x: (R() - 0.5) * 1.6, y: 0.3, z: (R() - 0.5) * 1.6, sy: 0.35 }, 0);
  return m;
}

export function lodge() {
  const m = M();
  m.s.box(2.85, 0.24, 2.4, P.stoneShade, { z: -0.2 });
  timberWalls(m, 2.3, 1.2, 1.9, { y: 0.24 });
  m.s.roof(2.9, 2.6, 1.15, P.terracotta, { y: 1.44, z: -0.05 });
  chimney(m, -0.6, -0.5, 2.15, { w: 0.3 });
  // big double door and windows
  m.s.box(0.7, 0.85, 0.05, P.woodDark, { y: 0.24, z: 0.96 });
  m.s.box(0.03, 0.85, 0.06, '#2E2218', { y: 0.24, z: 0.99 });
  windowAt(m, 0.8, 0.75, 0.96);
  windowAt(m, -0.8, 0.75, 0.96);
  // workshop lean-to with a sawhorse and a log pile
  m.s.box(0.08, 1.0, 0.08, P.woodDark, { x: 1.35, z: 1.2 });
  m.s.box(0.08, 1.0, 0.08, P.woodDark, { x: 1.35, z: 0.1 });
  m.s.box(0.5, 0.05, 1.3, P.terracottaShade, { x: 1.28, y: 1.02, z: 0.65, rz: -0.35 });
  m.s.box(0.7, 0.06, 0.12, P.wood, { x: 0.55, y: 0.45, z: 1.28 });
  for (const x of [0.3, 0.8]) m.s.box(0.05, 0.45, 0.2, P.woodDark, { x, z: 1.28 });
  for (let i = 0; i < 5; i++) m.s.cyl(0.1, 0.1, 0.8, 7, i % 2 ? P.wood : P.woodLight, { x: -1.0 + (i % 3) * 0.2, y: 0.1 + Math.floor(i / 3) * 0.18, z: 1.2, rz: Math.PI / 2, ry: Math.PI / 2 });
  // hammer sign
  m.s.box(0.44, 0.3, 0.04, P.wood, { x: -0.62, y: 1.25, z: 1.0 });
  m.s.box(0.22, 0.06, 0.02, P.gold, { x: -0.62, y: 1.38, z: 1.03 });
  m.s.box(0.05, 0.18, 0.02, P.gold, { x: -0.62, y: 1.23, z: 1.03 });
  lantern(m, 0.44, 0.95, 1.05, 2);
  return m;
}

export function herbalist() {
  const m = M();
  m.s.box(2.9, 0.2, 1.3, P.stoneShade, { z: -0.35 });
  timberWalls(m, 2.6, 1.0, 1.1, { y: 0.2, z: -0.35, wall: '#EFE3C6' });
  m.s.roof(3.0, 1.6, 0.9, '#6E8F5A', { y: 1.2, z: -0.35 });
  for (let i = 0; i < 6; i++) m.s.ico(0.14, '#7FA36A', { x: -1.2 + i * 0.48, y: 1.55, z: -0.35 + (i % 2 ? 0.3 : -0.3), sy: 0.5 }, 0);
  door(m, 1.0, 0.21, { w: 0.34, h: 0.6 });
  windowAt(m, -0.9, 0.62, 0.21);
  windowAt(m, 0.15, 0.62, 0.21);
  // counter with jars under a green awning
  m.s.box(2.2, 0.5, 0.36, P.wood, { z: 0.62 });
  m.s.box(2.3, 0.05, 0.44, P.woodDark, { z: 0.62, y: 0.5 });
  for (let i = 0; i < 7; i++) {
    const c = ['#9E8AC8', '#7FC4A0', '#E8A0C0', '#C9E07A', '#7FB2C4', '#9E8AC8', '#E8C35A'][i];
    m.s.cyl(0.05, 0.055, 0.16, 7, '#E9EEF0', { x: -0.95 + i * 0.3, y: 0.55, z: 0.6 });
    m.g.cyl(0.045, 0.05, 0.09, 7, c, { x: -0.95 + i * 0.3, y: 0.56, z: 0.6, intensity: 1.2 });
  }
  const stripes = 9;
  for (let i = 0; i < stripes; i++) {
    const x = -1.2 + (2.4 / stripes) * (i + 0.5);
    m.s.box(2.4 / stripes + 0.005, 0.035, 0.75, i % 2 ? P.canvas : '#6E8F5A', { x, y: 1.2, z: 0.62, rx: 0.32 });
  }
  for (const x of [-1.12, 1.12]) m.s.box(0.06, 1.2, 0.06, P.woodDark, { x, z: 0.92 });
  for (let i = 0; i < 5; i++) m.s.ico(0.08, i % 2 ? '#6F9B55' : '#8DB266', { x: -0.8 + i * 0.4, y: 1.0, z: 0.8, sy: 1.6 }, 0);
  for (const [x, z] of [[-1.35, 0.9], [1.35, 0.9]]) {
    m.s.cyl(0.13, 0.1, 0.22, 7, P.terracotta, { x, z });
    m.s.ico(0.16, '#6F9B55', { x, z, y: 0.32 }, 0);
  }
  lantern(m, -1.05, 0.95, 0.95, 2);
  return m;
}

export const BUILDERS = {
  lamp, string: stringLights, stall, field_turnip: fieldTurnip, field_wheat: fieldWheat, fishery, cookhouse,
  tent, hut, flowers, tree, bench, banner, hedge, crates, well, fountain, beacon, throne, lodge, herbalist,
  herbalistStall: herbalist,
};

// The key that picks a model for an object: type, variant, and anything else that changes its look.
export function modelKey(o, game) {
  if (o.type === 'beacon') return `beacon:${game.beaconTier}`;
  if (o.type === 'stall') return `stall:${o.variant}:${o.goods}`;
  return `${o.type}:${o.variant || 0}`;
}

export function buildModel(key) {
  const [type, a, b] = key.split(':');
  const fn = BUILDERS[type];
  if (type === 'beacon') return fn(Number(a));
  if (type === 'stall') return fn(Number(a), b);
  return fn(Number(a) || 0);
}

export { GOODS_COLORS };
