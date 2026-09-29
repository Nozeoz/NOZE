// A simple player used by the tests (and by "Watch a night" in the page).
// Each morning it lights the road, builds what the market lacks, adds homes and decor,
// then opens the Lantern Market at dusk and collects tips while the night plays out.
import { TYPES, MARKET_GOODS } from './catalog.js';
import { W, H, idx, N4, N8, inBounds, T } from './world.js';
import { LIT } from './game.js';

const ROTS = [0, 1, 2, 3];

function allAnchors(g, type, filter = () => true) {
  const out = [];
  for (let z = 0; z < H; z++) {
    for (let x = 0; x < W; x++) {
      for (const rot of TYPES[type].w === TYPES[type].d ? [0] : ROTS) {
        if (!filter(x, z, rot)) continue;
        if (g.canPlace(type, x, z, rot).ok) out.push({ x, z, rot });
      }
    }
  }
  return out;
}

function tilesOf(g, type, x, z, rot) {
  const { w, d } = g.size(type, rot);
  return g.tiles(x, z, w, d);
}

function nearPath(g, tiles) {
  return tiles.some(([x, z]) => N8.some(([dx, dz]) => g.isPath(x + dx, z + dz)));
}

// Street tiles, where stalls and decor should go: walkable, in the realm, reachable.
function streetScore(g, x, z) {
  return Math.hypot(x + 0.5 - 22, z + 0.5 - 20);
}

export function placeLamps(g, target = 0.92, budget = Infinity) {
  let spent = 0;
  for (let n = 0; n < 12 && g.routeLitFraction() < target && g.gold >= 15 && spent + 15 <= budget; n++) {
    const L = g.staticLight();
    const dark = g.route().filter(([x, z]) => L[idx(x, z)] < LIT);
    if (!dark.length) break;
    let best = null;
    const seen = new Set();
    for (const [x, z] of dark) {
      for (const [dx, dz] of N8) {
        const lx = x + dx;
        const lz = z + dz;
        const key = lx * 100 + lz;
        if (seen.has(key) || !g.canPlace('lamp', lx, lz).ok) continue;
        seen.add(key);
        const covered = dark.filter(([a, b]) => Math.hypot(a - lx, b - lz) < 3.2 - 0.7).length;
        if (!best || covered > best.covered) best = { x: lx, z: lz, covered };
      }
    }
    if (!best) break;
    if (!g.place('lamp', best.x, best.z)) break;
    spent += 15;
  }
}

function placeStall(g, goods) {
  if (g.gold < TYPES.stall.cost) return null;
  let best = null;
  for (const a of allAnchors(g, 'stall')) {
    const probe = { ...a, ...g.size('stall', a.rot), rot: a.rot };
    const front = g.frontTiles(probe).find(([x, z]) => g.visitorWalkable(x, z) && g.reachable(x, z));
    if (!front) continue;
    const score = streetScore(g, front[0], front[1]);
    if (!best || score < best.score) best = { ...a, score };
  }
  if (!best) return null;
  const s = g.place('stall', best.x, best.z, best.rot, MARKET_GOODS.indexOf(goods) % 4);
  if (s) g.setStallGoods(s.id, goods);
  return s;
}

function placeAwayFromPaths(g, type) {
  if (g.gold < TYPES[type].cost) return null;
  let best = null;
  for (const a of allAnchors(g, type)) {
    const tiles = tilesOf(g, type, a.x, a.z, a.rot);
    if (nearPath(g, tiles) && type !== 'fishery') continue;
    const c = { x: a.x + g.size(type, a.rot).w / 2, z: a.z + g.size(type, a.rot).d / 2 };
    const score = Math.hypot(c.x - 22, c.z - 21);
    if (!best || score < best.score) best = { ...a, score };
  }
  return best ? g.place(type, best.x, best.z, best.rot) : null;
}

const DECOR_ORDER = ['flowers', 'bench', 'banner', 'tree', 'hedge', 'crates', 'flowers', 'tree', 'well', 'flowers', 'banner'];

function placeDecor(g, reserve, limit = 10) {
  let placed = 0;
  let turn = g.day * 3;
  for (let tries = 0; tries < 40 && placed < limit; tries++) {
    if (g.appeal().total >= 96) break;
    let type = DECOR_ORDER[turn++ % DECOR_ORDER.length];
    if (g.isUnlocked('fountain') && !g.count('fountain') && g.gold >= 120 + reserve) type = 'fountain';
    if (!g.isUnlocked(type) || g.gold < TYPES[type].cost + reserve) continue;
    const D = g.decorMap();
    let best = null;
    for (const a of allAnchors(g, type)) {
      const tiles = tilesOf(g, type, a.x, a.z, a.rot);
      if (!nearPath(g, tiles) || !tiles.every(([x, z]) => g.inRealm(x, z))) continue;
      // Leave the fronts of stalls clear and prefer the least decorated stretch of street.
      const [x, z] = tiles[0];
      const around = N4.map(([dx, dz]) => (inBounds(x + dx, z + dz) && g.isPath(x + dx, z + dz) ? D[idx(x + dx, z + dz)] : 0));
      const score = Math.min(...around) + streetScore(g, x, z) * 0.15;
      if (!best || score < best.score) best = { ...a, score };
    }
    if (!best) continue;
    if (g.place(type, best.x, best.z, best.rot, g.rng.int(0, 3))) placed++;
  }
}

export function planMorning(g) {
  // 1. Light the way in.
  placeLamps(g, 0.92);
  // 2. Fish, and a stall for each kind of goods we make.
  if (!g.count('fishery')) placeAwayFromPaths(g, 'fishery');
  const makes = new Set(['harvest']);
  if (g.count('fishery')) makes.add('catch');
  if (g.count('field_wheat')) makes.add('grain');
  if (g.count('cookhouse')) makes.add('stew');
  for (const goods of makes) if (!g.sellers(goods).length) placeStall(g, goods);
  // 3. Beds for the people who want to stay.
  if (g.freeBeds() < 2 && g.gold >= TYPES.hut.cost + 10) placeAwayFromPaths(g, 'hut');
  // 4. Work for idle hands.
  const idle = g.settlers().filter(s => !s.job).length;
  if (idle > 0) {
    if (g.isUnlocked('cookhouse') && !g.count('cookhouse')) placeAwayFromPaths(g, 'cookhouse');
    else if (g.isUnlocked('field_wheat') && !g.count('field_wheat')) placeAwayFromPaths(g, 'field_wheat');
    else if (g.count('fishery') < 2 && g.stock.catch < 6) placeAwayFromPaths(g, 'fishery');
    else if (g.stock.harvest < 12) placeAwayFromPaths(g, 'field_turnip');
  }
  // 5. The Heartflame, once there are enough people to fill a wider realm.
  if (g.beaconTier < 2 && g.residents.length >= 7 && g.gold >= 260) g.upgradeBeacon();
  // 6. A second stall for busy goods, then stall upgrades.
  if (g.visitorsExpected() >= 10 && g.sellers('harvest').length < 2) placeStall(g, 'harvest');
  for (const s of g.stalls()) if (!TYPES[s.type].goods && s.level < 3 && g.gold >= 240) g.upgradeStall(s.id);
  // 7. Make it lovely with what's left.
  const reserve = g.beaconTier < 2 && g.residents.length >= 6 ? 200 : 40;
  placeDecor(g, reserve);
  placeLamps(g, 0.95);
}

// Plays one full day and night. Returns the Night Ledger.
export function playDay(g, { collectTips = true, dt = 0.1 } = {}) {
  planMorning(g);
  g.skipToDusk();
  g.openMarket();
  const oldSpeed = g.speed;
  g.speed = 4;
  let guard = 0;
  while (!g.ledger && guard++ < 20000) {
    g.update(dt);
    if (collectTips) for (const t of [...g.tips]) g.collectTip(t.id);
  }
  g.speed = oldSpeed;
  const ledger = g.ledger;
  g.sleep();
  return ledger;
}

export function autoplay(g, { maxDays = 20, until = x => x.rank >= 2, onDay } = {}) {
  const ledgers = [];
  while (g.day <= maxDays && !until(g)) {
    const l = playDay(g);
    ledgers.push(l);
    if (onDay) onDay(g, l);
  }
  return ledgers;
}

export { T };
