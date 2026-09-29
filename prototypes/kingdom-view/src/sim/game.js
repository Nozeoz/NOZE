// The Kingdom View simulation: map, building rules, time, production, the Lantern Market,
// visitors, light and the Veil, appeal, residents, tasks, and saves.
// It knows nothing about rendering; the renderer and the UI read its state and drain `events`.
import { W, H, T, BEACON, ENTRANCE, ROAD, REALM_RADIUS, idx, inBounds, makeTerrain, N4, N8 } from './world.js';
import {
  TYPES, GOODS, MARKET_GOODS, STALL_LEVELS, BEACON_TIERS, TASKS, PAGES, NAMES, VISITOR_KINDS, LINES,
} from './catalog.js';
import { makeRng } from './rng.js';

export const MIN_PER_SEC = 6; // game minutes per game second: an hour passes in 10 s at 1×
export const DAY_START = 6 * 60;
export const DUSK = 17 * 60;
export const NIGHT = 19 * 60;
export const MARKET_LAST_OPEN = 24 * 60;
export const CLOSE = 27 * 60; // 03:00 the next morning
export const LIT = 0.18; // a tile counts as lit at this light level
export const VILLAGE_RESIDENTS = 12;
const FRONT = [[0, 1], [1, 0], [0, -1], [-1, 0]];
const SPAWN_WINDOW = 240; // visitors arrive during the first 4 game hours after opening
const QUEUE_GAP = 0.42;

const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
export const fmtClock = minute => {
  const m = ((Math.floor(minute) % 1440) + 1440) % 1440;
  return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
};

export class Game {
  constructor({ seed = 1, empty = false } = {}) {
    this.seed = seed;
    this.rng = makeRng(seed);
    this.terrain = makeTerrain();
    this.surface = new Uint8Array(W * H); // 1 = stone path
    this.occ = new Int32Array(W * H);
    this.objects = new Map();
    this.nextId = 1;
    this.version = 0; // bumps whenever the map changes
    this.day = 1;
    this.minute = 8 * 60;
    this.speed = 1;
    this.gold = 150;
    this.stock = { harvest: 10, grain: 0, catch: 0, stew: 0, tonic: 6 };
    this.beaconTier = 1;
    this.rank = 1;
    this.residents = [];
    this.market = { open: false, openedDay: 0, spawns: [], closing: false };
    this.night = null; // tonight's ledger in progress
    this.ledger = null; // finished ledger waiting for the player
    this.visitors = [];
    this.tips = [];
    this.settleRequests = [];
    this.tasksDone = new Set();
    this.pages = ['ember'];
    this.stats = { nightsOpened: 0, settled: 0, soldTotal: zeroGoods(), bestNightSold: zeroGoods(), bestNightHappy: 0, visitors: 0, earned: 0 };
    this.player = { x: 20.5, z: 18.5, fx: 0, fz: 1, path: [], moving: false };
    this.tended = {}; // object id → day it was last tended
    this.events = [];
    this.clockSec = 0; // game seconds elapsed, for bubbles and animation timing
    this._cache = {};
    this._vid = 1;
    this.usedNames = new Set();
    if (!empty) this.layOutHamlet();
  }

  // ─── map helpers ───────────────────────────────────────────────────────────
  size(type, rot = 0) {
    const def = TYPES[type];
    return rot % 2 ? { w: def.d, d: def.w } : { w: def.w, d: def.d };
  }

  tiles(x, z, w, d) {
    const out = [];
    for (let dz = 0; dz < d; dz++) for (let dx = 0; dx < w; dx++) out.push([x + dx, z + dz]);
    return out;
  }

  objTiles(o) { return this.tiles(o.x, o.z, o.w, o.d); }
  objCentre(o) { return { x: o.x + o.w / 2, z: o.z + o.d / 2 }; }
  objectAt(x, z) { return inBounds(x, z) ? this.objects.get(this.occ[idx(x, z)]) || null : null; }
  realmRadius() { return REALM_RADIUS[this.beaconTier]; }
  inRealm(x, z) { return Math.hypot(x + 0.5 - BEACON.x, z + 0.5 - BEACON.z) <= this.realmRadius(); }
  isPath(x, z) { return inBounds(x, z) && (this.surface[idx(x, z)] === 1 || this.terrain[idx(x, z)] === T.ROAD); }

  visitorWalkable(x, z) {
    if (!this.isPath(x, z)) return false;
    const o = this.objectAt(x, z);
    return !o || !!TYPES[o.type].walkable;
  }

  playerWalkable(x, z) {
    if (!inBounds(x, z)) return false;
    const t = this.terrain[idx(x, z)];
    if (t === T.FOREST || t === T.WATER) return false;
    const o = this.objectAt(x, z);
    return !o || !!TYPES[o.type].walkable || !!TYPES[o.type].playerWalkable;
  }

  frontTiles(o) {
    const [fx, fz] = FRONT[o.rot];
    const out = [];
    if (fz === 1) for (let i = 0; i < o.w; i++) out.push([o.x + i, o.z + o.d]);
    if (fz === -1) for (let i = 0; i < o.w; i++) out.push([o.x + i, o.z - 1]);
    if (fx === 1) for (let j = 0; j < o.d; j++) out.push([o.x + o.w, o.z + j]);
    if (fx === -1) for (let j = 0; j < o.d; j++) out.push([o.x - 1, o.z + j]);
    return out;
  }

  neighbourTiles(o) {
    const out = [];
    for (let x = o.x - 1; x <= o.x + o.w; x++) {
      for (let z = o.z - 1; z <= o.z + o.d; z++) {
        const inside = x >= o.x && x < o.x + o.w && z >= o.z && z < o.z + o.d;
        const corner = (x === o.x - 1 || x === o.x + o.w) && (z === o.z - 1 || z === o.z + o.d);
        if (!inside && !corner) out.push([x, z]);
      }
    }
    return out;
  }

  // ─── building rules ────────────────────────────────────────────────────────
  isUnlocked(type) {
    const def = TYPES[type];
    return !!def && !def.fixed && (!def.unlock || this.tasksDone.has(def.unlock));
  }

  canPlace(type, x, z, rot = 0, ignoreId = 0) {
    const def = TYPES[type];
    if (!def) return { ok: false, reason: 'Unknown building.' };
    if (def.surface) return this.canPaintPath(x, z);
    const { w, d } = this.size(type, rot);
    const tiles = this.tiles(x, z, w, d);
    for (const [tx, tz] of tiles) {
      if (!inBounds(tx, tz)) return { ok: false, reason: 'That runs off the edge of the map.' };
      const t = this.terrain[idx(tx, tz)];
      if (t === T.FOREST) return { ok: false, reason: 'The forest is too thick here.' };
      if (t === T.WATER) return { ok: false, reason: 'That’s the pond.' };
      const occupant = this.occ[idx(tx, tz)];
      if (occupant && occupant !== ignoreId) return { ok: false, reason: 'Something is already here.' };
      if (!def.walkable && this.isPath(tx, tz)) return { ok: false, reason: 'Keep the paths clear.' };
    }
    if (def.reach) {
      const reachable = tiles.every(([tx, tz]) => this.inRealm(tx, tz) || N8.some(([dx, dz]) => this.isPath(tx + dx, tz + dz)));
      if (!reachable) return { ok: false, reason: 'Lights go inside the realm or right beside a road.' };
    } else if (!tiles.every(([tx, tz]) => this.inRealm(tx, tz))) {
      return { ok: false, reason: 'Outside the realm. Raise the Heartflame to build farther out.' };
    }
    if (def.needs === 'water') {
      const wet = tiles.some(([tx, tz]) => N4.some(([dx, dz]) => inBounds(tx + dx, tz + dz) && this.terrain[idx(tx + dx, tz + dz)] === T.WATER));
      if (!wet) return { ok: false, reason: 'A Fishing Hut has to touch the pond.' };
    }
    return { ok: true };
  }

  canPaintPath(x, z) {
    if (!inBounds(x, z)) return { ok: false, reason: 'Off the map.' };
    const i = idx(x, z);
    if (this.terrain[i] !== T.GRASS) return { ok: false, reason: this.terrain[i] === T.ROAD ? 'The Old Road is already here.' : 'You can’t pave that.' };
    if (this.surface[i]) return { ok: false, reason: 'Already a path.' };
    const o = this.objectAt(x, z);
    if (o && !TYPES[o.type].walkable) return { ok: false, reason: 'Something is in the way.' };
    if (!this.inRealm(x, z) && !N4.some(([dx, dz]) => this.isPath(x + dx, z + dz))) return { ok: false, reason: 'Paths start inside the realm or from another path.' };
    return { ok: true };
  }

  // Places an object. `free` skips the cost (starting layout, moves).
  place(type, x, z, rot = 0, variant = 0, { free = false, fixed = false } = {}) {
    const def = TYPES[type];
    if (def.surface) return this.paintPath(x, z, { free }) ? { type: 'path', x, z } : null;
    if (!fixed) {
      if (!this.isUnlocked(type)) return this.fail('Not unlocked yet.');
      const check = this.canPlace(type, x, z, rot);
      if (!check.ok) return this.fail(check.reason);
      if (!free && this.gold < def.cost) return this.fail(`You need ${def.cost} gold.`);
    }
    if (!free && !fixed) this.gold -= def.cost;
    const { w, d } = this.size(type, rot);
    const o = { id: this.nextId++, type, x, z, rot, w, d, variant: Math.min(variant, (def.variants || 1) - 1), placedDay: this.day };
    if (def.stall) Object.assign(o, { goods: def.goods || 'harvest', level: 1, queue: [], progress: 0, sold: 0 });
    if (def.worker) o.worker = null;
    for (const [tx, tz] of this.objTiles(o)) this.occ[idx(tx, tz)] = o.id;
    this.objects.set(o.id, o);
    this.changed();
    return o;
  }

  paintPath(x, z, { free = false } = {}) {
    const check = this.canPaintPath(x, z);
    if (!check.ok) return this.fail(check.reason);
    if (!free && this.gold < TYPES.path.cost) return this.fail('You need 2 gold.');
    if (!free) this.gold -= TYPES.path.cost;
    this.surface[idx(x, z)] = 1;
    this.changed();
    return true;
  }

  erasePath(x, z) {
    if (!inBounds(x, z) || !this.surface[idx(x, z)]) return false;
    this.surface[idx(x, z)] = 0;
    this.gold += 1;
    this.changed();
    return true;
  }

  remove(id) {
    const o = this.objects.get(id);
    if (!o) return false;
    const def = TYPES[o.type];
    if (def.fixed) return this.fail('That belongs to the realm. It stays.');
    if (def.beds && this.beds() - def.beds < this.settlers().length) return this.fail('Someone sleeps here. Build another home first.');
    for (const [tx, tz] of this.objTiles(o)) this.occ[idx(tx, tz)] = 0;
    this.objects.delete(id);
    this.gold += Math.floor(def.cost / 2) + (o.level > 1 ? Math.floor(STALL_LEVELS[o.level].cost / 2) : 0);
    this.changed();
    return true;
  }

  move(id, x, z, rot) {
    const o = this.objects.get(id);
    if (!o || TYPES[o.type].fixed) return this.fail('That can’t be moved.');
    const check = this.canPlace(o.type, x, z, rot, id);
    if (!check.ok) return this.fail(check.reason);
    for (const [tx, tz] of this.objTiles(o)) this.occ[idx(tx, tz)] = 0;
    const { w, d } = this.size(o.type, rot);
    Object.assign(o, { x, z, rot, w, d });
    for (const [tx, tz] of this.objTiles(o)) this.occ[idx(tx, tz)] = o.id;
    this.changed();
    return true;
  }

  setVariant(id, variant) {
    const o = this.objects.get(id);
    if (!o) return false;
    o.variant = ((variant % (TYPES[o.type].variants || 1)) + (TYPES[o.type].variants || 1)) % (TYPES[o.type].variants || 1);
    this.changed();
    return true;
  }

  setStallGoods(id, goods) {
    const o = this.objects.get(id);
    if (!o || !TYPES[o.type].stall || TYPES[o.type].goods || !MARKET_GOODS.includes(goods)) return false;
    o.goods = goods;
    this.changed(false);
    return true;
  }

  upgradeStall(id) {
    const o = this.objects.get(id);
    if (!o || !TYPES[o.type].stall || o.level >= 3) return false;
    const cost = STALL_LEVELS[o.level + 1].cost;
    if (this.gold < cost) return this.fail(`You need ${cost} gold.`);
    this.gold -= cost;
    o.level++;
    this.emit({ type: 'upgrade', id: o.id });
    this.changed(false);
    return true;
  }

  upgradeBeacon() {
    const next = BEACON_TIERS[this.beaconTier + 1];
    if (!next) return false;
    if (this.gold < next.cost) return this.fail(`You need ${next.cost} gold.`);
    this.gold -= next.cost;
    this.beaconTier++;
    this.emit({ type: 'beacon', tier: this.beaconTier });
    this.toast(`The ${next.name} roars. The realm grows.`, 'good');
    this.changed();
    this.checkProgress();
    return true;
  }

  fail(reason) {
    this.lastError = reason;
    return null;
  }

  changed(mapChanged = true) {
    if (mapChanged) this.version++;
    this._cache = {};
    this.assignJobs();
  }

  count(type) { let n = 0; for (const o of this.objects.values()) if (o.type === type) n++; return n; }
  list(pred) { return [...this.objects.values()].filter(pred); }

  // ─── the starting hamlet (the end of Chapter 1's Founding) ─────────────────
  layOutHamlet() {
    const put = (type, x, z, rot = 0, variant = 0) => this.place(type, x, z, rot, variant, { fixed: true, free: true });
    put('throne', 21, 10);
    put('beacon', 21, 13);
    put('lodge', 13, 13, 1);
    put('herbalist', 26, 13);
    for (let x = 16; x <= 28; x++) for (const z of [15, 16]) this.surface[idx(x, z)] = 1;
    for (let z = 17; z <= 32; z++) for (const x of [21, 22]) this.surface[idx(x, z)] = 1;
    put('stall', 23, 19, 3, 0);
    put('field_turnip', 17, 19);
    put('tent', 17, 23);
    put('tent', 24, 23);
    put('lamp', 20, 21);
    put('lamp', 23, 26);
    for (const [x, z, v] of [[20, 10, 0], [23, 10, 1], [20, 11, 2], [23, 11, 3]]) put('flowers', x, z, 0, v);
    put('bench', 19, 17);
    put('bench', 25, 17);
    put('banner', 20, 17, 0, 0);
    put('banner', 23, 17, 0, 0);
    this.residents = [
      { name: 'Bram', sworn: true },
      { name: 'Linnea', sworn: true },
      { name: 'Hob', sworn: false, since: 0 },
      { name: 'Ada', sworn: false, since: 0 },
    ];
    this.usedNames = new Set(['Bram', 'Linnea', 'Hob', 'Ada']);
    this.changed();
  }

  // ─── residents and work ────────────────────────────────────────────────────
  settlers() { return this.residents.filter(r => !r.sworn); }
  beds() { let n = 0; for (const o of this.objects.values()) n += TYPES[o.type].beds || 0; return n; }
  freeBeds() { return Math.max(0, this.beds() - this.settlers().length); }

  assignJobs() {
    const workplaces = this.list(o => TYPES[o.type].worker).sort((a, b) => a.id - b.id);
    const settlers = this.settlers();
    workplaces.forEach((o, i) => { o.worker = settlers[i] ? settlers[i].name : null; });
    for (const s of settlers) s.job = workplaces.find(o => o.worker === s.name)?.id || null;
  }

  // ─── light and the Veil ────────────────────────────────────────────────────
  lightSources({ dynamic = true } = {}) {
    const out = [];
    for (const o of this.objects.values()) {
      const def = TYPES[o.type];
      if (o.type === 'beacon') {
        out.push({ x: o.x + 1, z: o.z + 1, r: BEACON_TIERS[this.beaconTier].light, kind: 'beacon' });
      } else if (def.lights) {
        for (const [lx, lz, r] of def.lights) {
          const p = this.rotLocal(o, lx, lz);
          out.push({ x: p.x, z: p.z, r, kind: o.type });
        }
      } else if (def.light) {
        const c = this.objCentre(o);
        out.push({ x: c.x, z: c.z, r: def.light, kind: o.type });
      }
    }
    if (dynamic) {
      out.push({ x: this.player.x, z: this.player.z, r: 2.4, kind: 'flicker' });
      for (const v of this.visitors) if (VISITOR_KINDS[v.kind].lantern) out.push({ x: v.x, z: v.z, r: VISITOR_KINDS[v.kind].lantern, kind: 'lantern' });
    }
    return out;
  }

  // Centre of local tile (lx, lz) of an object's unrotated footprint, in world tile units.
  rotLocal(o, lx, lz) {
    const def = TYPES[o.type];
    const cx = lx + 0.5 - def.w / 2;
    const cz = lz + 0.5 - def.d / 2;
    const [c, s] = [[1, 0], [0, 1], [-1, 0], [0, -1]][o.rot];
    // rotation.y = rot·90°: local +z turns toward +x
    const rx = cx * c + cz * s;
    const rz = -cx * s + cz * c;
    const centre = this.objCentre(o);
    return { x: centre.x + rx, z: centre.z + rz };
  }

  staticLight() {
    if (this._cache.light) return this._cache.light;
    const L = new Float32Array(W * H);
    for (const s of this.lightSources({ dynamic: false })) addLight(L, s);
    this._cache.light = L;
    return L;
  }

  lightAt(x, z) {
    let l = this.staticLight()[idx(x, z)] || 0;
    const cx = x + 0.5;
    const cz = z + 0.5;
    const dyn = [[this.player.x, this.player.z, 2.4]];
    for (const v of this.visitors) if (VISITOR_KINDS[v.kind].lantern) dyn.push([v.x, v.z, VISITOR_KINDS[v.kind].lantern]);
    for (const [sx, sz, r] of dyn) l = Math.max(l, 1 - Math.hypot(cx - sx, cz - sz) / r);
    return l;
  }

  nightFactor(minute = this.minute) {
    const m = ((minute % 1440) + 1440) % 1440;
    if (m >= 7 * 60 && m < DUSK) return 0;
    if (m >= DUSK && m < NIGHT) return (m - DUSK) / (NIGHT - DUSK);
    if (m >= NIGHT || m < 4.5 * 60) return 1;
    if (m < 6.5 * 60) return 1 - (m - 4.5 * 60) / 120;
    return 0;
  }

  // The walk from the forest edge to the Heartflame, and how much of it is lit at night.
  route() {
    if (this._cache.route) return this._cache.route;
    const target = this.plazaTile();
    this._cache.route = this.findPath([ENTRANCE.x, ENTRANCE.z], target, (x, z) => this.visitorWalkable(x, z)) || [];
    return this._cache.route;
  }

  routeLitFraction() {
    const route = this.route();
    if (!route.length) return 0;
    const L = this.staticLight();
    return route.filter(([x, z]) => L[idx(x, z)] >= LIT).length / route.length;
  }

  plazaTile() { return [21, 16]; }

  // ─── appeal ────────────────────────────────────────────────────────────────
  decorMap() {
    if (this._cache.decor) return this._cache.decor;
    const D = new Float32Array(W * H);
    for (const o of this.objects.values()) {
      const ap = TYPES[o.type].appeal;
      if (!ap) continue;
      const [a, r] = ap;
      const c = this.objCentre(o);
      for (let z = Math.floor(c.z - r - 1); z <= c.z + r + 1; z++) {
        for (let x = Math.floor(c.x - r - 1); x <= c.x + r + 1; x++) {
          if (!inBounds(x, z)) continue;
          const f = 1 - Math.hypot(x + 0.5 - c.x, z + 0.5 - c.z) / r;
          if (f > 0) D[idx(x, z)] = Math.min(10, D[idx(x, z)] + a * f);
        }
      }
    }
    this._cache.decor = D;
    return D;
  }

  appeal() {
    if (this._cache.appeal) return this._cache.appeal;
    const D = this.decorMap();
    const L = this.staticLight();
    let decorSum = 0;
    let decorN = 0;
    let lit = 0;
    let walk = 0;
    for (let z = 0; z < H; z++) {
      for (let x = 0; x < W; x++) {
        if (!this.visitorWalkable(x, z)) continue;
        walk++;
        if (L[idx(x, z)] >= LIT) lit++;
        if (this.inRealm(x, z)) { decorSum += D[idx(x, z)]; decorN++; }
      }
    }
    const types = new Set(this.list(o => TYPES[o.type].appeal && !TYPES[o.type].fixed).map(o => o.type));
    const herbalist = this.list(o => o.type === 'herbalist')[0];
    const decor = decorN ? (decorSum / decorN) * 9 : 0;
    const variety = Math.min(8, types.size) * 2.5;
    const light = walk ? (lit / walk) * 25 : 0;
    const sworn = herbalist && this.serviceTile(herbalist) ? 5 : 0;
    const total = Math.round(clamp(decor + variety + light + sworn, 0, 100));
    this._cache.appeal = { total, decor: Math.round(decor), variety: Math.round(variety), light: Math.round(light), sworn };
    return this._cache.appeal;
  }

  visitorsExpected() {
    return Math.min(22, 3 + Math.floor(this.appeal().total / 7) + (this.rank - 1) * 2);
  }

  // ─── paths ─────────────────────────────────────────────────────────────────
  findPath(from, to, walkable, { diagonal = false } = {}) {
    const [sx, sz] = from;
    const [gx, gz] = to;
    if (!inBounds(sx, sz) || !inBounds(gx, gz)) return null;
    const prev = new Int32Array(W * H).fill(-1);
    const start = idx(sx, sz);
    const goal = idx(gx, gz);
    prev[start] = start;
    const queue = [start];
    const dirs = diagonal ? N8 : N4;
    for (let qi = 0; qi < queue.length; qi++) {
      const cur = queue[qi];
      if (cur === goal) break;
      const cx = cur % W;
      const cz = (cur - cx) / W;
      for (const [dx, dz] of dirs) {
        const nx = cx + dx;
        const nz = cz + dz;
        if (!inBounds(nx, nz)) continue;
        const ni = idx(nx, nz);
        if (prev[ni] !== -1) continue;
        if (ni !== goal && !walkable(nx, nz)) continue;
        if (dx && dz && (!walkable(cx + dx, cz) || !walkable(cx, cz + dz))) continue;
        prev[ni] = cur;
        queue.push(ni);
      }
    }
    if (prev[goal] === -1) return null;
    const path = [];
    for (let cur = goal; cur !== start; cur = prev[cur]) path.push([cur % W, Math.floor(cur / W)]);
    path.push([sx, sz]);
    return path.reverse();
  }

  distanceField(from, walkable) {
    const dist = new Int32Array(W * H).fill(-1);
    const start = idx(from[0], from[1]);
    dist[start] = 0;
    const queue = [start];
    for (let qi = 0; qi < queue.length; qi++) {
      const cur = queue[qi];
      const cx = cur % W;
      const cz = (cur - cx) / W;
      for (const [dx, dz] of N4) {
        const nx = cx + dx;
        const nz = cz + dz;
        if (!inBounds(nx, nz) || !walkable(nx, nz)) continue;
        const ni = idx(nx, nz);
        if (dist[ni] !== -1) continue;
        dist[ni] = dist[cur] + 1;
        queue.push(ni);
      }
    }
    return dist;
  }

  entranceDist() {
    if (!this._cache.entrance) this._cache.entrance = this.distanceField([ENTRANCE.x, ENTRANCE.z], (x, z) => this.visitorWalkable(x, z));
    return this._cache.entrance;
  }

  reachable(x, z) { return inBounds(x, z) && this.entranceDist()[idx(x, z)] >= 0; }

  // Where customers stand to buy from a stall, or null if no reachable path runs past its counter.
  serviceTile(o) {
    this._cache.service ||= {};
    if (o.id in this._cache.service) return this._cache.service[o.id];
    const tile = this.frontTiles(o).find(([x, z]) => this.visitorWalkable(x, z) && this.reachable(x, z)) || null;
    this._cache.service[o.id] = tile;
    return tile;
  }

  restTile(o) {
    this._cache.rest ||= {};
    if (o.id in this._cache.rest) return this._cache.rest[o.id];
    const tile = this.neighbourTiles(o).find(([x, z]) => this.visitorWalkable(x, z) && this.reachable(x, z)) || null;
    this._cache.rest[o.id] = tile;
    return tile;
  }

  stalls() { return this.list(o => TYPES[o.type].stall); }
  stockOf(goods) { return this.stock[goods] || 0; }
  sellers(goods) { return this.stalls().filter(s => s.goods === goods && this.serviceTile(s)); }

  // ─── time ──────────────────────────────────────────────────────────────────
  // dt is real seconds; the game speed scales it. Walking as the Sovereign uses real time.
  update(dt) {
    if (this.ledger) return;
    const g = dt * this.speed;
    if (g <= 0) return;
    const before = this.minute;
    this.minute += g * MIN_PER_SEC;
    this.clockSec += g;
    for (let h = Math.floor(before / 60) + 1; h <= Math.floor(this.minute / 60); h++) this.onHour(h);
    if (this.market.open) this.spawnDue();
    this.updateStalls(g);
    for (const v of this.visitors) this.updateVisitor(v, g);
    this.visitors = this.visitors.filter(v => v.state !== 'gone');
    if (this.market.open && this.minute >= CLOSE) this.closeMarket();
    if (this.market.closing) {
      if (!this.visitors.length) this.finishNight();
    } else if (!this.market.open && this.minute >= CLOSE) this.finishNight();
  }

  onHour(h) {
    const m = h * 60;
    if (m > DAY_START && m <= NIGHT) this.produce(h);
    this.checkProgress();
  }

  produce(hour) {
    for (const o of this.objects.values()) {
      const def = TYPES[o.type];
      if (def.worker && !o.worker) continue;
      if (def.produce) {
        for (const [goods, n] of Object.entries(def.produce)) this.addStock(goods, n, o);
      } else if (def.convert) {
        const ok = Object.entries(def.convert.in).every(([goods, n]) => this.stock[goods] >= n);
        if (ok) {
          for (const [goods, n] of Object.entries(def.convert.in)) this.stock[goods] -= n;
          for (const [goods, n] of Object.entries(def.convert.out)) this.addStock(goods, n, o);
        }
      }
    }
    if (hour % 2 === 0) this.addStock('tonic', 1, this.list(o => o.type === 'herbalist')[0]);
  }

  addStock(goods, n, o) {
    this.stock[goods] = (this.stock[goods] || 0) + n;
    if (o) this.emit({ type: 'produce', id: o.id, goods, n });
  }

  skipToDusk() {
    if (this.minute >= DUSK || this.ledger) return false;
    for (let h = Math.floor(this.minute / 60) + 1; h <= DUSK / 60; h++) this.onHour(h);
    this.minute = DUSK;
    return true;
  }

  canOpenMarket() {
    return !this.market.open && !this.market.closing && !this.ledger && this.minute >= DUSK && this.minute < MARKET_LAST_OPEN && this.market.openedDay !== this.day;
  }

  openMarket() {
    if (!this.canOpenMarket()) return false;
    this.market.open = true;
    this.market.openedDay = this.day;
    this.stats.nightsOpened++;
    this.night = {
      day: this.day, visitors: 0, happy: 0, content: 0, unhappy: 0, turnedBack: 0, sold: zeroGoods(), revenue: 0,
      tips: 0, tipsMissed: 0, none: zeroGoods(), soldOut: 0, asked: [], noBed: 0, appeal: this.appeal().total, bestStall: null,
    };
    const n = this.visitorsExpected();
    const start = Math.max(this.minute + 10, NIGHT - 30);
    const window = Math.min(SPAWN_WINDOW, CLOSE - 150 - start);
    this.market.spawns = [];
    for (let i = 0; i < n; i++) this.market.spawns.push(start + (window * (i + this.rng.range(0.05, 0.95))) / n);
    this.market.spawns.sort((a, b) => a - b);
    for (const s of this.stalls()) { s.queue = []; s.progress = 0; s.sold = 0; }
    this.emit({ type: 'market', open: true });
    this.checkProgress();
    return true;
  }

  closeMarket() {
    if (!this.market.open) return false;
    this.market.open = false;
    this.market.closing = true;
    this.market.spawns = [];
    for (const v of this.visitors) {
      if (v.state !== 'leave' && v.state !== 'flee' && v.state !== 'gone') this.finishVisit(v);
      v.speed = Math.max(v.speed, 2.4);
    }
    for (const s of this.stalls()) s.queue = [];
    this.emit({ type: 'market', open: false });
    return true;
  }

  finishNight() {
    if (this.ledger) return;
    this.market.closing = false;
    const night = this.night || { day: this.day, visitors: 0, closed: true, sold: zeroGoods(), none: zeroGoods(), asked: [], appeal: this.appeal().total };
    const missed = this.tips.reduce((sum, t) => sum + t.value, 0);
    night.tipsMissed = Math.floor(missed / 2);
    this.tips = [];
    this.gold += night.tipsMissed;
    const best = this.stalls().sort((a, b) => b.sold - a.sold)[0];
    night.bestStall = best && best.sold ? { id: best.id, goods: best.goods, sold: best.sold } : null;
    for (const g of Object.keys(this.stats.bestNightSold)) this.stats.bestNightSold[g] = Math.max(this.stats.bestNightSold[g], night.sold[g] || 0);
    this.stats.bestNightHappy = Math.max(this.stats.bestNightHappy, night.happy || 0);
    // Visitors who asked to stay move in, as long as there are beds.
    night.settled = [];
    for (const req of this.settleRequests) {
      if (this.freeBeds() <= 0) { night.noBed = (night.noBed || 0) + 1; continue; }
      this.residents.push({ name: req.name, sworn: false, since: this.day });
      this.usedNames.add(req.name);
      night.settled.push(req.name);
      this.stats.settled++;
    }
    this.settleRequests = [];
    this.assignJobs();
    this.ledger = night;
    this.night = null;
    this.checkProgress();
    this.emit({ type: 'ledger' });
  }

  // Close the market now, or, if it never opened tonight, let the night pass.
  endNight() {
    if (this.market.open) return this.closeMarket();
    if (this.market.closing || this.ledger || this.minute < DUSK) return false;
    this.minute = Math.max(this.minute, CLOSE);
    this.finishNight();
    return true;
  }

  // Called when the player closes the Night Ledger: sleep until dawn.
  sleep() {
    if (!this.ledger) return false;
    this.ledger = null;
    this.day++;
    this.minute = DAY_START;
    this.visitors = [];
    this.tended = {};
    this.checkProgress();
    this.emit({ type: 'dawn', day: this.day });
    return true;
  }

  // ─── visitors ──────────────────────────────────────────────────────────────
  spawnDue() {
    while (this.market.spawns.length && this.market.spawns[0] <= this.minute) {
      this.market.spawns.shift();
      this.spawnVisitor();
    }
  }

  spawnVisitor(kind) {
    const rng = this.rng;
    kind ||= rng.weighted(Object.entries(VISITOR_KINDS).map(([k, v]) => [k, v.weight]));
    const def = VISITOR_KINDS[kind];
    const nWants = rng.weighted([[1, 3], [2, 4], [3, 2]]);
    const pool = Object.entries(def.wants);
    const wants = [];
    for (let i = 0; i < nWants && wants.length < pool.length; i++) {
      const g = rng.weighted(pool.filter(([k]) => !wants.includes(k)));
      wants.push(g);
    }
    const free = NAMES.filter(n => !this.usedNames.has(n) && !this.visitors.some(v => v.name === n));
    const v = {
      id: this._vid++, kind, name: def.creature ? def.name : rng.pick(free.length ? free : NAMES),
      x: ENTRANCE.x + 0.5, z: ENTRANCE.z + 0.5, tx: ENTRANCE.x, tz: ENTRANCE.z,
      path: [], pi: 0, state: 'arrive', wants, complained: [], sat: 52, fear: 0, speed: rng.range(1.45, 1.75),
      timer: 0, bubble: null, stallId: 0, seed: rng.int(0, 1e6), warned: false, greeted: false, served: 0,
    };
    this.visitors.push(v);
    if (this.night) this.night.visitors++;
    this.stats.visitors++;
    this.planNext(v);
    return v;
  }

  say(v, text, secs = 3.2) {
    if (!text) return;
    v.bubble = { text, until: this.clockSec + secs };
  }

  sayPick(v, list, p = 1) {
    if (this.rng.chance(p)) this.say(v, this.rng.pick(list));
  }

  // Decide where to go next: a stall, a place to linger, or home.
  planNext(v) {
    const here = [v.tx, v.tz];
    const creature = VISITOR_KINDS[v.kind].creature;
    const inMarket = this.inRealm(v.tx, v.tz);
    let best = null;
    for (const g of v.wants) {
      if (this.stockOf(g) <= 0) continue;
      for (const s of this.sellers(g)) {
        const tile = this.serviceTile(s);
        const d = Math.abs(tile[0] - here[0]) + Math.abs(tile[1] - here[1]) + s.queue.length * 3;
        if (!best || d < best.d) best = { s, d, g };
      }
    }
    if (best) {
      v.stallId = best.s.id;
      v.goal = best.g;
      return this.walkTo(v, this.serviceTile(best.s), 'toStall');
    }
    // Nothing to buy from here. Walk up to the market first, then grumble about what's missing.
    if (!inMarket && v.state === 'arrive') return this.walkTo(v, this.plazaTile(), 'arrive');
    for (const g of v.wants) {
      if (v.complained.includes(g)) continue;
      v.complained.push(g);
      if (!this.sellers(g).length) {
        v.sat -= 5;
        if (this.night) this.night.none[g]++;
        if (!creature) this.say(v, LINES.none[g]);
      } else {
        v.sat -= 7;
        if (this.night) this.night.soldOut++;
        this.sayPick(v, creature ? LINES.creature[v.kind] : LINES.sold_out);
      }
    }
    v.wants = [];
    if (v.state === 'arrive' || v.state === 'toStall' || v.state === 'buy') return this.planStroll(v);
    return this.finishVisit(v);
  }

  planStroll(v) {
    const rng = this.rng;
    const spots = this.list(o => TYPES[o.type].rest).map(o => this.restTile(o)).filter(Boolean);
    let tile = null;
    if (spots.length && rng.chance(0.7)) tile = rng.pick(spots);
    if (!tile) {
      const D = this.decorMap();
      const options = [];
      for (let z = 0; z < H; z++) for (let x = 0; x < W; x++) {
        if (this.inRealm(x, z) && this.visitorWalkable(x, z) && this.reachable(x, z)) options.push([[x, z], 1 + D[idx(x, z)]]);
      }
      if (options.length) tile = rng.weighted(options);
    }
    if (!tile) return this.finishVisit(v);
    return this.walkTo(v, tile, 'stroll');
  }

  walkTo(v, tile, state) {
    const path = this.findPath([v.tx, v.tz], tile, (x, z) => this.visitorWalkable(x, z));
    if (!path) return this.finishVisit(v);
    v.path = path;
    v.pi = 1;
    v.state = state;
    if (path.length <= 1) this.arrive(v);
    return true;
  }

  // Leave for home. Happiness is settled here: tips and requests to stay.
  finishVisit(v) {
    if (v.state === 'leave' || v.state === 'flee' || v.state === 'gone') return;
    if (v.stallId) this.leaveQueue(v);
    v.sat = clamp(v.sat - v.fear / 4, 0, 100);
    const n = this.night;
    const def = VISITOR_KINDS[v.kind];
    if (v.sat >= 70) {
      if (n) n.happy++;
      const value = Math.round(this.rng.range(2, 5) * (1 + this.appeal().total / 100));
      const tip = { id: this._vid++, x: v.x + this.rng.range(-0.3, 0.3), z: v.z + this.rng.range(-0.3, 0.3), value, born: this.clockSec };
      this.tips.push(tip);
      this.emit({ type: 'tip', id: tip.id });
      if (def.settles && this.rng.chance(0.42) && !this.settleRequests.some(r => r.name === v.name)) {
        this.settleRequests.push({ name: v.name, kind: v.kind });
        if (n) n.asked.push(v.name);
        this.sayPick(v, LINES.settle);
        this.toast(this.freeBeds() - this.settleRequests.length >= 0 ? `${v.name} asks to settle in the realm.` : `${v.name} wants to stay, but there’s no free bed.`, 'settle');
      }
    } else if (v.sat >= 40) {
      if (n) n.content++;
    } else if (n) n.unhappy++;
    v.state = 'leave';
    v.speed = Math.max(v.speed, 1.7);
    const path = this.findPath([v.tx, v.tz], [ENTRANCE.x, ENTRANCE.z], (x, z) => this.visitorWalkable(x, z));
    v.path = path || [[v.tx, v.tz]];
    v.pi = 1;
    if (!path) v.state = 'gone';
  }

  turnBack(v) {
    v.state = 'flee';
    v.speed = 2.2;
    if (this.night) this.night.turnedBack++;
    this.sayPick(v, VISITOR_KINDS[v.kind].creature ? LINES.creature[v.kind] : LINES.turn_back);
    const path = this.findPath([v.tx, v.tz], [ENTRANCE.x, ENTRANCE.z], (x, z) => this.visitorWalkable(x, z));
    v.path = path || [[v.tx, v.tz]];
    v.pi = 1;
    if (!path) v.state = 'gone';
  }

  leaveQueue(v) {
    const s = this.objects.get(v.stallId);
    if (s && s.queue) {
      const i = s.queue.indexOf(v.id);
      if (i >= 0) { s.queue.splice(i, 1); if (i === 0) s.progress = 0; }
    }
    v.stallId = 0;
  }

  updateVisitor(v, dt) {
    if (v.state === 'queue') return this.updateQueued(v, dt);
    if (v.state === 'linger') {
      v.timer -= dt;
      if (v.timer <= 0) this.finishVisit(v);
      return;
    }
    let step = v.speed * dt;
    while (step > 0 && v.pi < v.path.length) {
      const [nx, nz] = v.path[v.pi];
      const dx = nx + 0.5 - v.x;
      const dz = nz + 0.5 - v.z;
      const d = Math.hypot(dx, dz);
      if (d <= step) {
        v.x = nx + 0.5;
        v.z = nz + 0.5;
        step -= d;
        v.pi++;
        this.enterTile(v, nx, nz);
        if (v.state === 'flee' && v.pi === 1) break; // path was just replaced
      } else {
        v.x += (dx / d) * step;
        v.z += (dz / d) * step;
        v.fx = dx / d;
        v.fz = dz / d;
        step = 0;
      }
    }
    if (v.pi >= v.path.length && v.state !== 'queue' && v.state !== 'linger') this.arrive(v);
  }

  enterTile(v, x, z) {
    v.tx = x;
    v.tz = z;
    const def = VISITOR_KINDS[v.kind];
    if (this.nightFactor() >= 0.5 && !def.lantern && (v.state === 'arrive' || v.state === 'toStall' || v.state === 'leave')) {
      if (this.lightAt(x, z) >= LIT) {
        v.fear = Math.max(0, v.fear - 3);
      } else {
        v.fear += 6;
        if (!v.warned && v.fear >= 18) { v.warned = true; this.sayPick(v, def.creature ? LINES.creature[v.kind] : LINES.dark, 0.7); }
        if (v.fear >= 45 && v.state !== 'leave') return this.turnBack(v);
      }
    }
    if (!v.greeted && this.inRealm(x, z) && v.state !== 'leave' && v.state !== 'flee') {
      v.greeted = true;
      if (v.fear === 0 && !def.creature && this.nightFactor() >= 0.5) this.sayPick(v, LINES.arrive_lit, 0.35);
    }
  }

  arrive(v) {
    if (v.state === 'toStall') {
      const s = this.objects.get(v.stallId);
      if (!s || !this.serviceTile(s)) return this.planNext(v);
      s.queue.push(v.id);
      v.state = 'queue';
      return;
    }
    if (v.state === 'stroll') {
      v.state = 'linger';
      v.timer = this.rng.range(3.5, 7);
      const score = this.decorMap()[idx(v.tx, v.tz)];
      v.sat += clamp((score - 1.5) * 3.5, -6, 14);
      const def = VISITOR_KINDS[v.kind];
      if (def.creature) this.sayPick(v, LINES.creature[v.kind], 0.6);
      else this.sayPick(v, score >= 4 ? LINES.stroll_high : score >= 1.5 ? LINES.stroll_mid : LINES.stroll_low, 0.75);
      return;
    }
    if (v.state === 'arrive') return this.planNext(v);
    if (v.state === 'leave' || v.state === 'flee') v.state = 'gone';
  }

  updateQueued(v, dt) {
    const s = this.objects.get(v.stallId);
    if (!s) { v.stallId = 0; return this.planNext(v); }
    const pos = s.queue.indexOf(v.id);
    const tile = this.serviceTile(s);
    if (pos < 0 || !tile) { v.stallId = 0; return this.planNext(v); }
    // Stand in line, stretching back along the path away from the counter.
    const [fx, fz] = FRONT[s.rot];
    const tx = tile[0] + 0.5 + fx * QUEUE_GAP * pos;
    const tz = tile[1] + 0.5 + fz * QUEUE_GAP * pos;
    const k = Math.min(1, dt * 5);
    v.x += (tx - v.x) * k;
    v.z += (tz - v.z) * k;
    v.fx = -fx;
    v.fz = -fz;
  }

  sovereignAt(s) {
    const tile = this.serviceTile(s);
    return !!tile && Math.hypot(this.player.x - (tile[0] + 0.5), this.player.z - (tile[1] + 0.5)) < 1.35;
  }

  updateStalls(dt) {
    for (const s of this.stalls()) {
      if (!s.queue.length) { s.progress = 0; continue; }
      const helping = this.sovereignAt(s);
      s.helped = helping;
      s.progress += dt * (helping ? 2 : 1);
      if (s.progress >= STALL_LEVELS[s.level].service) {
        s.progress = 0;
        const v = this.visitors.find(x => x.id === s.queue[0]);
        s.queue.shift();
        if (v) this.sell(s, v, helping);
      }
    }
  }

  sell(s, v, helping) {
    const g = s.goods;
    v.stallId = 0;
    v.state = 'buy';
    v.wants = v.wants.filter(w => w !== g);
    if (this.stockOf(g) <= 0) {
      v.sat -= 8;
      if (this.night) this.night.soldOut++;
      this.sayPick(v, LINES.sold_out);
      return this.planNext(v);
    }
    this.stock[g]--;
    const price = Math.round(GOODS[g].price * STALL_LEVELS[s.level].mult);
    this.gold += price;
    s.sold++;
    this.stats.earned += price;
    this.stats.soldTotal[g]++;
    if (this.night) { this.night.sold[g]++; this.night.revenue += price; }
    v.sat += helping ? 17 : 12;
    if (helping) { v.served++; this.sayPick(v, LINES.served, 0.8); } else if (VISITOR_KINDS[v.kind].creature) this.sayPick(v, LINES.creature[v.kind], 0.4);
    else this.sayPick(v, LINES.buy[g], 0.45);
    this.emit({ type: 'sale', id: s.id, goods: g, price });
    this.checkProgress();
    return this.planNext(v);
  }

  collectTip(id) {
    const i = this.tips.findIndex(t => t.id === id);
    if (i < 0) return 0;
    const [tip] = this.tips.splice(i, 1);
    this.gold += tip.value;
    if (this.night) this.night.tips += tip.value;
    this.stats.earned += tip.value;
    this.emit({ type: 'tipCollected', id, value: tip.value, x: tip.x, z: tip.z });
    return tip.value;
  }

  // ─── the Sovereign (walk mode) ─────────────────────────────────────────────
  // Moves by a direction in world tiles per second, sliding along walls. Uses real time.
  movePlayer(dx, dz, dt, speed = 3.4) {
    const p = this.player;
    const len = Math.hypot(dx, dz);
    if (len < 0.01) { p.moving = false; return; }
    p.path = [];
    const sx = (dx / len) * speed * dt;
    const sz = (dz / len) * speed * dt;
    const r = 0.28;
    const free = (x, z) => this.playerWalkable(Math.floor(x - r), Math.floor(z - r)) && this.playerWalkable(Math.floor(x + r), Math.floor(z - r))
      && this.playerWalkable(Math.floor(x - r), Math.floor(z + r)) && this.playerWalkable(Math.floor(x + r), Math.floor(z + r));
    if (free(p.x + sx, p.z)) p.x += sx;
    if (free(p.x, p.z + sz)) p.z += sz;
    p.fx = dx / len;
    p.fz = dz / len;
    p.moving = true;
    this.afterPlayerMove();
  }

  walkPlayerTo(x, z) {
    const from = [Math.floor(this.player.x), Math.floor(this.player.z)];
    let goal = [x, z];
    if (!this.playerWalkable(x, z)) {
      // Walk to the nearest free tile next to the target (a building, a stall, a person).
      const o = this.objectAt(x, z);
      const around = o ? this.neighbourTiles(o) : N8.map(([dx, dz]) => [x + dx, z + dz]);
      const options = around.filter(([a, b]) => this.playerWalkable(a, b));
      options.sort((a, b) => Math.hypot(a[0] - from[0], a[1] - from[1]) - Math.hypot(b[0] - from[0], b[1] - from[1]));
      if (!options.length) return false;
      goal = options[0];
    }
    const path = this.findPath(from, goal, (a, b) => this.playerWalkable(a, b), { diagonal: true });
    if (!path) return false;
    this.player.path = path.slice(1);
    return true;
  }

  // Follows a clicked path. Uses real time.
  stepPlayer(dt, speed = 3.4) {
    const p = this.player;
    if (!p.path.length) { p.moving = false; return; }
    let step = speed * dt;
    while (step > 0 && p.path.length) {
      const [nx, nz] = p.path[0];
      const dx = nx + 0.5 - p.x;
      const dz = nz + 0.5 - p.z;
      const d = Math.hypot(dx, dz);
      if (d <= step) { p.x = nx + 0.5; p.z = nz + 0.5; step -= d; p.path.shift(); } else {
        p.x += (dx / d) * step;
        p.z += (dz / d) * step;
        p.fx = dx / d;
        p.fz = dz / d;
        step = 0;
      }
    }
    p.moving = p.path.length > 0;
    this.afterPlayerMove();
  }

  afterPlayerMove() {
    for (const t of [...this.tips]) if (Math.hypot(t.x - this.player.x, t.z - this.player.z) < 0.8) this.collectTip(t.id);
  }

  // What the Sovereign could interact with right now, nearest first.
  interactables() {
    const p = this.player;
    const out = [];
    for (const o of this.objects.values()) {
      const def = TYPES[o.type];
      const c = this.objCentre(o);
      const reach = Math.max(o.w, o.d) / 2 + 1.1;
      const d = Math.hypot(c.x - p.x, c.z - p.z);
      if (d > reach) continue;
      if (def.produce && o.worker !== undefined) out.push({ kind: 'tend', id: o.id, d, label: this.tended[o.id] === this.day ? 'Tended today' : `Tend the ${def.name}`, ready: this.tended[o.id] !== this.day });
      if (def.sworn) out.push({ kind: 'talk', who: def.sworn, id: o.id, d, label: `Talk to ${def.sworn === 'bram' ? 'Bram' : 'Linnea'}`, ready: true });
      if (o.type === 'beacon') out.push({ kind: 'beacon', id: o.id, d, label: 'Warm your hands at the Heartflame', ready: true });
    }
    const hob = this.list(o => o.worker === 'Hob')[0];
    if (hob) {
      const c = this.objCentre(hob);
      const d = Math.hypot(c.x - p.x, c.z - p.z);
      if (d < 2.6) out.push({ kind: 'talk', who: 'hob', id: hob.id, d: d + 0.2, label: 'Talk to Hob', ready: true });
    }
    return out.sort((a, b) => a.d - b.d);
  }

  interact(target = this.interactables()[0]) {
    if (!target) return null;
    if (target.kind === 'tend') {
      const o = this.objects.get(target.id);
      if (!o || this.tended[o.id] === this.day) return this.talkLine('flicker', 'Those rows are tended for today. Come back tomorrow.');
      this.tended[o.id] = this.day;
      for (const [goods] of Object.entries(TYPES[o.type].produce)) this.addStock(goods, 3, o);
      this.emit({ type: 'tend', id: o.id });
      return this.talkLine('flicker', 'Royal hands in the dirt! +3 for the stores.');
    }
    if (target.kind === 'talk') return this.talkLine(target.who, this.swornLine(target.who));
    if (target.kind === 'beacon') return this.talkLine('flicker', this.beaconTier < 2 ? 'Feed me 250 gold of oil and I’ll light up the whole clearing. Upgrade me in Kingdom View.' : 'Warm, bright, and still humble. That’s me.');
    return null;
  }

  talkLine(who, text) {
    const line = { who, text };
    this.emit({ type: 'talk', ...line });
    return line;
  }

  swornLine(who) {
    const done = id => this.tasksDone.has(id);
    if (who === 'bram') {
      if (!done('light_road')) return 'The Old Road’s black as pitch after dusk. A Lantern Post every few steps through the trees, that’s what it needs.';
      if (!done('build_hut')) return 'Folk won’t stay where there’s nowhere to sleep. Put up a Hut and I’ll have the roof on by supper.';
      if (this.beaconTier < 2) return `Raise the Heartflame and I can build farther out. ${this.gold >= 250 ? 'You’ve the gold for it.' : 'Costs 250 gold of oil and iron, mind.'}`;
      if (this.rank < 2) return `${this.residents.length} of ${VILLAGE_RESIDENTS} under one banner. Beds first, then people.`;
      return 'A Village. Hah. Still plenty to build.';
    }
    if (who === 'linnea') {
      const a = this.appeal();
      if (a.total < 55) return 'The paths look a little bare. Flowers and benches near the stalls make people linger, and people who linger come back.';
      if (!done('happy_12')) return 'Happy visitors leave little tips behind. Pick them up before the mist does!';
      return 'The clearing smells of lavender and bread now. The Veil hates that.';
    }
    if (who === 'hob') {
      if (!this.count('fishery')) return 'There’s trout in that pond, you know. Build a Fishing Hut by the water and folk will pay good coin for it.';
      if (!this.count('cookhouse') && this.isUnlocked('cookhouse')) return 'Turnips and trout in one pot: a Cookhouse would sell Stew all night.';
      return 'The soil here remembers being a garden.';
    }
    return '…';
  }

  // ─── tasks, pages and rank ─────────────────────────────────────────────────
  taskDone(id) {
    const n = this.night;
    switch (id) {
      case 'open_market': return this.stats.nightsOpened >= 1;
      case 'light_road': return this.routeLitFraction() >= 0.85;
      case 'sell_fish': return this.stats.soldTotal.catch >= 1;
      case 'build_hut': return this.count('hut') >= 1;
      case 'first_settler': return this.stats.settled >= 1;
      case 'appeal_55': return this.appeal().total >= 55;
      case 'sell_stew': return this.stats.bestNightSold.stew >= 5 || (n && n.sold.stew >= 5);
      case 'beacon_t2': return this.beaconTier >= 2;
      case 'happy_12': return this.stats.bestNightHappy >= 12 || (n && n.happy >= 12);
      case 'village': return this.rank >= 2;
      default: return false;
    }
  }

  activeTasks() { return TASKS.filter(t => !this.tasksDone.has(t.id)).slice(0, 3); }

  checkProgress() {
    if (this.rank < 2 && this.residents.length >= VILLAGE_RESIDENTS && this.beaconTier >= 2) {
      this.rank = 2;
      this.emit({ type: 'rank', rank: 2 });
    }
    for (const t of TASKS) {
      if (this.tasksDone.has(t.id) || !this.taskDone(t.id)) continue;
      this.tasksDone.add(t.id);
      this.gold += t.reward;
      if (t.page && !this.pages.includes(t.page)) { this.pages.push(t.page); this.emit({ type: 'page', id: t.page }); }
      this.emit({ type: 'task', id: t.id });
      this.toast(`Task done: ${t.title}${t.reward ? ` (+${t.reward} gold)` : ''}`, 'task');
      this._cache = {};
      this.checkProgress();
      return;
    }
  }

  emit(e) { this.events.push(e); if (this.events.length > 400) this.events.splice(0, this.events.length - 400); }
  toast(text, kind = 'info') { this.emit({ type: 'toast', text, kind }); }

  // ─── saves ─────────────────────────────────────────────────────────────────
  serialize() {
    const midNight = this.market.open || this.market.closing || !!this.ledger;
    return {
      v: 1, seed: this.seed, rng: this.rng.state, day: this.day,
      minute: midNight ? Math.min(this.minute, DUSK) : this.minute, openedDay: midNight ? 0 : this.market.openedDay,
      gold: this.gold, stock: { ...this.stock }, beaconTier: this.beaconTier, rank: this.rank,
      paths: [...this.surface.keys()].filter(i => this.surface[i]),
      objects: [...this.objects.values()].map(o => ({ id: o.id, type: o.type, x: o.x, z: o.z, rot: o.rot, variant: o.variant, goods: o.goods, level: o.level, placedDay: o.placedDay })),
      nextId: this.nextId, residents: this.residents.map(r => ({ name: r.name, sworn: r.sworn, since: r.since })),
      tasksDone: [...this.tasksDone], pages: [...this.pages], stats: JSON.parse(JSON.stringify(this.stats)),
      player: { x: this.player.x, z: this.player.z }, tended: { ...this.tended }, usedNames: [...this.usedNames],
    };
  }

  static load(data) {
    const g = new Game({ seed: data.seed, empty: true });
    g.rng.state = data.rng;
    Object.assign(g, { day: data.day, minute: data.minute, gold: data.gold, stock: { ...zeroGoods(), tonic: 0, ...data.stock }, beaconTier: data.beaconTier, rank: data.rank });
    g.market.openedDay = data.openedDay || 0;
    for (const i of data.paths) g.surface[i] = 1;
    for (const s of data.objects) {
      const def = TYPES[s.type];
      if (!def) continue;
      const { w, d } = g.size(s.type, s.rot);
      const o = { id: s.id, type: s.type, x: s.x, z: s.z, rot: s.rot, w, d, variant: s.variant || 0, placedDay: s.placedDay || 1 };
      if (def.stall) Object.assign(o, { goods: s.goods || def.goods || 'harvest', level: s.level || 1, queue: [], progress: 0, sold: 0 });
      if (def.worker) o.worker = null;
      for (const [tx, tz] of g.objTiles(o)) g.occ[idx(tx, tz)] = o.id;
      g.objects.set(o.id, o);
    }
    g.nextId = data.nextId;
    g.residents = data.residents.map(r => ({ ...r }));
    g.tasksDone = new Set(data.tasksDone);
    g.pages = [...data.pages];
    g.stats = { ...g.stats, ...data.stats, soldTotal: { ...zeroGoods(), ...data.stats.soldTotal }, bestNightSold: { ...zeroGoods(), ...data.stats.bestNightSold } };
    g.player.x = data.player.x;
    g.player.z = data.player.z;
    g.tended = { ...data.tended };
    g.usedNames = new Set(data.usedNames || g.residents.map(r => r.name));
    g.changed();
    return g;
  }
}

function zeroGoods() { return { harvest: 0, grain: 0, catch: 0, stew: 0, tonic: 0 }; }

function addLight(L, { x, z, r }) {
  for (let tz = Math.floor(z - r); tz <= Math.ceil(z + r); tz++) {
    for (let tx = Math.floor(x - r); tx <= Math.ceil(x + r); tx++) {
      if (!inBounds(tx, tz)) continue;
      const f = 1 - Math.hypot(tx + 0.5 - x, tz + 0.5 - z) / r;
      if (f > L[idx(tx, tz)]) L[idx(tx, tz)] = f;
    }
  }
}

export { FRONT, ROAD, ENTRANCE, BEACON, W, H, T, idx, inBounds };
export { PAGES };
