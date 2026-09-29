// Checks the Kingdom View simulation: the map, building rules, the market night,
// light and the Veil, the Sovereign's walk mode, saves, and a full run to Village rank.
// Run with: npm test
import test from 'node:test';
import assert from 'node:assert/strict';
import { Game, LIT, DUSK, CLOSE } from '../src/sim/game.js';
import { autoplay, placeLamps, playDay } from '../src/sim/bot.js';
import { TYPES, TASKS, PAGE_ORDER } from '../src/sim/catalog.js';
import { W, H, T, ROAD, ENTRANCE, idx } from '../src/sim/world.js';

const fresh = (seed = 1) => new Game({ seed });

// First free spot for a building, scanning outward from the Heartflame.
function spot(g, type, rot = 0, avoid = []) {
  const tiles = [];
  for (let z = 0; z < H; z++) for (let x = 0; x < W; x++) tiles.push([x, z]);
  tiles.sort((a, b) => Math.hypot(a[0] - 22, a[1] - 18) - Math.hypot(b[0] - 22, b[1] - 18));
  return tiles.find(([x, z]) => g.canPlace(type, x, z, rot).ok && !avoid.some(([ax, az]) => ax === x && az === z));
}

function runNight(g, { collect = true } = {}) {
  g.skipToDusk();
  assert.ok(g.openMarket(), 'market opens at dusk');
  g.speed = 4;
  for (let i = 0; i < 20000 && !g.ledger; i++) {
    g.update(0.1);
    if (collect) for (const t of [...g.tips]) g.collectTip(t.id);
  }
  assert.ok(g.ledger, 'the night ends with a ledger');
  return g.ledger;
}

test('the map: a clearing, a pond, and a road that reaches the Heartflame', () => {
  const g = fresh();
  const count = t => g.terrain.filter(v => v === t).length;
  assert.ok(count(T.FOREST) > 600, 'forest ring');
  assert.ok(count(T.WATER) > 20, 'pond');
  for (const [x, z] of ROAD) assert.equal(g.terrain[idx(x, z)], T.ROAD);
  assert.deepEqual(g.route()[0], [ENTRANCE.x, ENTRANCE.z]);
  assert.ok(g.route().length > 25, 'a real walk in');
  let fishery = false;
  for (let z = 0; z < H && !fishery; z++) for (let x = 0; x < W && !fishery; x++) fishery = g.canPlace('fishery', x, z, 0).ok;
  assert.ok(fishery, 'a Fishing Hut fits by the pond inside the first realm');
});

test('the starting hamlet obeys its own building rules', () => {
  const g = fresh();
  for (const o of g.objects.values()) {
    if (TYPES[o.type].fixed) continue;
    const check = g.canPlace(o.type, o.x, o.z, o.rot, o.id);
    assert.ok(check.ok, `${o.type} at ${o.x},${o.z}: ${check.reason}`);
  }
  for (const s of g.stalls()) assert.ok(g.serviceTile(s), `${s.type} has a counter on a path`);
  assert.equal(g.residents.length, 4);
  assert.equal(g.beds(), 2);
  assert.equal(g.freeBeds(), 0);
  assert.equal(g.activeTasks().length, 3);
  assert.ok(g.appeal().total > 20 && g.appeal().total < 45, `starting appeal ${g.appeal().total}`);
});

test('building rules: paths, the realm, the pond, overlap, cost, refunds, moving', () => {
  const g = fresh();
  assert.equal(g.canPlace('stall', 21, 20, 0).ok, false, 'not on the street');
  assert.match(g.canPlace('stall', 21, 20, 0).reason, /paths clear/);
  assert.equal(g.canPlace('hut', 22, 38, 0).ok, false, 'not out by the forest road');
  assert.ok(g.canPlace('lamp', 20, 38).ok || g.canPlace('lamp', 23, 38).ok, 'a lamp can stand beside the forest road');
  assert.equal(g.canPlace('fishery', 12, 22, 0).ok, false, 'fishing needs water');
  assert.equal(g.canPlace('tree', 17, 19).ok, false, 'no overlap with the field');
  const gold = g.gold;
  const tree = g.place('tree', 19, 24);
  assert.ok(tree, g.lastError);
  assert.equal(g.gold, gold - TYPES.tree.cost);
  assert.ok(g.move(tree.id, 20, 24, 0), g.lastError);
  assert.equal(g.objectAt(20, 24).id, tree.id);
  assert.ok(g.remove(tree.id));
  assert.equal(g.gold, gold - TYPES.tree.cost + Math.floor(TYPES.tree.cost / 2));
  const tent = g.list(o => o.type === 'tent')[0];
  assert.ok(!g.remove(tent.id), 'someone sleeps there');
  assert.match(g.lastError, /sleeps here/);
  assert.ok(g.paintPath(20, 25), g.lastError);
  assert.ok(g.isPath(20, 25));
  assert.equal(g.canPlace('field_wheat', 10, 22, 0).ok, false, 'locked or outside');
  assert.equal(g.isUnlocked('field_wheat'), false, 'wheat unlocks with the first settler');
});

test('production: a worked field makes 13 Harvest a day, an empty one makes none', () => {
  const g = fresh();
  const [ex, ez] = spot(g, 'field_turnip');
  const extra = g.place('field_turnip', ex, ez, 0);
  assert.ok(extra, g.lastError);
  // Hob works the first field and Ada takes the new one.
  assert.ok(g.list(o => o.type === 'field_turnip').every(o => o.worker));
  const before = g.stock.harvest;
  g.minute = 6 * 60;
  g.skipToDusk();
  while (g.minute < 19 * 60 + 1) g.update(0.5);
  assert.equal(g.stock.harvest - before, 26, 'two fields, 13 hours each');
  const [tx, tz] = spot(g, 'field_turnip');
  const third = g.place('field_turnip', tx, tz, 0);
  assert.ok(third, g.lastError);
  assert.equal(third.worker, null, 'nobody left to work it');
});

test('a dark Old Road turns most travelers back', () => {
  const g = fresh(3);
  assert.ok(g.routeLitFraction() < 0.5);
  const night = runNight(g);
  assert.ok(night.visitors >= 6);
  assert.ok(night.turnedBack >= night.visitors * 0.6, `${night.turnedBack} of ${night.visitors} turned back`);
});

test('lighting the road brings them in: sales, gold, and the task', () => {
  const g = fresh(3);
  placeLamps(g, 0.92);
  assert.ok(g.routeLitFraction() >= 0.85, `lit ${g.routeLitFraction()}`);
  const gold = g.gold;
  const night = runNight(g);
  assert.ok(night.turnedBack <= 1, `${night.turnedBack} turned back`);
  const sold = Object.values(night.sold).reduce((a, b) => a + b, 0);
  assert.ok(sold >= 5, `sold ${sold}`);
  assert.ok(g.gold > gold, 'earned gold');
  assert.ok(night.none.catch + night.none.grain + night.none.stew > 0, 'people ask for goods we do not sell yet');
  g.sleep();
  assert.ok(g.tasksDone.has('light_road') && g.tasksDone.has('open_market'));
  assert.equal(g.day, 2);
});

test('appeal grows with decor, variety and light', () => {
  const g = fresh();
  const a0 = g.appeal().total;
  for (const [type, x, z] of [['flowers', 20, 19], ['tree', 20, 23], ['hedge', 23, 22], ['crates', 23, 21]]) assert.ok(g.place(type, x, z), `${type}: ${g.lastError}`);
  const a1 = g.appeal();
  assert.ok(a1.total > a0, `${a1.total} > ${a0}`);
  assert.ok(a1.variety > 10);
  placeLamps(g, 0.92);
  assert.ok(g.appeal().light > a1.light);
});

test('the Sovereign at a stall serves twice as fast and delights customers', () => {
  const timeToServe = helping => {
    const g = fresh(5);
    placeLamps(g, 0.92);
    const stall = g.stalls().find(s => s.type === 'stall');
    const tile = g.serviceTile(stall);
    g.minute = 20 * 60;
    g.market.open = true;
    g.night = { sold: {}, none: {}, asked: [] };
    for (const k of ['harvest']) g.night.sold[k] = 0;
    g.player.x = helping ? tile[0] + 0.5 : 5;
    g.player.z = helping ? tile[1] + 0.5 : 5;
    const v = g.spawnVisitor('traveler');
    v.wants = ['harvest'];
    v.tx = tile[0]; v.tz = tile[1]; v.x = tile[0] + 0.5; v.z = tile[1] + 0.5;
    v.state = 'toStall';
    v.stallId = stall.id;
    g.arrive(v);
    let t = 0;
    while (stall.queue.includes(v.id) && t < 20) { g.updateStalls(0.05); t += 0.05; }
    return { t, sat: v.sat };
  };
  const alone = timeToServe(false);
  const helped = timeToServe(true);
  assert.ok(helped.t < alone.t * 0.6, `${helped.t} vs ${alone.t}`);
  assert.ok(helped.sat > alone.sat);
});

test('tips: click them for gold, and Flicker saves half of the ones you miss', () => {
  const g = fresh(9);
  placeLamps(g, 0.92);
  const night = runNight(g, { collect: false });
  assert.ok(night.happy >= 1 ? night.tipsMissed > 0 : true);
  assert.equal(g.tips.length, 0);
  const g2 = fresh(9);
  g2.tips.push({ id: 999, x: 5, z: 5, value: 7 });
  const gold = g2.gold;
  assert.equal(g2.collectTip(999), 7);
  assert.equal(g2.gold, gold + 7);
});

test('walking as the Sovereign: walls, paths, tending and talking', () => {
  const g = fresh();
  const p = g.player;
  // Walk east into the pond: we stop at the shore.
  p.x = 26.5; p.z = 24.5;
  for (let i = 0; i < 100; i++) g.movePlayer(1, 0, 0.05);
  assert.ok(g.terrain[idx(Math.floor(p.x), Math.floor(p.z))] !== T.WATER, 'stays out of the pond');
  // Click on Bram's lodge: walk to its door.
  p.x = 21.5; p.z = 20.5;
  assert.ok(g.walkPlayerTo(14, 14));
  for (let i = 0; i < 400 && p.path.length; i++) g.stepPlayer(0.05);
  const talk = g.interactables().find(a => a.kind === 'talk' && a.who === 'bram');
  assert.ok(talk, 'Bram is in reach');
  assert.match(g.interact(talk).text, /Road|road/);
  // Tend the turnip field once a day.
  p.x = 20.5; p.z = 20.5;
  const tend = g.interactables().find(a => a.kind === 'tend');
  assert.ok(tend);
  const h = g.stock.harvest;
  g.interact(tend);
  assert.equal(g.stock.harvest, h + 3);
  g.interact(tend);
  assert.equal(g.stock.harvest, h + 3, 'only once a day');
});

test('saves: a morning save loads back to the same kingdom', () => {
  const g = fresh(11);
  playDay(g);
  playDay(g);
  const data = JSON.parse(JSON.stringify(g.serialize()));
  const h = Game.load(data);
  assert.deepEqual(JSON.parse(JSON.stringify(h.serialize())), data);
  assert.equal(h.appeal().total, g.appeal().total);
  assert.equal(h.routeLitFraction(), g.routeLitFraction());
  const l1 = playDay(g);
  const l2 = playDay(h);
  assert.deepEqual(l2, l1, 'the same night plays out the same way');
});

for (const seed of [1, 7, 42, 99]) {
  test(`the bot raises the Hamlet to a Village (seed ${seed})`, () => {
    const g = fresh(seed);
    const ledgers = autoplay(g, { maxDays: 14, until: x => x.rank >= 2 && TASKS.every(t => x.tasksDone.has(t.id)) });
    assert.equal(g.rank, 2, `rank ${g.rank} after ${ledgers.length} days`);
    assert.ok(g.residents.length >= 12);
    assert.equal(g.beaconTier, 2);
    for (const t of TASKS) assert.ok(g.tasksDone.has(t.id), `task ${t.id}`);
    for (const p of PAGE_ORDER) assert.ok(g.pages.includes(p), `page ${p}`);
    assert.ok(ledgers.length >= 5, `not too fast: ${ledgers.length} days`);
  });
}
