// A simple goal-driven player. The tests use it to finish Chapter 1 on both the Spare and Banish paths,
// and the page uses it to fast-forward to a chosen moment ("Skip to Rook's night").
import { BUILDINGS, PROJECTS, ITEMS, CROPS } from './content.js';

export function autoplay(game, { path = 'spare', tone = 'warm', stopWhen = null, maxSteps = 60000 } = {}) {
  for (let step = 0; step < maxSteps; step++) {
    if (stopWhen && stopWhen(game)) return 'stopped';
    if (game.mode === 'ended') return 'ended';
    if (game.mode === 'scene') { sceneStep(game, path, tone); continue; }
    if (game.mode === 'shop') { shopPolicy(game); game.leaveCaravan(); continue; }
    if (freeActions(game)) continue;
    game.act(pickAction(game));
    if (game.s.day > 200) throw new Error('autoplay: Chapter 1 took more than 200 days');
  }
  throw new Error('autoplay: ran out of steps');
}

function sceneStep(g, path, tone) {
  const sc = g.scene;
  const w = sc.wait;
  if (w.type === 'input') return g.submitInput(w.variable === 'var_player_name' ? 'Aria' : 'Brightwater');
  if (w.type === 'banner') return g.submitBanner({ field: 'navy', emblem: 'sun', accent: 'gold' });
  if (w.type === 'end') return g.closeScene();
  const cs = sc.choices;
  const by = re => cs.find(c => re.test(c.text));
  const pick = (path === 'spare' ? by(/^Spare him/) : by(/^Banish him/))
    || by(/Rattle a Creature Treat/) || by(/^Crouch low/)
    || by(/^Open Gates/)
    || cs.find(c => c.tone === tone)
    || by(/^Grant it/) || by(/^Give it to Hob/) || by(/^Welcome them/) || by(/^Order it investigated/) || by(/^Forgive him/)
    || cs[0];
  g.choose(pick.index);
}

// ─────────────── what the bot is saving up for
function target(g) {
  const s = g.s;
  const bundleNeeds = id => {
    const out = {};
    for (const b of PROJECTS[id].bundles) if (!s.projects[id]?.[b.id]) for (const [k, n] of Object.entries(b.needs)) out[k] = (out[k] || 0) + n;
    return out;
  };
  if (g.flag('ch1_longhouse_planned') && !g.built('longhouse') && !s.construction) return BUILDINGS.longhouse.cost;
  if (g.flag('ch1_granary_shown') && !g.flag('ch1_granary_restored')) return bundleNeeds('granary');
  if (g.flag('npc_tamsin_found') && !g.flag('npc_tamsin_recruited')) return { min_copper_ore: 10 };
  if (g.flag('npc_marigold_met') && !g.built('kitchen') && !(s.construction?.id === 'kitchen')) return BUILDINGS.kitchen.cost;
  if (g.flag('ch1_vs_complete') && g.flag('npc_tamsin_recruited') && s.beacon < 2 && s.construction?.id !== 'beacon_tower') return BUILDINGS.beacon_tower.cost;
  if (g.flag('ch1_founded') && !s.built.commons && s.construction?.id !== 'commons') return BUILDINGS.commons.cost;
  if (g.flag('ch1_founded') && g.bedsFree() <= 0 && g.residents() < 13 && s.construction?.id !== 'hut') return BUILDINGS.hut.cost;
  if (g.flag('ch1_bridge_shown') && !g.flag('ch1_bridge_restored')) return bundleNeeds('bridge');
  if (g.flag('ch1_bridge_restored') && !g.built('waybeacon') && s.construction?.id !== 'waybeacon') return BUILDINGS.waybeacon.cost;
  return {};
}
function shortfall(g) {
  const out = {};
  for (const [k, n] of Object.entries(target(g))) {
    const have = k === 'gold' ? g.s.gold : g.item(k);
    if (have < n) out[k] = n - have;
  }
  return out;
}
const trialOn = g => ['active', 'late'].includes(g.v('npc_rook_trial'));
const readyPlots = g => g.s.fields.filter(p => p.crop && p.age >= CROPS[p.crop].days).length;
const emptyPlots = g => g.s.fields.filter(p => !p.crop).length;
const seeds = g => ['seed_turnip', 'seed_carrot', 'seed_potato'].reduce((n, k) => n + g.item(k), 0);

// ─────────────── free actions; returns true if it started something (a scene)
function freeActions(g) {
  for (const id of g.talkable()) if (id !== 'mira' && !g.talkedToday(id)) { g.talk(id); return true; }
  const s = g.s;
  if (g.flag('npc_bram_found') && !g.flag('npc_bram_recruited') && g.item('food_any') < 1) cookOne(g);
  if (g.flag('ch1_meadow_shown') && !g.flag('ch1_emberkit_pact') && g.item('sig_twine') < 1 && g.item('mat_fiber') >= 3 && g.unlocked('recipe:sig_twine')) g.cook('sig_twine');
  if (g.flag('npc_juniper_met') && !g.flag('npc_juniper_recruited') && g.item('sig_treat') < 1 && g.item('crop_carrot') > 0 && g.item('frg_forage') > 0 && g.unlocked('familiar:tending')) g.cook('sig_treat');
  while (s.energy < 45 && eatOne(g)) { /* keep eating */ }
  if (g.mode !== 'plan') return true;
  if (buildPolicy(g)) return g.mode !== 'plan';
  for (const p of g.projects()) {
    for (const b of p.bundles) {
      if (b.delivered || !b.can) continue;
      g.deliver(p.id, b.id);
      if (g.mode !== 'plan') return true;
    }
  }
  if (g.flag('ch1_founded')) stockPolicy(g);
  if (g.residents() < 12 && !g.canSummon()) g.summon();
  giftPolicy(g);
  return g.mode !== 'plan';
}
function cookOne(g) {
  const r = g.recipes().find(x => !x.craft && x.can);
  if (r) g.cook(r.id);
}
function eatOne(g) {
  const dishes = Object.keys(g.s.inv).filter(k => ITEMS[k]?.dish && g.s.inv[k] > 0);
  if (!dishes.length) {
    if (g.flag('ch1_campfire') && g.item('frg_forage') >= 4) { g.cook('food_foragers_skewer'); return eatOne(g); }
    return false;
  }
  g.eat(dishes[0]);
  return true;
}
function buildPolicy(g) {
  const s = g.s;
  const want = [];
  if (g.flag('ch1_longhouse_planned') && !g.built('longhouse')) want.push('longhouse');
  if (g.flag('npc_marigold_met') && !g.built('kitchen')) want.push('kitchen');
  if (g.flag('ch1_vs_complete') && g.flag('npc_tamsin_recruited') && s.beacon < 2) want.push('beacon_tower');
  if (g.flag('ch1_founded') && !s.built.commons) want.push('commons');
  if (g.flag('ch1_founded') && g.bedsFree() <= 0 && g.residents() < 13) want.push(g.hasAll(BUILDINGS.hut.cost) && !s.construction ? 'hut' : 'tent');
  if (g.flag('ch1_bridge_restored') && !g.built('waybeacon')) want.push('waybeacon');
  for (const id of want) {
    const b = g.buildable().find(x => x.id === id);
    if (b && !b.why) { g.build(id); return true; }
  }
  return false;
}
function stockPolicy(g) {
  const s = g.s;
  const keep = shortfall(g);
  const reserve = { frg_forage: g.flag('ch1_granary_restored') ? 2 : 10, crop_turnip: 0, crop_carrot: 1, crop_potato: 0 };
  const hungry = s.food < g.residents() * 3;
  if (!trialOn(g) && !hungry) return;
  for (const id of ['crop_turnip', 'crop_potato', 'frg_forage', 'crop_carrot', 'food_foragers_skewer', 'food_roasted_turnip']) {
    const spare = g.item(id) - (reserve[id] || 0) - (keep[id] ? 0 : 0) - (target(g).crop_any && ITEMS[id]?.crop ? target(g).crop_any : 0);
    if (spare > 0) g.stock(id, spare);
  }
}
function giftPolicy(g) {
  const plan = [
    ['linnea', 'crop_dawnbell', 1], ['linnea', 'frg_healing_herb', 12], ['bram', 'food_vegetable_stew', 0], ['bram', 'mat_wood', 150],
    ['tamsin', 'min_copper_ore', 30], ['rook', 'trk_crow_charm', 0], ['juniper', 'sig_treat', 2], ['marigold', 'mat_exotic_spice', 0], ['hob', 'crop_turnip', 8],
  ];
  for (const [npc, item, keep] of plan) {
    if (!g.talkable().includes(npc) || g.giftsLeft(npc) <= 0 || g.item(item) <= keep) continue;
    g.gift(npc, item);
    return;
  }
}

// ─────────────── Mira's caravan
function wantsCaravan(g) {
  const need = shortfall(g);
  const sellables = g.sellable().filter(x => !['mat_wood', 'min_stone'].includes(x.id)).reduce((n, x) => n + x.price * x.count, 0);
  return (need.gold && sellables > 0)
    || (g.flag('ch1_meadow_shown') && !g.flag('ch1_first_pact') && g.item('crop_carrot') < 1)
    || (emptyPlots(g) > 0 && seeds(g) < emptyPlots(g) && g.s.gold >= 20)
    || (trialOn(g) && g.stat('food') < 28 && g.s.gold >= 45 && g.flag('ch1_granary_restored'))
    || (g.flag('npc_juniper_met') && !g.flag('npc_juniper_recruited') && g.item('sig_treat') < 1 && g.s.gold >= 30);
}
function shopPolicy(g) {
  const need = shortfall(g);
  const keepIds = new Set(Object.keys(need));
  for (const x of g.sellable()) {
    if (['mat_wood', 'min_stone', 'mat_fiber', 'con_healing_salve', 'sig_twine', 'sig_treat'].includes(x.id)) continue;
    if (keepIds.has(x.id) || (need.crop_any && ITEMS[x.id]?.crop)) continue;
    let keep = { frg_healing_herb: 6, frg_forage: 10, crop_carrot: 2, min_copper_ore: 12, min_veilglass: 8, crop_turnip: trialOn(g) ? 99 : 2, crop_potato: trialOn(g) ? 99 : 1 }[x.id] || 0;
    if (x.count > keep) g.sell(x.id, x.count - keep);
  }
  const reserveGold = need.gold ? need.gold : 0;
  const spend = () => g.s.gold - reserveGold;
  if (g.flag('ch1_meadow_shown') && !g.flag('ch1_first_pact') && g.item('crop_carrot') < 1 && spend() >= 40) g.buy('crop_carrot');
  if (g.flag('npc_juniper_met') && !g.flag('npc_juniper_recruited') && g.item('sig_treat') < 2 && spend() >= 30) g.buy('sig_treat');
  if (trialOn(g) && g.flag('ch1_granary_restored')) while (g.stat('food') < 28 && spend() >= 45) g.buy('pack_rations');
  const gap = emptyPlots(g) - seeds(g);
  for (let i = 0; i < gap; i++) {
    const seed = spend() >= 50 ? 'seed_potato' : spend() >= 20 ? 'seed_turnip' : null;
    if (!seed) break;
    g.buy(seed);
  }
  if (g.flag('npc_rook_recruited') && g.item('trk_crow_charm') < 1 && spend() >= 300 && !g.s.boughtCharm) { g.buy('trk_crow_charm'); g.s.boughtCharm = true; }
}

// ─────────────── what to do with this part of the day
function pickAction(g) {
  const s = g.s;
  const acts = Object.fromEntries(g.actions().map(a => [a.id, a]));
  const ok = id => acts[id] && !acts[id].disabled;
  const need = shortfall(g);
  if (s.energy < 20) return ok('rest') ? 'rest' : 'bed';
  if (ok('caravan') && wantsCaravan(g)) return 'caravan';
  const fieldsDue = readyPlots(g) > 0 || (emptyPlots(g) > 0 && seeds(g) > 0) || (!g.flag('ch1_first_pact') && s.fields.some(p => p.crop && !p.watered));
  if (ok('fields') && fieldsDue && s.phase === 0) return 'fields';
  if (!g.flag('ch1_campfire')) return 'gather';
  if (g.flag('ch1_smoke_seen') && !g.flag('npc_bram_found') && ok('explore:windmill')) return 'explore:windmill';
  if (g.flag('npc_bram_found') && !g.flag('npc_bram_recruited')) {
    if (g.item('frg_healing_herb') >= 3 && g.item('food_any') >= 1 && ok('explore:windmill')) return 'explore:windmill';
    return 'forage';
  }
  if (g.flag('ch1_meadow_shown') && !g.flag('ch1_first_pact') && g.item('crop_carrot') > 0 && ok('explore:meadow')) return 'explore:meadow';
  if (g.flag('ch1_first_pact') && !g.flag('ch1_emberkit_pact') && g.item('sig_twine') > 0 && ok('explore:meadow')) return 'explore:meadow';
  if (g.flag('ch1_vs_complete') && !g.flag('npc_juniper_recruited') && ok('explore:meadow') && s.lastMeadow !== s.day) { s.lastMeadow = s.day; return 'explore:meadow'; }
  if (trialOn(g) && g.stat('food') < 28 && g.flag('ch1_granary_restored')) return ok('help:hob') && s.phase !== 1 ? 'help:hob' : 'forage';
  if (g.flag('npc_tamsin_found') && !g.flag('npc_tamsin_recruited') && g.item('min_copper_ore') < 10 && ok('dive')) return 'dive';
  if (g.flag('world_cellars_open') && !g.flag('ch1_signet') && ok('dive') && s.energy >= 50) return 'dive';
  if ((need.min_copper_ore || need.min_veilglass) && ok('dive')) return 'dive';
  if (need.mat_wood || need.min_stone) return 'gather';
  if (need.frg_forage || need.frg_healing_herb || need.crop_any || need.gold) return 'forage';
  if (s.construction && ok('help:bram')) return 'help:bram';
  const lowest = g.helpable().filter(id => ok(`help:${id}`)).sort((a, b) => (s.hearts[a] || 0) - (s.hearts[b] || 0))[0];
  if (lowest && s.phase === 2) return `help:${lowest}`;
  return ok('gather') ? 'gather' : 'rest';
}
