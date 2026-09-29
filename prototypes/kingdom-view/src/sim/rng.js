// Small seeded random generator (mulberry32) so tests and replays are repeatable.
export function makeRng(seed = 1) {
  let s = (seed >>> 0) || 1;
  const rng = {
    get state() { return s; },
    set state(v) { s = v >>> 0; },
    next() {
      s = (s + 0x6D2B79F5) >>> 0;
      let t = s;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    },
    range(a, b) { return a + (b - a) * rng.next(); },
    int(a, b) { return a + Math.floor(rng.next() * (b - a + 1)); },
    pick(list) { return list[Math.floor(rng.next() * list.length)]; },
    chance(p) { return rng.next() < p; },
    weighted(entries) {
      const total = entries.reduce((sum, [, w]) => sum + w, 0);
      let roll = rng.next() * total;
      for (const [value, w] of entries) { roll -= w; if (roll <= 0) return value; }
      return entries[entries.length - 1][0];
    },
  };
  return rng;
}
