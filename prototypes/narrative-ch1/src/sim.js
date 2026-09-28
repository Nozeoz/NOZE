// Kingsbloom Chapter 1 prototype: the simulation.
// Engine-agnostic: it is handed an inkjs Story and runs in the browser and in Node (tests, the fast-forward bot).
// The game owns time, items and numbers; Ink owns the story flags and asks for numbers through EXTERNAL functions.
import {
  WEEKDAYS, PHASES, SEASON_LENGTH, SEASONS, ITEMS, CROPS, RECIPES, BUILDINGS, SWORN_BUILDINGS, PROJECTS, SHOP,
  NPCS, SWORN_ORDER, SETTLER_NAMES, BACKGROUNDS, TRAITS, RANKS, SCENES, HEART_EVENTS, FLAG_NEWS,
} from './content.js';

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const WAYSTONES = [3, 5, 8, 10];
const ENERGY = { gather: 20, forage: 15, fields: 15, dive: 30, help: 10, explore: 10, caravan: 0, rest: 0 };
const UNLOCK_LABELS = {
  'activity:gather': 'Gather and Forage', 'activity:cook': 'Cooking at the campfire', 'activity:fields': 'Working the fields',
  'activity:caravan': "Mira's caravan (Tue and Fri)", 'activity:dive': 'Diving the Sunken Cellars', 'location:windmill': 'The Windmill Ruin',
  'location:meadow': 'Mossbun Meadow', 'recipe:sig_twine': 'Twine Sigil (craft)', 'recipe:food_baked_potato': 'Baked Potato recipe',
  'recipe:food_herb_tea': 'Herb Tea recipe', 'recipe:food_vegetable_stew': 'Vegetable Stew recipe', 'familiar:tending': 'Mossbun tends your field every day',
  'building:lodge': "Carpenter's Lodge", 'building:clinic': 'Herbalist Hut', 'building:longhouse': 'Longhouse blueprint',
  'building:commons': 'Commons Field blueprint', 'building:scout_post': "Scout's Post", 'building:smithy': 'Smithy',
  'building:kitchen': 'Kitchen blueprint', 'building:tavern': 'Tavern (hot meals, +Joy)', 'building:den': 'The Den',
  'building:waybeacon': 'Waybeacon blueprint', 'project:granary': 'Restoration: The Old Granary', 'project:bridge': 'Restoration: The Old Bridge',
  'rank:1': 'Rank: Hamlet', 'rank:2': 'Rank: Village', 'beacon:1': 'Beacon tier 1: the Heartflame Brazier', 'regalia:signet': 'Regalia: the Signet (Purify, Naming)',
  'tool:hoe_copper': 'Copper Hoe: field work costs less energy', 'decree': 'Your first Royal Decree', 'chapter:2': 'Chapter 2: Whispers in the Wood',
};

function freshState(seed) {
  return {
    seed, rng: seed >>> 0 || 1,
    day: 1, phase: 0,
    gold: 0, energy: 100, energyMax: 100, exposure: 0, knockedOut: false,
    inv: {}, fields: [], built: {}, construction: null, projects: {},
    settlers: [], extraBeds: 0, namesUsed: [],
    hearts: {}, talked: {}, gifts: {},
    unlocks: {}, played: {},
    food: 0, joyBonus: 0, hungry: false,
    ra: 0, beacon: 0, depth: 0, waystone: 0, powerBonus: 0, familiars: 0,
    trialDays: 0, courtDay: 0, heartEventDay: 0,
    focus: 'food', copperHoe: false,
    pending: [], log: [],
    stats: { knockouts: 0, dives: 0, arrivals: 0, declined: 0, thefts: 0, scenes: 0 },
    milestones: {},
  };
}

export class Game {
  constructor(story, { seed = 7, onEvent = null } = {}) {
    this.story = story;
    this.s = freshState(seed);
    this.scene = null;
    this.mode = 'plan';
    this.onEvent = onEvent;
    this.news = [];
    this.bindInk();
  }

  // ───────────── Ink bridge
  bindInk() {
    const st = this.story;
    st.BindExternalFunction('item', id => this.item(id), true);
    st.BindExternalFunction('give', (id, n) => { this.give(id, n); }, false);
    st.BindExternalFunction('stat', key => this.stat(key), true);
    st.BindExternalFunction('add_stat', (key, n) => { this.addStat(key, n); }, false);
    st.BindExternalFunction('hearts', npc => this.heartsOf(npc), true);
    st.BindExternalFunction('add_hearts', (npc, p) => { this.addHearts(npc, p); }, false);
    st.BindExternalFunction('weekday', () => this.weekday, true);
    st.BindExternalFunction('season', () => this.season, true);
    st.BindExternalFunction('built', id => this.built(id), true);
    st.BindExternalFunction('unlock', what => { this.unlock(what); }, false);
    st.BindExternalFunction('plant', (crop, n) => { this.plant(crop, n); }, false);
    st.BindExternalFunction('add_settler', (name, role) => { this.addSettler(name, role); }, false);
  }
  v(name) { return this.story.variablesState[name]; }
  flag(name) { return !!this.story.variablesState[name]; }
  setVar(name, value) { this.story.variablesState[name] = value; }
  played(knot) { return !!this.s.played[knot]; }

  // ───────────── Time
  get day() { return this.s.day; }
  get season() { return SEASONS[Math.floor((this.s.day - 1) / SEASON_LENGTH) % 4]; }
  get seasonDay() { return ((this.s.day - 1) % SEASON_LENGTH) + 1; }
  get weekday() { return WEEKDAYS[(this.s.day - 1) % 7]; }
  get phaseName() { return PHASES[this.s.phase]; }
  rand() { this.s.rng = (this.s.rng * 1103515245 + 12345) % 2147483648; return this.s.rng / 2147483648; }

  // ───────────── Inventory
  item(id) {
    if (id === 'food_any') return Object.keys(this.s.inv).filter(k => ITEMS[k]?.dish).reduce((n, k) => n + this.s.inv[k], 0);
    if (id === 'crop_any') return ['crop_turnip', 'crop_carrot', 'crop_potato'].reduce((n, k) => n + (this.s.inv[k] || 0), 0);
    return this.s.inv[id] || 0;
  }
  give(id, n) {
    n = Math.trunc(n);
    if (n < 0 && (id === 'food_any' || id === 'crop_any')) {
      const pool = id === 'food_any'
        ? Object.keys(ITEMS).filter(k => ITEMS[k].dish).sort((a, b) => ITEMS[a].sell - ITEMS[b].sell)
        : ['crop_turnip', 'crop_carrot', 'crop_potato'];
      let left = -n;
      for (const k of pool) { const take = Math.min(left, this.s.inv[k] || 0); this.s.inv[k] = (this.s.inv[k] || 0) - take; left -= take; }
      return;
    }
    this.s.inv[id] = Math.max(0, (this.s.inv[id] || 0) + n);
    if (n !== 0) this.note(`${n > 0 ? '+' : '−'}${Math.abs(n)} ${ITEMS[id]?.name || id}`, 'item');
  }
  hasAll(needs) { return Object.entries(needs).every(([k, n]) => (k === 'gold' ? this.s.gold : this.item(k)) >= n); }
  pay(needs) { for (const [k, n] of Object.entries(needs)) { if (k === 'gold') this.addStat('gold', -n); else this.give(k, -n); } }

  // ───────────── Numbers Ink can ask for
  stat(key) {
    const s = this.s;
    switch (key) {
      case 'gold': return s.gold;
      case 'food': return s.food;
      case 'food_cap': return this.foodCap();
      case 'energy': return s.energy;
      case 'exposure': return s.exposure;
      case 'joy': return this.joy();
      case 'safety': return this.safety();
      case 'ra': return s.ra;
      case 'beacon': return s.beacon;
      case 'floor': return s.depth;
      case 'power': return this.power();
      case 'familiars': return s.familiars;
      case 'residents': return this.residents();
      case 'sworn': return this.swornCount();
      case 'settlers': return s.settlers.length;
      case 'beds_free': return this.bedsFree();
      case 'day': return s.day;
      case 'season_day': return this.seasonDay;
      case 'trial_days': return Math.max(0, s.trialDays);
      case 'construction': return s.construction ? s.construction.daysLeft : 0;
      default: return 0;
    }
  }
  addStat(key, n) {
    const s = this.s;
    n = Math.trunc(n);
    switch (key) {
      case 'gold': s.gold = Math.max(0, s.gold + n); if (n) this.note(`${n > 0 ? '+' : '−'}${Math.abs(n)} gold`, 'gold'); break;
      case 'food': s.food = clamp(s.food + n, 0, this.foodCap()); if (n) this.note(`${n > 0 ? '+' : '−'}${Math.abs(n)} Food Stock`, 'food'); break;
      case 'energy': s.energy = clamp(s.energy + n, 0, s.energyMax); break;
      case 'exposure': s.exposure = clamp(s.exposure + n, 0, 100); break;
      case 'joy': s.joyBonus = clamp(s.joyBonus + n, -30, 30); break;
      case 'ra': s.ra = clamp(s.ra + n, 0, this.raCap()); break;
      case 'beacon': s.beacon = clamp(s.beacon + n, 0, 4); break;
      case 'power': s.powerBonus += n; break;
      case 'familiars': s.familiars += n; break;
      case 'construction': if (s.construction) s.construction.daysLeft = Math.max(1, s.construction.daysLeft + n); break;
      default: break;
    }
  }
  heartsOf(npc) { return Math.floor((this.s.hearts[npc] || 0) / 100); }
  addHearts(npc, points) {
    const before = this.heartsOf(npc);
    this.s.hearts[npc] = clamp((this.s.hearts[npc] || 0) + Math.trunc(points), 0, 1000);
    const after = this.heartsOf(npc);
    if (after > before && NPCS[npc]) this.note(`${NPCS[npc].name}: ${after} ♥`, 'heart', true);
  }
  built(id) {
    if (SWORN_BUILDINGS[id]) return this.flag(SWORN_BUILDINGS[id]);
    if (id === 'granary') return this.flag('ch1_granary_restored');
    if (id === 'kitchen' && this.flag('npc_marigold_recruited')) return true;
    return (this.s.built[id] || 0) > 0;
  }
  unlock(what) {
    if (this.s.unlocks[what]) return;
    this.s.unlocks[what] = true;
    if (what === 'tool:hoe_copper') this.s.copperHoe = true;
    const label = UNLOCK_LABELS[what];
    if (label) this.note(`Unlocked: ${label}`, 'unlock', true);
  }
  unlocked(what) { return !!this.s.unlocks[what]; }
  plant(crop, n) {
    const s = this.s;
    while (s.fields.length < n) s.fields.push({ crop: null, age: 0, watered: false });
    let left = n;
    for (const p of s.fields) if (!p.crop && left > 0) { p.crop = crop; p.age = 0; p.watered = true; left--; }
  }
  addSettler(name, role, trait = '') {
    this.s.settlers.push({ name, role, trait, since: this.s.day });
    this.note(`${name} moved in (${role}).`, 'people', true);
  }

  // ───────────── Kingdom
  swornCount() { return SWORN_ORDER.filter(id => this.flag(`npc_${id}_recruited`)).length; }
  residents() { return this.swornCount() + this.s.settlers.length; }
  beds() { const b = this.s.built; return (b.longhouse ? 2 : 0) + (b.tent || 0) + (b.hut || 0) * 2 + this.s.extraBeds; }
  bedsNeeded() { return this.s.settlers.filter(x => x.role !== 'Child').length; }
  bedsFree() { return this.beds() - this.bedsNeeded(); }
  foodCap() { return this.flag('ch1_granary_restored') ? 200 : 20; }
  rank() { return this.v('kingdom_rank') || 0; }
  raCap() { return 20 + 20 * this.rank(); }
  decree() { return this.v('kingdom_first_decree') || ''; }
  power() { return 1 + this.s.powerBonus + (this.flag('npc_linnea_recruited') ? 1 : 0); }
  joy() {
    let j = 55 + this.s.joyBonus;
    if (this.flag('npc_marigold_recruited')) j += 10;
    if (this.s.hungry) j -= 15;
    if (this.decree() === 'night_curfew') j -= 5;
    if (this.decree() === 'rationing') j -= 10;
    return clamp(j, 0, 100);
  }
  safety() {
    let v = 30 + 10 * this.s.beacon;
    const rep = this.v('kingdom_reputation');
    if (rep === 'stern') v += 10;
    if (rep === 'merciful') v -= 5;
    if (this.decree() === 'night_curfew') v += 10;
    if (this.decree() === 'open_gates') v -= 10;
    if (this.decree() === 'mercy_edict') v -= 5;
    if (this.flag('npc_rook_recruited')) v += 5;
    return clamp(v, 0, 100);
  }
  villageReady() {
    return this.residents() >= RANKS[2].residents && this.swornCount() >= RANKS[2].sworn && this.flag('ch1_signet') && this.s.beacon >= 2;
  }
  nextRankNeeds() {
    const r = this.rank();
    if (r === 0) return [
      { label: 'Residents', have: this.residents(), need: 3 }, { label: 'Sworn', have: this.swornCount(), need: 2 },
      { label: 'Longhouse', ok: this.built('longhouse') }, { label: 'Beacon tier 1', ok: this.s.beacon >= 1 }];
    if (r === 1) return [
      { label: 'Residents', have: this.residents(), need: 12 }, { label: 'Sworn', have: this.swornCount(), need: 5 },
      { label: 'The Signet', ok: this.flag('ch1_signet') }, { label: 'Beacon tier 2', ok: this.s.beacon >= 2 }];
    return [];
  }

  // ───────────── Notes and news
  note(text, kind = 'info', toast = false) {
    const entry = { day: this.s.day, phase: this.s.phase, text, kind };
    this.s.log.push(entry);
    if (this.s.log.length > 160) this.s.log.shift();
    if (toast) this.news.push(entry);
  }
  takeNews() { const n = this.news; this.news = []; return n; }
  snapshotFlags() {
    const out = {};
    for (const name of Object.keys(FLAG_NEWS).concat(['npc_rook_trial', 'ch1_founded'])) out[name] = this.v(name);
    return out;
  }
  afterFlags(before) {
    for (const [name, text] of Object.entries(FLAG_NEWS)) {
      if (!before[name] && this.flag(name)) {
        this.note(text.replace('your realm', this.v('var_kingdom_name') || 'your realm'), 'story', true);
        this.s.milestones[name] = this.s.day;
      }
    }
    if (before.npc_rook_trial !== 'active' && this.v('npc_rook_trial') === 'active') this.s.trialDays = 7;
    if (!before.ch1_founded && this.flag('ch1_founded')) {
      this.s.food = Math.max(this.s.food, 8);
      while (this.s.fields.length < 10) this.s.fields.push({ crop: null, age: 0, watered: false });
      this.note('Hob tilled four more plots: 10 plots in all.', 'info');
    }
    if (!before.npc_rook_recruited && this.flag('npc_rook_recruited')) this.s.extraBeds += 3;
  }

  // ───────────── Scenes
  startScene(knot, opts = {}) {
    const s = this.s;
    s.played[knot] = (s.played[knot] || 0) + 1;
    s.stats.scenes++;
    const others = s.settlers.filter(x => x.name !== 'Hob Furrow' && x.role !== 'Child');
    this.setVar('court_name', others.length ? others[Math.floor(this.rand() * others.length)].name.split(' ')[0] : 'Ada');
    this.before = this.snapshotFlags();
    this.scene = { knot, after: opts.after || null, phaseAction: !!opts.phaseAction, onClose: opts.onClose || null,
      lines: [], choices: [], wait: null, place: '', bg: 'day', lastPicked: null };
    this.mode = 'scene';
    this.story.ChoosePathString(knot, true, opts.args || []);
    this.pump();
  }
  pump() {
    const st = this.story, sc = this.scene;
    while (st.canContinue) {
      const text = st.Continue().trim();
      const tags = parseTags(st.currentTags);
      if (tags.scene) sc.place = tags.scene;
      if (tags.bg) sc.bg = tags.bg;
      const dupe = sc.lastPicked && text === sc.lastPicked;
      sc.lastPicked = null;
      if (text && !dupe) sc.lines.push({ text, ...tags });
      if (tags.input) { sc.wait = { type: 'input', variable: tags.input, prompt: text }; return; }
      if (tags.banner) { sc.wait = { type: 'banner' }; return; }
    }
    if (st.currentChoices.length) {
      sc.choices = st.currentChoices.map(c => ({ index: c.index, text: c.text.trim(), ...parseTags(c.tags || []) }));
      sc.wait = { type: 'choice' };
      return;
    }
    sc.wait = { type: 'end' };
  }
  choose(index) {
    const sc = this.scene;
    const c = sc.choices.find(x => x.index === index);
    if (!c) throw new Error(`No choice ${index} in ${sc.knot}`);
    sc.lines.push({ text: c.text, picked: true, tone: c.tone || null, speaker: c.speaker || null });
    sc.lastPicked = c.text;
    sc.choices = [];
    this.story.ChooseChoiceIndex(index);
    this.pump();
  }
  submitInput(value) {
    const sc = this.scene;
    const fallback = { var_player_name: 'Aria', var_kingdom_name: 'Brightwater' }[sc.wait.variable] || 'Nobody';
    const clean = String(value || '').replace(/[{}#|\\]/g, '').trim().slice(0, 24) || fallback;
    this.setVar(sc.wait.variable, clean);
    sc.lines.push({ text: clean, picked: true, speaker: 'you', input: null });
    sc.wait = null;
    this.pump();
  }
  submitBanner(banner) {
    this.s.banner = banner;
    this.setVar('var_banner', `${banner.emblem} on ${banner.field}`);
    this.scene.wait = null;
    this.pump();
  }
  closeScene() {
    const sc = this.scene;
    if (!sc || sc.wait?.type !== 'end') return;
    this.scene = null;
    this.mode = 'plan';
    this.afterFlags(this.before);
    if (sc.onClose) sc.onClose();
    if (this.flag('ch1_complete')) { this.mode = 'ended'; return; }
    if (this.mode !== 'plan') return;
    if (sc.after === 'dawn') return this.sleep();
    if (sc.after === 'night') { this.s.phase = 3; return this.startPhase(); }
    if (sc.after === 'phase' || sc.phaseAction) return this.endPhase();
    if (!this.checkTriggers()) this.settle();
  }

  // ───────────── Day flow
  begin() { this.startPhase(); return this; }
  startPhase() {
    if (this.checkTriggers()) return;
    this.settle();
  }
  settle() {
    this.mode = 'plan';
    if (this.s.phase === 3) this.sleep();
  }
  checkTriggers() {
    const s = this.s;
    if (s.pending.length && s.phase === 0) {
      const next = s.pending.shift();
      if (next.applicant) this.startArrival(next.applicant);
      else this.startScene(next.knot);
      return true;
    }
    for (const sc of SCENES) {
      if (!sc.repeat && s.played[sc.knot]) continue;
      if (sc.phase) {
        const phases = Array.isArray(sc.phase) ? sc.phase : [sc.phase];
        if (!phases.includes(this.phaseName)) continue;
      } else if (s.phase === 3) continue;
      if (!sc.when(this)) continue;
      if (sc.knot === 'court_weekly' || sc.knot === 'mq116_court') s.courtDay = s.day;
      this.startScene(sc.knot, { after: sc.after });
      return true;
    }
    if (this.phaseName === 'Evening' && s.heartEventDay !== s.day) {
      for (const ev of HEART_EVENTS) {
        const present = this.flag(`npc_${ev.npc}_recruited`);
        if (present && !this.flag(ev.flag) && this.heartsOf(ev.npc) >= ev.hearts && !(ev.flag === 'ev_rook_4' && !this.flag('ev_rook_2'))) {
          s.heartEventDay = s.day;
          this.startScene(ev.knot);
          return true;
        }
      }
    }
    return false;
  }
  endPhase() {
    this.s.phase++;
    if (this.s.phase > 3) return this.sleep();
    this.startPhase();
  }
  sleep() {
    const s = this.s;
    s.day++;
    s.phase = 0;
    s.energy = s.knockedOut ? 60 : s.energyMax;
    s.knockedOut = false;
    s.exposure = 0;
    s.talked = {};
    if (this.weekday === 'Mon') s.gifts = {};
    // Crops grow if watered (or tended by your Mossbun).
    const tending = this.flag('ch1_first_pact');
    for (const p of s.fields) if (p.crop) { if (p.watered || tending) p.age++; p.watered = false; }
    // Construction.
    if (s.construction && --s.construction.daysLeft <= 0) {
      const id = s.construction.id;
      s.built[id] = (s.built[id] || 0) + 1;
      if (id === 'beacon_tower') s.beacon = Math.max(s.beacon, 2);
      this.note(`${BUILDINGS[id].name} finished.`, 'build', true);
      s.construction = null;
    }
    // Royal Authority.
    s.ra = clamp(s.ra + 1 + this.rank(), 0, this.raCap());
    // The realm's day.
    if (this.flag('ch1_founded')) this.kingdomDay();
    if (this.v('npc_rook_trial') === 'active') s.trialDays--;
    this.dawnEvents();
    this.note(`${this.season} ${this.seasonDay}, ${this.weekday}.`, 'day');
    this.startPhase();
  }
  kingdomDay() {
    const s = this.s;
    const workers = s.settlers.filter(x => x.role !== 'Child');
    let prod = 0;
    if (s.focus === 'food') {
      let slots = 3 * (s.built.commons || 0);
      for (const w of workers) { prod += slots > 0 ? 2 : 1; if (slots > 0) slots--; if (w.role === 'Farmer') prod += 1; }
    } else {
      for (const w of workers) { s.inv.mat_wood = (s.inv.mat_wood || 0) + 5; s.inv.min_stone = (s.inv.min_stone || 0) + 3; }
      if (workers.length) this.note(`Settlers brought in ${5 * workers.length} wood and ${3 * workers.length} stone.`, 'item');
    }
    if (this.flag('npc_juniper_recruited')) prod += 2;
    if (this.flag('npc_marigold_recruited')) prod += 2;
    const eat = Math.round(this.residents() * (this.decree() === 'rationing' ? 0.75 : 1));
    const start = s.food;
    s.food = clamp(s.food + prod - eat, 0, this.foodCap());
    s.hungry = start + prod < eat;
    if (s.hungry) { s.joyBonus = clamp(s.joyBonus - 5, -30, 30); this.note('The stores ran out. People went to bed hungry.', 'warn', true); }
    else if (s.joyBonus > 0) s.joyBonus--; else if (s.joyBonus < 0) s.joyBonus++;
    this.note(`Food Stock: +${prod} made, −${eat} eaten → ${s.food}.`, 'food');
  }
  dawnEvents() {
    const s = this.s;
    if (this.flag('deed_banished_rook') && !this.flag('ch1_complete')) {
      const p = (this.safety() >= 60 ? 0.15 : 0.3) * (this.decree() === 'night_curfew' ? 0.5 : 1);
      if (this.rand() < p) {
        let loss;
        if (s.food >= 4) { const n = 3 + Math.floor(this.rand() * 4); s.food = Math.max(0, s.food - n); loss = `${n} rations are gone.`; }
        else { const n = Math.min(s.gold, 20 + Math.floor(this.rand() * 21)); s.gold -= n; loss = `${n} gold is gone.`; }
        s.stats.thefts++;
        this.setVar('theft_loss', loss);
        s.pending.push({ knot: 'theft_report' });
      }
    }
    if (s.summoned) { s.summoned = false; this.queueArrival(); return; }
    if (this.flag('ch1_founded') && this.bedsFree() > 0 && s.food >= this.residents() && this.joy() >= 40 && this.safety() >= 30) {
      const rep = this.v('kingdom_reputation');
      let p = 0.4 + (rep === 'merciful' ? 0.2 : 0) - (rep === 'stern' ? 0.15 : 0);
      if (this.decree() === 'open_gates') p *= 2;
      if (this.decree() === 'mercy_edict' && rep === 'merciful') p += 0.1;
      if (this.rand() < Math.min(0.95, p)) this.queueArrival();
    }
  }
  queueArrival() {
    const s = this.s;
    const names = SETTLER_NAMES.filter(n => !s.namesUsed.includes(n));
    if (!names.length) return;
    const name = names[Math.floor(this.rand() * names.length)];
    const background = BACKGROUNDS[Math.floor(this.rand() * BACKGROUNDS.length)];
    const [trait, phrase] = TRAITS[Math.floor(this.rand() * TRAITS.length)];
    s.namesUsed.push(name);
    s.pending.push({ knot: 'arrival', applicant: { name, background, trait, phrase } });
  }

  // An arrival scene needs the applicant filled in, and reads the answer afterwards.
  startArrival(a) {
    const s = this.s;
    this.setVar('arrival_name', a.name);
    this.setVar('arrival_background', a.background);
    this.setVar('arrival_trait', a.phrase);
    this.startScene('arrival', {
      onClose: () => {
        if (this.flag('arrival_accepted')) { s.stats.arrivals++; this.addSettler(a.name, cap(a.background), a.trait); }
        else s.stats.declined++;
      },
    });
  }

  // ───────────── Actions that use up the part of the day
  actions() {
    const s = this.s, g = this;
    const list = [];
    const add = (id, group, label, desc, energy, ok = true, why = '') => {
      const tired = energy > 0 && s.energy < energy;
      list.push({ id, group, label, desc, energy, disabled: !ok ? why : tired ? 'Too tired' : '' });
    };
    if (this.mode !== 'plan' || s.phase === 3) return list;
    const day = s.phase < 2;
    if (this.unlocked('activity:gather')) {
      add('gather', 'Out in the Vale', 'Gather wood & stone', '+14 wood, +9 stone', ENERGY.gather);
      add('forage', 'Out in the Vale', 'Forage the meadows', 'Herbs, fiber, wild greens, maybe a carrot', ENERGY.forage);
    }
    if (this.unlocked('location:windmill')) add('explore:windmill', 'Out in the Vale', 'Visit the Windmill Ruin', this.flag('npc_bram_recruited') ? 'Bram\'s old camp' : 'Where the smoke was', ENERGY.explore);
    if (this.unlocked('location:meadow')) add('explore:meadow', 'Out in the Vale', 'Visit Mossbun Meadow', this.flag('ch1_first_pact') ? 'Clover, Mossbuns, forage' : 'Where the Mossbuns live', ENERGY.explore);
    if (this.unlocked('activity:fields')) add('fields', 'At home', 'Work the fields', this.fieldSummary(), s.copperHoe ? 10 : ENERGY.fields);
    if (this.unlocked('activity:caravan')) {
      const here = ['Tue', 'Fri'].includes(this.weekday) && day;
      add('caravan', 'At home', "Visit Mira's caravan", here ? 'Buy seeds and treats; sell what you grow' : 'Mira comes on Tuesday and Friday, before dusk', 0, here, 'Not here today');
    }
    if (this.unlocked('activity:dive')) add('dive', 'Below', 'Dive the Sunken Cellars', `From the floor-${this.diveStart()} Waystone · deepest ${s.depth}/10 · power ${this.power()}`, ENERGY.dive);
    for (const id of this.helpable()) add(`help:${id}`, 'Your people', `Spend time with ${NPCS[id].name}`, helpDesc(id), ENERGY.help);
    add('rest', 'Rest', 'Rest by the fire', '+35 energy', 0, s.energy < s.energyMax, 'Already rested');
    if (s.phase === 2) add('bed', 'Rest', 'Go to bed early', 'End the day', 0);
    return list;
  }
  helpable() {
    const ids = [];
    for (const id of SWORN_ORDER) if (this.flag(`npc_${id}_recruited`)) ids.push(id);
    if (this.flag('npc_hob_arrived')) ids.push('hob');
    return ids;
  }
  act(id) {
    const s = this.s;
    const action = this.actions().find(a => a.id === id);
    if (!action) throw new Error(`Action ${id} is not available now`);
    if (action.disabled) throw new Error(`Action ${id} is disabled: ${action.disabled}`);
    s.energy = Math.max(0, s.energy - action.energy);
    const [kind, arg] = id.split(':');
    switch (kind) {
      case 'gather': this.give('mat_wood', 14); this.give('min_stone', 9); return this.endPhase();
      case 'forage': {
        this.give('frg_healing_herb', 2); this.give('mat_fiber', 3); this.give('frg_forage', 4);
        if (this.rand() < 0.25) this.give('crop_carrot', 1);
        return this.endPhase();
      }
      case 'fields': this.workFields(); return this.endPhase();
      case 'rest': this.addStat('energy', 35); this.note('You rest by the fire. +35 energy.', 'info'); return this.endPhase();
      case 'bed': s.phase = 2; return this.endPhase();
      case 'explore': return this.startScene(`loc_${arg}`, { phaseAction: true });
      case 'help': return this.startScene(`help_${arg}`, { phaseAction: true });
      case 'caravan':
        if (!this.talkedToday('mira')) { s.talked.mira = s.day; this.addHearts('mira', 20); }
        return this.startScene('talk_mira', { onClose: () => { this.mode = 'shop'; } });
      case 'dive': return this.dive();
      default: throw new Error(`Unknown action ${id}`);
    }
  }
  leaveCaravan() {
    if (this.mode !== 'shop') return;
    this.mode = 'plan';
    if (this.heartsOf('mira') >= 2 && !this.flag('ev_mira_2')) return this.startScene('heart_mira_2', { phaseAction: true });
    this.endPhase();
  }
  fieldSummary() {
    const f = this.s.fields;
    if (!f.length) return 'No plots yet';
    const ready = f.filter(p => p.crop && p.age >= CROPS[p.crop].days).length;
    const empty = f.filter(p => !p.crop).length;
    const growing = f.length - ready - empty;
    return `${ready} ready · ${growing} growing · ${empty} empty`;
  }
  workFields() {
    const s = this.s;
    let harvested = 0;
    for (const p of s.fields) {
      if (p.crop && p.age >= CROPS[p.crop].days) {
        harvested++;
        if (this.decree() === 'harvest_tithe' && this.flag('ch1_founded') && harvested % 10 === 1) this.addStat('food', 1);
        else this.give(p.crop, 1);
        p.crop = null; p.age = 0;
      }
    }
    const order = ['seed_potato', 'seed_carrot', 'seed_turnip', 'seed_dawnbell'];
    let sown = 0;
    for (const p of s.fields) {
      if (p.crop) continue;
      const seed = order.find(k => (s.inv[k] || 0) > 0);
      if (!seed) break;
      s.inv[seed]--;
      p.crop = Object.keys(CROPS).find(c => CROPS[c].seed === seed);
      p.age = 0;
      sown++;
    }
    for (const p of s.fields) if (p.crop) p.watered = true;
    this.note(`Fields: ${harvested} harvested, ${sown} sown, everything watered.`, 'info');
  }
  diveStart() { return this.s.waystone >= 10 && this.flag('ch1_signet') ? 5 : this.s.waystone; }
  dive() {
    const s = this.s;
    s.stats.dives++;
    let floor = this.diveStart();
    if (floor >= 10 && !this.flag('ch1_signet')) return this.startScene('mq112_ruinback', { phaseAction: true });
    const steps = 3 + (this.flag('npc_rook_recruited') ? 1 : 0);
    const loot = {};
    const bank = () => { for (const [k, n] of Object.entries(loot)) { if (k === 'gold') this.addStat('gold', n); else this.give(k, n); } };
    for (let i = 0; i < steps && floor < 10; i++) {
      floor++;
      s.depth = Math.max(s.depth, floor);
      if (WAYSTONES.includes(floor)) s.waystone = Math.max(s.waystone, floor);
      // Diving tired is risky, and the deepest floors bite if your power is low.
      const risk = (s.energy < 20 && i > 0 ? 0.3 : 0) + (floor >= 8 && this.power() < 3 ? 0.25 : 0);
      if (risk > 0 && this.rand() < risk) {
        if (this.item('con_healing_salve') > 0) { this.give('con_healing_salve', -1); this.note(`Floor ${floor}: you went down hard, but a Healing Salve got you back up.`, 'warn', true); }
        else return this.knockout(floor);
      }
      loot.min_copper_ore = (loot.min_copper_ore || 0) + 2 + (floor >= 4 ? 1 : 0);
      loot.min_stone = (loot.min_stone || 0) + 3;
      if (floor >= 6) loot.min_veilglass = (loot.min_veilglass || 0) + 1;
      loot.gold = (loot.gold || 0) + 3 * floor;
      if (this.rand() < 0.3) loot.frg_healing_herb = (loot.frg_healing_herb || 0) + 1;
      if (this.v('ask_rook') === 'open' && floor >= 2 && !this.item('key_magpie_slingshot')) {
        loot.key_magpie_slingshot = 1;
        this.note(`Floor ${floor}: a slingshot with a crow carved on the grip, wedged under a crate.`, 'story', true);
      }
      if (floor === 3 && !this.flag('npc_tamsin_found')) { bank(); return this.startScene('mq111_captive', { phaseAction: true }); }
      if (floor === 10 && !this.flag('ch1_signet')) { bank(); return this.startScene('mq112_ruinback', { phaseAction: true }); }
    }
    bank();
    this.note(`You dive to floor ${floor}.`, 'info');
    this.endPhase();
  }
  knockout(floor) {
    const s = this.s;
    s.stats.knockouts++;
    s.knockedOut = true;
    this.note(`Knocked out on floor ${floor}. You lost what you found on this dive.`, 'warn', true);
    s.pending.unshift({ knot: 'knockout_wake' });
    this.sleep();
  }

  // ───────────── Free actions (no time passes)
  talkable() {
    const ids = [];
    for (const id of SWORN_ORDER) {
      if (this.flag(`npc_${id}_recruited`)) ids.push(id);
      else if (id === 'rook' && ['active', 'late'].includes(this.v('npc_rook_trial'))) ids.push(id);
      else if (id === 'tamsin' && this.flag('npc_tamsin_found')) ids.push(id);
      else if (id === 'marigold' && this.flag('npc_marigold_met')) ids.push(id);
    }
    if (this.flag('npc_hob_arrived')) ids.push('hob');
    if (this.mode === 'shop') ids.push('mira');
    return ids;
  }
  canTalk(npc) { return this.mode === 'plan' || (this.mode === 'shop' && npc === 'mira'); }
  talkedToday(npc) { return this.s.talked[npc] === this.s.day; }
  talk(npc) {
    if (npc === 'flicker') return this.startScene('talk_flicker');
    if (!this.talkable().includes(npc)) throw new Error(`${npc} is not here`);
    const back = this.mode === 'shop';
    if (!this.talkedToday(npc)) { this.s.talked[npc] = this.s.day; this.addHearts(npc, 20); }
    this.startScene(`talk_${npc}`, { onClose: back ? () => { this.mode = 'shop'; } : null });
  }
  giftsLeft(npc) { return 2 - (this.s.gifts[npc] || 0); }
  taste(npc, itemId) {
    const p = NPCS[npc];
    if (p.loved?.includes(itemId)) return 'loved';
    if (p.liked?.includes(itemId)) return 'liked';
    if (p.disliked?.includes(itemId)) return 'disliked';
    return 'neutral';
  }
  isBirthday(npc) { const b = NPCS[npc]?.birthday; return !!b && b[0] === this.season && b[1] === this.seasonDay; }
  gift(npc, itemId) {
    if (!this.talkable().includes(npc)) throw new Error(`${npc} is not here`);
    if (this.giftsLeft(npc) <= 0 && !this.isBirthday(npc)) throw new Error('Two gifts a week each');
    if (this.item(itemId) < 1 || ITEMS[itemId]?.key) throw new Error('You cannot give that');
    const taste = this.taste(npc, itemId);
    let pts = { loved: 80, liked: 45, neutral: 20, disliked: -20 }[taste];
    if (this.isBirthday(npc) && pts > 0) pts *= 5;
    this.give(itemId, -1);
    this.s.gifts[npc] = (this.s.gifts[npc] || 0) + 1;
    this.addHearts(npc, pts);
    const back = this.mode === 'shop';
    this.startScene(`gift_${npc}`, { args: [taste], onClose: back ? () => { this.mode = 'shop'; } : null });
  }
  recipes() {
    return RECIPES.filter(r => !r.unlock || this.unlocked(r.unlock)).map(r => ({ ...r, name: ITEMS[r.id].name, can: this.flag('ch1_campfire') && this.hasAll(r.needs) }));
  }
  cook(id) {
    const r = this.recipes().find(x => x.id === id);
    if (!r || !r.can) throw new Error(`Cannot make ${id}`);
    this.pay(r.needs);
    this.give(id, 1);
    this.retrigger();
  }
  eat(id) {
    const it = ITEMS[id];
    if (!it?.dish || this.item(id) < 1) throw new Error(`Cannot eat ${id}`);
    this.give(id, -1);
    this.addStat('energy', it.energy);
    if (it.warms) this.addStat('exposure', -30);
    this.note(`You eat the ${it.name}. +${it.energy} energy.`, 'info');
  }
  stock(id, n = 1) {
    if (!this.flag('ch1_founded')) throw new Error('No stores before the Founding');
    const it = ITEMS[id];
    if (!it?.ration) throw new Error(`${id} is not food`);
    n = Math.min(n, this.item(id), Math.ceil((this.foodCap() - this.s.food) / it.ration));
    if (n <= 0) return 0;
    this.give(id, -n);
    this.addStat('food', n * it.ration);
    return n;
  }
  shop() {
    return SHOP.filter(x => !x.needs || this.flag(x.needs)).map(x => ({ ...x, name: x.name || ITEMS[x.id].name, can: this.s.gold >= x.price }));
  }
  buy(id, n = 1) {
    if (this.mode !== 'shop') throw new Error('The caravan is not here');
    const x = this.shop().find(y => y.id === id);
    if (!x) throw new Error(`Mira doesn't sell ${id}`);
    for (let i = 0; i < n; i++) {
      if (this.s.gold < x.price) break;
      this.addStat('gold', -x.price);
      if (id === 'pack_rations') this.addStat('food', 5); else this.give(id, 1);
    }
  }
  sellable() {
    return Object.keys(this.s.inv).filter(k => this.s.inv[k] > 0 && ITEMS[k]?.sell && !ITEMS[k].key)
      .map(k => ({ id: k, name: ITEMS[k].name, count: this.s.inv[k], price: this.sellPrice(k) }));
  }
  sellPrice(id) { return Math.round(ITEMS[id].sell * (this.decree() === 'harvest_tithe' && ITEMS[id].crop ? 0.95 : 1)); }
  sell(id, n = 1) {
    if (this.mode !== 'shop') throw new Error('The caravan is not here');
    n = Math.min(n, this.item(id));
    if (n <= 0) return;
    this.s.inv[id] -= n;
    this.addStat('gold', n * this.sellPrice(id));
    this.note(`Sold ${n} ${ITEMS[id].name}.`, 'gold');
  }
  buildable() {
    return Object.entries(BUILDINGS).filter(([, b]) => b.needs(this)).map(([id, b]) => {
      let why = '';
      if (!b.repeat && this.s.built[id]) why = 'Built';
      else if (this.s.construction?.id === id) why = 'Under construction';
      else if (b.days > 0 && !this.flag('npc_bram_recruited')) why = 'Needs a carpenter';
      else if (b.days > 0 && this.s.construction) why = 'Bram is busy';
      else if (!this.hasAll(b.cost)) why = 'Not enough materials';
      return { id, ...b, count: this.s.built[id] || 0, why };
    });
  }
  build(id) {
    const b = this.buildable().find(x => x.id === id);
    if (!b || b.why) throw new Error(`Cannot build ${id}: ${b?.why || 'unknown'}`);
    this.pay(b.cost);
    if (b.days === 0) {
      this.s.built[id] = (this.s.built[id] || 0) + 1;
      this.note(`${b.name} built.`, 'build', true);
      this.retrigger();
    } else {
      this.s.construction = { id, daysLeft: b.days };
      this.note(`Bram starts on the ${b.name}: ${b.days} day(s).`, 'build', true);
    }
  }
  projects() {
    return Object.entries(PROJECTS).filter(([, p]) => this.unlocked(p.unlock)).map(([id, p]) => ({
      id, ...p, done: p.bundles.every(b => this.s.projects[id]?.[b.id]),
      bundles: p.bundles.map(b => ({ ...b, delivered: !!this.s.projects[id]?.[b.id], can: this.hasAll(b.needs) })),
    }));
  }
  deliver(projectId, bundleId) {
    const p = this.projects().find(x => x.id === projectId);
    const b = p?.bundles.find(x => x.id === bundleId);
    if (!b || b.delivered || !b.can) throw new Error('Cannot deliver that bundle');
    this.pay(b.needs);
    (this.s.projects[projectId] ||= {})[bundleId] = true;
    this.note(`Delivered: ${b.name} (${p.name}).`, 'build', true);
    if (PROJECTS[projectId].bundles.every(x => this.s.projects[projectId][x.id]) && this.mode === 'plan') this.startScene(PROJECTS[projectId].done);
  }
  setFocus(f) { if (['food', 'materials'].includes(f)) this.s.focus = f; }
  // Royal Summons (docs/03 §15.1): spend 15 Royal Authority and a settler answers at the next dawn.
  canSummon() {
    if (!this.flag('ch1_founded')) return 'After the Founding';
    if (this.s.summoned) return 'Someone is already on the way';
    if (this.bedsFree() <= 0) return 'Needs a free bed';
    if (this.s.ra < 15) return 'Needs 15 Royal Authority';
    return '';
  }
  summon() {
    const why = this.canSummon();
    if (why) throw new Error(why);
    this.s.ra -= 15;
    this.s.summoned = true;
    this.note('Royal Summons sent. Someone will answer at dawn.', 'people', true);
  }
  retrigger() { if (this.mode === 'plan') this.checkTriggers(); }

  // ───────────── Save / load
  serialize() { return JSON.stringify({ v: 1, s: this.s, ink: this.story.state.toJson() }); }
  load(json) {
    const data = JSON.parse(json);
    this.s = data.s;
    this.story.state.LoadJson(data.ink);
    this.scene = null;
    this.mode = this.flag('ch1_complete') ? 'ended' : 'plan';
    this.startPhase();
  }
}

function cap(t) { return t.charAt(0).toUpperCase() + t.slice(1); }

function helpDesc(id) {
  return {
    bram: 'Construction goes a day faster (or +8 wood)', linnea: '+3 Healing Herbs', rook: 'Bounties: +40 gold',
    tamsin: 'Nails for Mira: +35 gold', juniper: '+3 greens, +2 Food Stock', marigold: '+8 Food Stock, +Joy', hob: '+4 Food Stock',
  }[id] || '';
}

export function parseTags(tags) {
  const out = {};
  for (const raw of tags || []) {
    const t = String(raw).trim();
    const i = t.indexOf(':');
    if (i < 0) out[t] = true;
    else out[t.slice(0, i).trim()] = t.slice(i + 1).trim();
  }
  return out;
}
