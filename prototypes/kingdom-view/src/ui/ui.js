// The HUD and everything the player touches: tools, the build catalogue, building details,
// walking as the Sovereign, speech bubbles, the Night Ledger, the Royal Chronicle, and settings.
import { TYPES, CATEGORIES, GOODS, MARKET_GOODS, STALL_LEVELS, BEACON_TIERS, TASKS, PAGES, PAGE_ORDER } from '../sim/catalog.js';
import { fmtClock, DUSK, VILLAGE_RESIDENTS } from '../sim/game.js';
import { ICON, GOODS_ICON } from './icons.js';
import { HALF } from '../render/veil.js';
import { playDay } from '../sim/bot.js';

const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const WHO = { flicker: ['Flicker', 'F'], bram: ['Bram', 'B'], linnea: ['Linnea', 'L'], hob: ['Hob', 'H'] };
const STOCK_ORDER = ['harvest', 'grain', 'catch', 'stew', 'tonic'];
const SEASON = d => `Spring ${((d - 1) % 28) + 1}`;
const MOVE_KEYS = { w: [0, 1], arrowup: [0, 1], s: [0, -1], arrowdown: [0, -1], a: [-1, 0], arrowleft: [-1, 0], d: [1, 0], arrowright: [1, 0] };

export class UI {
  constructor({ app, view, game, audio, hasSave, onRestart, onQuality, save, quality }) {
    Object.assign(this, { app, view, game, audio, onRestart, onQuality, save, quality });
    this.hud = app.querySelector('#hud');
    this.state = { mode: 'view', tool: 'select', placing: null, selected: null, hoverTile: null, showDark: false, cat: 'paths', started: false };
    this.keys = new Set();
    this.pointers = new Map();
    this.floats = [];
    this.bubbleEls = [];
    this.hudTimer = 0;
    this.talkTimer = 0;
    this.pending = null;
    this.readPages = new Set(game.pages);
    this.tasksCollapsed = window.innerWidth < 760;
    this.htmlCache = {};
    this.saleSound = 0;
    this.build();
    this.bind();
    this.showTitle(hasSave);
  }

  // ─── DOM ───────────────────────────────────────────────────────────────────
  build() {
    this.hud.innerHTML = `
<header class="top">
  <div class="realm card">
    <div class="crest">${ICON.crown}</div>
    <div class="realm-name"><b>Dawnmere</b><small id="rank">Hamlet</small></div>
    <div class="stats">
      <span class="stat" title="Gold"><span class="ic">${ICON.gold}</span><b id="gold">0</b></span>
      <span class="stat" title="Residents. A Village needs ${VILLAGE_RESIDENTS}."><span class="ic">${ICON.people}</span><b id="res">0</b><small>/${VILLAGE_RESIDENTS}</small></span>
      <span class="stat" title="Free beds"><span class="ic">${ICON.bed}</span><b id="beds">0</b></span>
    </div>
  </div>
  <div class="mid">
    <div class="midrow">
      <div class="stocks card" aria-label="Kingdom stores">${STOCK_ORDER.map(g => `<span class="chip" id="chip-${g}" title="${GOODS[g].name} (${GOODS[g].item})"><span class="ic">${GOODS_ICON[g]}</span><b id="st-${g}">0</b></span>`).join('')}</div>
      <div class="clock card"><span class="ic" id="phase">${ICON.sun}</span><b id="clock">08:00</b><small id="day"></small></div>
    </div>
    <button class="market-btn" id="market" type="button"></button>
  </div>
  <div class="right">
    <div class="appeal card" id="appeal-card"><span class="ic">${ICON.appeal}</span><div class="meter"><span id="appeal-bar"></span></div><b id="appeal">0</b></div>
    <button class="icon-btn" id="btn-book" type="button" aria-label="Royal Chronicle" title="Royal Chronicle">${ICON.book}<span class="dot" hidden></span></button>
    <button class="icon-btn" id="btn-sound" type="button" aria-label="Turn sound on" title="Sound">${ICON.mute}</button>
    <button class="icon-btn" id="btn-settings" type="button" aria-label="Settings" title="Settings">${ICON.gear}</button>
    <button class="icon-btn" id="btn-help" type="button" aria-label="Controls" title="Controls">${ICON.help}</button>
  </div>
</header>
<aside class="tasks card" id="tasks" aria-label="Tasks"></aside>
<aside class="inspect" id="inspect" hidden></aside>
<div class="catalog card" id="catalog" hidden></div>
<footer class="bottom">
  <div class="seg card" id="speed" aria-label="Game speed">
    <button type="button" data-speed="0" aria-label="Pause" title="Pause (P)">${ICON.pause}</button>
    <button type="button" data-speed="1" aria-label="Normal speed" title="Normal speed (1)">${ICON.play}</button>
    <button type="button" data-speed="2" aria-label="Double speed" title="Double speed (2)"><b>2×</b></button>
    <button type="button" data-speed="4" aria-label="Fast" title="Fast (3)">${ICON.fast}</button>
  </div>
  <div class="mode-row">
    <div class="seg card" id="tools">
      <button type="button" data-mode="view" title="Kingdom View (Tab)">${ICON.crown}<span class="lbl">Kingdom View</span></button>
      <button type="button" data-mode="walk" title="Walk as the Sovereign (Tab)">${ICON.walk}<span class="lbl">Walk</span></button>
      <span class="sep"></span>
      <button type="button" data-tool="select" title="Select">${ICON.select}<span class="lbl">Select</span></button>
      <button type="button" data-tool="build" title="Build (B)">${ICON.build}<span class="lbl">Build</span></button>
      <button type="button" data-tool="move" title="Move">${ICON.move}<span class="lbl">Move</span></button>
      <button type="button" data-tool="remove" title="Remove">${ICON.remove}<span class="lbl">Remove</span></button>
    </div>
  </div>
  <div class="seg card cam">
    <button type="button" data-cam="left" aria-label="Turn the camera left" title="Turn left (Q)">${ICON.rotL}</button>
    <button type="button" data-cam="right" aria-label="Turn the camera right" title="Turn right (E)">${ICON.rotR}</button>
    <button type="button" data-cam="photo" aria-label="Photo mode" title="Photo mode">${ICON.camera}</button>
  </div>
</footer>
<div class="hint" id="hint" hidden></div>
<div class="confirm card" id="confirm" hidden>
  <button type="button" class="btn" data-confirm="rotate">${ICON.rotate}Rotate</button>
  <button type="button" class="btn" data-confirm="style">Style</button>
  <button type="button" class="btn primary" data-confirm="place">${ICON.check}Place</button>
  <button type="button" class="btn" data-confirm="cancel" aria-label="Stop building">${ICON.close}</button>
</div>
<div class="talk card" id="talk" hidden></div>
<div class="toasts" id="toasts" aria-live="polite"></div>
<div class="bubbles" id="bubbles"></div>
<div class="floats" id="floats"></div>
<div class="modal" id="modal" hidden></div>
<button type="button" class="btn photo-exit" id="photo-exit">Exit photo mode</button>`;
    this.el = id => this.hud.querySelector(`#${id}`);
    this.renderCatalog();
  }

  bind() {
    this.hud.addEventListener('click', e => this.onHudClick(e));
    const cv = this.view.renderer.domElement;
    cv.addEventListener('pointerdown', e => this.onDown(e));
    window.addEventListener('pointermove', e => this.onMove(e));
    window.addEventListener('pointerup', e => this.onUp(e));
    window.addEventListener('pointercancel', e => this.onUp(e, true));
    cv.addEventListener('wheel', e => { e.preventDefault(); this.view.rig.zoom(Math.exp(e.deltaY * 0.0012)); }, { passive: false });
    cv.addEventListener('contextmenu', e => e.preventDefault());
    window.addEventListener('keydown', e => this.onKey(e, true));
    window.addEventListener('keyup', e => this.onKey(e, false));
    window.addEventListener('blur', () => this.keys.clear());
  }

  // ─── title ─────────────────────────────────────────────────────────────────
  showTitle(hasSave) {
    const g = this.game;
    const title = document.createElement('div');
    title.className = 'title';
    title.innerHTML = `<div class="title-card">
      <h1>Kingsbloom</h1>
      <div class="tag">Kingdom View · 3D prototype</div>
      <ul class="card">
        <li><span class="ic">${ICON.build}</span><span><b>Build freely</b> in Kingdom View: paths, stalls, fields, homes, lanterns and flowers.</span></li>
        <li><span class="ic">${ICON.lantern}</span><span><b>Light the Old Road.</b> At dusk, open the Lantern Market. Travelers turn back in the dark.</span></li>
        <li><span class="ic">${ICON.walk}</span><span><b>Walk as the Sovereign.</b> Tend fields, talk to Bram and Linnea, and serve at a stall yourself.</span></li>
        <li><span class="ic">${ICON.people}</span><span><b>Grow the Hamlet into a Village:</b> happy visitors ask to stay if there is a bed for them.</span></li>
      </ul>
      <div class="acts">
        ${hasSave ? `<button type="button" class="btn primary" data-title="continue">Continue (day ${hasSave.day})</button>` : ''}
        <button type="button" class="btn ${hasSave ? '' : 'primary'}" data-title="new">${hasSave ? 'Start over' : 'Begin'}</button>
        <button type="button" class="btn" data-title="sound" aria-pressed="false">${ICON.music}Music and sound</button>
      </div>
      <p class="small">Placeholder 3D art made in code. Nothing here is final. Graphics: ${esc(this.quality)} (change in Settings).</p>
    </div>`;
    this.app.querySelector('#hud').appendChild(title);
    this.app.classList.add('titled');
    this.titleEl = title;
    g.speed = 0;
    title.addEventListener('click', e => {
      const b = e.target.closest('[data-title]');
      if (!b) return;
      const act = b.dataset.title;
      if (act === 'sound') {
        const on = this.audio.toggle();
        b.setAttribute('aria-pressed', String(on));
        this.syncSoundButton();
        return;
      }
      if (act === 'new' && hasSave) return this.onRestart();
      this.begin();
    });
  }

  begin() {
    if (this.titleEl) { this.titleEl.remove(); this.titleEl = null; }
    this.app.classList.remove('titled');
    this.state.started = true;
    this.game.speed = 1;
    this.toast('Day 1 in Dawnmere. Bram and Flicker have tasks for you (left).', 'info');
  }

  // ─── HUD refresh ───────────────────────────────────────────────────────────
  refreshHud() {
    const g = this.game;
    const set = (id, v) => { const e = this.el(id); if (e && e.textContent !== String(v)) e.textContent = v; };
    set('gold', g.gold);
    set('res', g.residents.length);
    set('beds', g.freeBeds());
    set('rank', g.rank >= 2 ? 'Village' : 'Hamlet');
    for (const k of STOCK_ORDER) {
      set(`st-${k}`, g.stock[k]);
      const chip = this.el(`chip-${k}`);
      chip.classList.toggle('zero', g.stock[k] === 0);
      chip.classList.toggle('low', g.stock[k] > 0 && g.stock[k] < 4 && g.market.open);
    }
    set('clock', fmtClock(g.minute));
    set('day', SEASON(g.day));
    const night = g.nightFactor();
    const phase = night > 0.6 ? 'moon' : night > 0.05 ? 'dusk' : 'sun';
    if (this.phase !== phase) { this.phase = phase; const p = this.el('phase'); p.innerHTML = ICON[phase]; p.classList.toggle('night', phase === 'moon'); }
    const a = g.appeal();
    set('appeal', a.total);
    this.el('appeal-bar').style.width = `${a.total}%`;
    this.el('appeal-card').title = `Appeal ${a.total}: decor ${a.decor}, variety ${a.variety}, light ${a.light}, Linnea's stall ${a.sworn}. More appeal brings more visitors (${g.visitorsExpected()} expected tonight).`;
    this.renderMarketButton();
    this.renderTasks();
    for (const b of this.hud.querySelectorAll('[data-speed]')) b.setAttribute('aria-pressed', String(Number(b.dataset.speed) === g.speed));
    for (const b of this.hud.querySelectorAll('[data-mode]')) b.setAttribute('aria-pressed', String(b.dataset.mode === this.state.mode));
    for (const b of this.hud.querySelectorAll('[data-tool]')) {
      b.setAttribute('aria-pressed', String(this.state.mode === 'view' && b.dataset.tool === this.state.tool));
      b.hidden = this.state.mode === 'walk';
    }
    this.hud.querySelector('#tools .sep').hidden = this.state.mode === 'walk';
    const dot = this.el('btn-book').querySelector('.dot');
    dot.hidden = g.pages.every(p => this.readPages.has(p));
    if (this.state.selected) this.renderInspect();
    if (this.state.tool === 'build' && !this.el('catalog').hidden) this.renderCatalog();
    this.renderHint();
  }

  marketState() {
    const g = this.game;
    if (g.ledger) return { label: 'Night Ledger', act: 'ledger', cls: 'seal' };
    if (g.market.open) return { label: 'Close the market', sub: `${g.visitors.length} here`, act: 'close', cls: 'open' };
    if (g.market.closing) return { label: 'Closing up…', disabled: true, cls: 'open' };
    if (g.canOpenMarket()) return { label: 'Open the Lantern Market', act: 'open', cls: 'seal pulse', icon: ICON.lantern };
    if (g.minute < DUSK) return { label: 'Skip to dusk', sub: 'market opens at 17:00', act: 'skip', icon: ICON.skip };
    return { label: 'Rest until dawn', act: 'sleep', icon: ICON.moon };
  }

  renderMarketButton() {
    const s = this.marketState();
    const html = `${s.icon ? `<span class="ic">${s.icon}</span>` : ''}${esc(s.label)}${s.sub ? ` <small>${esc(s.sub)}</small>` : ''}`;
    const b = this.el('market');
    if (this.htmlCache.market !== html + s.cls) {
      this.htmlCache.market = html + s.cls;
      b.innerHTML = html;
      b.className = `market-btn ${s.cls || ''}`;
    }
    b.disabled = !!s.disabled;
    b.dataset.act = s.act || '';
  }

  taskProgress(id) {
    const g = this.game;
    const night = g.night;
    switch (id) {
      case 'light_road': return `The way in is ${Math.round(g.routeLitFraction() * 100)}% lit. Goal: 85%. Dark stretches show violet marks.`;
      case 'appeal_55': return `Appeal ${g.appeal().total} of 55`;
      case 'happy_12': return `Best night so far: ${Math.max(g.stats.bestNightHappy, night ? night.happy : 0)} of 12 happy`;
      case 'sell_stew': return `Best night so far: ${Math.max(g.stats.bestNightSold.stew, night ? night.sold.stew : 0)} of 5 Stew`;
      case 'village': return `${g.residents.length} of ${VILLAGE_RESIDENTS} residents · Heartflame ${g.beaconTier >= 2 ? 'raised' : 'not raised yet'}`;
      case 'sell_fish': return g.count('fishery') ? 'Now set a stall to sell Catch.' : '';
      case 'build_hut': return `Free beds: ${g.freeBeds()}`;
      case 'first_settler': return `Free beds: ${g.freeBeds()}`;
      default: return '';
    }
  }

  renderTasks() {
    const g = this.game;
    const list = g.activeTasks();
    const html = `<h2>Tasks <button type="button" data-act="tasks-toggle">${this.tasksCollapsed ? 'Show' : 'Hide'}</button></h2>${list.length ? list.map(t => {
      const [name, init] = WHO[t.giver];
      const prog = this.taskProgress(t.id);
      return `<div class="task"><span class="who who-${t.giver}" title="${name}">${init}</span><div><b>${esc(t.title)}</b><p>${esc(t.text)}</p>${prog ? `<div class="prog">${esc(prog)}</div>` : ''}</div></div>`;
    }).join('') : '<div class="task"><span class="who who-flicker">F</span><div><b>Every task is done</b><p>Keep building. The Chronicle has the whole story so far.</p></div></div>'}`;
    const el = this.el('tasks');
    if (this.htmlCache.tasks !== html) { this.htmlCache.tasks = html; el.innerHTML = html; }
    el.classList.toggle('collapsed', this.tasksCollapsed);
  }

  // ─── build catalogue ───────────────────────────────────────────────────────
  renderCatalog() {
    const g = this.game;
    const cat = this.state.cat;
    const items = Object.entries(TYPES).filter(([, d]) => d.cat === cat && !d.fixed);
    const html = `<div class="cat-tabs" role="tablist">${CATEGORIES.map(c => `<button type="button" role="tab" data-cat="${c.id}" aria-selected="${c.id === cat}">${esc(c.name)}</button>`).join('')}</div>
      <div class="items">${items.map(([type, d]) => {
        const locked = !g.isUnlocked(type);
        const poor = g.gold < d.cost;
        const lockTask = d.unlock && TASKS.find(t => t.id === d.unlock);
        const on = this.state.placing && this.state.placing.type === type && !this.state.placing.moving;
        return `<button type="button" class="item ${locked ? 'locked' : ''} ${poor ? 'poor' : ''}" data-item="${type}" aria-pressed="${!!on}" ${locked ? 'aria-disabled="true"' : ''}>
          <b>${esc(d.name)}</b><span class="cost">${ICON.gold}${d.cost}</span><small>${locked ? `Unlocks with “${esc(lockTask ? lockTask.title : d.unlock)}”` : esc(d.desc)}</small></button>`;
      }).join('')}</div>`;
    if (this.htmlCache.catalog !== html) { this.htmlCache.catalog = html; this.el('catalog').innerHTML = html; }
  }

  // ─── building details ──────────────────────────────────────────────────────
  renderInspect() {
    const g = this.game;
    const el = this.el('inspect');
    const o = g.objects.get(this.state.selected);
    if (!o) { this.state.selected = null; el.hidden = true; return; }
    const def = TYPES[o.type];
    const rows = [];
    let body = '';
    let acts = '';
    let note = '';
    if (def.stall) {
      const level = STALL_LEVELS[o.level];
      const next = STALL_LEVELS[o.level + 1];
      const service = g.serviceTile(o);
      if (!def.goods) {
        body += `<div class="goods" role="group" aria-label="What this stall sells">${MARKET_GOODS.map(k => `<button type="button" data-act="goods" data-goods="${k}" aria-pressed="${o.goods === k}">${GOODS_ICON[k]}${GOODS[k].name}<small>${g.stock[k]} in store</small></button>`).join('')}</div>`;
      }
      rows.push(['Sells', `${GOODS[o.goods].name} (${g.stock[o.goods]} in store)`]);
      rows.push(['Price', `${Math.round(GOODS[o.goods].price * level.mult)} gold each`]);
      rows.push(['Serves a customer every', `${level.service.toFixed(1)} s`]);
      rows.push(['Level', `${o.level} of 3`]);
      if (g.market.open) rows.push(['Sold tonight', o.sold]);
      if (!def.goods) acts += next ? `<button type="button" class="btn primary" data-act="upgrade" ${g.gold < next.cost ? 'disabled' : ''}>Upgrade: ×${next.mult} price, ${next.service}s (${next.cost} gold)</button>` : '<span class="note">Fully upgraded.</span>';
      if (!service) note = `<p class="note warn">No path runs past the counter, so nobody can buy here. Paint a path in front of it.</p>`;
      else if (g.market.open && g.sovereignAt(o)) note = '<p class="note">You are serving here: twice as fast, and customers love it.</p>';
      else note = '<p class="note">Tip: walk to the front of a stall as the Sovereign during the market to serve twice as fast.</p>';
      if (def.sworn) note = `<p class="note">Linnea brews ${g.stock.tonic} Tonics here and sells them herself. A new Tonic every two hours.</p>` + note;
    } else if (def.produce || def.convert) {
      rows.push(['Worked by', o.worker || 'nobody']);
      if (def.produce) for (const [k, n] of Object.entries(def.produce)) rows.push(['Makes', `+${n} ${GOODS[k].name} an hour, 07:00–19:00`]);
      if (def.convert) rows.push(['Makes', '1 Harvest + 1 Catch → 1 Stew, each hour']);
      if (!o.worker) note = '<p class="note warn">Nobody works here yet. Happy visitors can settle if there is a free bed.</p>';
      else note = '<p class="note">Walk here as the Sovereign to lend a hand: +3 once a day.</p>';
    } else if (def.beds) {
      rows.push(['Beds', def.beds]);
      rows.push(['Free beds in the realm', g.freeBeds()]);
    } else if (o.type === 'beacon') {
      const tier = BEACON_TIERS[g.beaconTier];
      const next = BEACON_TIERS[g.beaconTier + 1];
      rows.push(['Light', `${tier.light} tiles`]);
      rows.push(['Realm', `${g.realmRadius()} tiles around it`]);
      if (next) acts += `<button type="button" class="btn seal" data-act="beacon" ${g.gold < next.cost ? 'disabled' : ''}>Raise the Heartflame (${next.cost} gold)</button>`;
      else note = '<p class="note">The Heartflame burns high.</p>';
    } else if (def.sworn) {
      note = `<p class="note">${def.sworn === 'bram' ? 'Bram builds everything you place. Talk to him in Walk mode.' : 'Talk to Linnea in Walk mode.'}</p>`;
      acts += `<button type="button" class="btn" data-act="visit">${ICON.walk}Walk over and talk</button>`;
    } else if (def.light || def.lights) {
      rows.push(['Light', `${def.light || def.lights[0][2]} tiles`]);
      if (def.appeal) rows.push(['Appeal', `+${def.appeal[0]} nearby`]);
    } else if (def.appeal) {
      rows.push(['Appeal', `+${def.appeal[0]} within ${def.appeal[1]} tiles`]);
    }
    if ((def.variants || 1) > 1) acts += `<button type="button" class="btn" data-act="variant">Change style</button>`;
    if (!def.fixed) {
      acts += `<button type="button" class="btn" data-act="move">${ICON.move}Move</button>`;
      acts += `<button type="button" class="btn" data-act="remove">${ICON.remove}Remove (+${Math.floor(def.cost / 2)})</button>`;
    }
    const html = `<button type="button" class="close" data-act="deselect" aria-label="Close">${ICON.close}</button>
      <h3>${esc(def.name)}</h3><p class="sub">${esc(def.desc || '')}</p>${body}
      <div class="rows">${rows.map(([k, v]) => `<div class="row"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join('')}</div>${note}
      <div class="acts">${acts}</div>`;
    if (this.htmlCache.inspect !== html) { this.htmlCache.inspect = html; el.innerHTML = html; }
    el.hidden = false;
  }

  select(id) {
    this.state.selected = id;
    this.htmlCache.inspect = null;
    if (id) this.renderInspect();
    else this.el('inspect').hidden = true;
  }

  // ─── tools and modes ───────────────────────────────────────────────────────
  setMode(mode) {
    const rig = this.view.rig;
    this.cancelPlacing();
    this.select(null);
    this.state.mode = mode;
    if (mode === 'walk') {
      this.state.tool = 'select';
      this.el('catalog').hidden = true;
      rig.goalDist = 15;
      rig.min = 7;
      rig.max = 30;
      this.toast('Walking as the Sovereign. WASD or tap to move, E to interact.', 'info');
    } else {
      rig.min = 9;
      rig.max = 62;
      rig.goalDist = Math.max(rig.goalDist, 28);
    }
    this.refreshHud();
  }

  setTool(tool) {
    if (this.state.mode === 'walk') this.setMode('view');
    this.cancelPlacing();
    this.state.tool = tool;
    this.el('catalog').hidden = tool !== 'build';
    if (tool === 'build') this.renderCatalog();
    if (tool !== 'select') this.select(null);
    this.refreshHud();
  }

  startPlacing(type, { moving = null, rot = 0, variant = 0, goods = 'harvest' } = {}) {
    const g = this.game;
    if (!moving && !g.isUnlocked(type)) { this.toast('Not unlocked yet. Check the tasks.', 'bad'); return; }
    this.state.placing = { type, rot, variant, goods, moving, x: undefined, z: undefined, ok: false };
    this.view.overlay.setGhost(g, type, variant, goods);
    if (this.state.hoverTile) this.placeAt(...this.state.hoverTile);
    this.renderCatalog();
  }

  cancelPlacing() {
    this.state.placing = null;
    this.view.overlay.setGhost(this.game, null);
    this.el('confirm').hidden = true;
    this.renderCatalog();
  }

  placeAt(tx, tz) {
    const g = this.game;
    const p = this.state.placing;
    if (!p) return;
    const { w, d } = g.size(p.type, p.rot);
    p.x = tx - Math.floor((w - 1) / 2);
    p.z = tz - Math.floor((d - 1) / 2);
    const check = p.moving ? g.canPlace(p.type, p.x, p.z, p.rot, p.moving) : g.canPlace(p.type, p.x, p.z, p.rot);
    const cost = p.moving ? 0 : TYPES[p.type].cost;
    p.ok = check.ok && g.gold >= cost;
    p.reason = !check.ok ? check.reason : g.gold < cost ? `You need ${cost} gold.` : '';
  }

  commitPlacing() {
    const g = this.game;
    const p = this.state.placing;
    if (!p || p.x === undefined) return;
    if (!p.ok) { this.toast(p.reason || 'Can’t build there.', 'bad'); this.audio.sfx('error'); return; }
    if (p.moving) {
      if (g.move(p.moving, p.x, p.z, p.rot)) {
        this.audio.sfx('place');
        const id = p.moving;
        this.cancelPlacing();
        this.state.tool = 'select';
        this.select(id);
      } else this.toast(g.lastError, 'bad');
      return;
    }
    if (p.type === 'path') {
      if (g.paintPath(p.x, p.z)) this.audio.sfx('click');
      return;
    }
    const o = g.place(p.type, p.x, p.z, p.rot, p.variant);
    if (!o) { this.toast(g.lastError, 'bad'); this.audio.sfx('error'); return; }
    this.audio.sfx('place');
    this.dust(o);
    if (p.type === 'stall') {
      g.setStallGoods(o.id, p.goods);
      this.cancelPlacing();
      this.state.tool = 'select';
      this.el('catalog').hidden = true;
      this.select(o.id);
      this.toast('Choose what this stall sells.', 'info');
    }
    this.placeAt(p.x + Math.floor((o.w - 1) / 2), p.z + Math.floor((o.d - 1) / 2));
  }

  dust(o) {
    const cx = o.x + o.w / 2 - HALF;
    const cz = o.z + o.d / 2 - HALF;
    this.view.fx.burst(cx, 0.2, cz, { color: '#E8D8B0', n: 16, speed: 1.6, size: 0.16, life: 0.7, up: 0.6 });
  }

  // ─── clicks on the world ───────────────────────────────────────────────────
  clickWorld(e, touch) {
    const g = this.game;
    const hit = this.view.pick(e.clientX, e.clientY);
    // Tips first: they are small and float above the ground.
    const rect = this.view.renderer.domElement.getBoundingClientRect();
    for (const t of g.tips) {
      const p = this.view.project(t.x - HALF, 0.55, t.z - HALF);
      if (Math.hypot(p.x + rect.left - e.clientX, p.y + rect.top - e.clientY) < 34) {
        g.collectTip(t.id);
        return;
      }
    }
    if (!hit) return;
    const { tx, tz } = hit;
    if (this.state.mode === 'walk') {
      const o = g.objectAt(tx, tz);
      if (g.walkPlayerTo(tx, tz)) this.pending = o ? { id: o.id } : null;
      return;
    }
    const tool = this.state.tool;
    if (this.state.placing) {
      if (touch && (this.state.placing.x === undefined || this.lastTouchTile !== `${tx},${tz}`)) {
        this.placeAt(tx, tz);
        this.lastTouchTile = `${tx},${tz}`;
        this.el('confirm').hidden = false;
        return;
      }
      this.placeAt(tx, tz);
      this.commitPlacing();
      return;
    }
    const o = g.objectAt(tx, tz);
    if (tool === 'remove') {
      if (o) {
        const name = TYPES[o.type].name;
        const before = g.gold;
        if (g.remove(o.id)) { this.toast(`Removed ${name} (+${g.gold - before} gold)`, 'info'); this.audio.sfx('click'); }
        else this.toast(g.lastError, 'bad');
      } else if (g.erasePath(tx, tz)) this.audio.sfx('click');
      return;
    }
    if (tool === 'move') {
      if (o && !TYPES[o.type].fixed) this.startPlacing(o.type, { moving: o.id, rot: o.rot, variant: o.variant, goods: o.goods });
      else if (o) this.toast('That belongs to the realm. It stays.', 'bad');
      return;
    }
    this.select(o ? o.id : null);
  }

  // ─── pointer input ─────────────────────────────────────────────────────────
  onDown(e) {
    if (!this.state.started) return;
    this.view.renderer.domElement.setPointerCapture?.(e.pointerId);
    this.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (this.pointers.size === 2) {
      const [a, b] = [...this.pointers.values()];
      this.pinch = { d: Math.hypot(a.x - b.x, a.y - b.y), ang: Math.atan2(b.y - a.y, b.x - a.x), dist: this.view.rig.goalDist, yaw: this.view.rig.goalYaw };
      this.drag = null;
      return;
    }
    const p = this.state.placing;
    const painting = (p && p.type === 'path') || (this.state.tool === 'remove' && this.state.mode === 'view');
    this.drag = { id: e.pointerId, x0: e.clientX, y0: e.clientY, x: e.clientX, y: e.clientY, moved: false, rotate: e.button === 2, paint: painting && e.pointerType === 'mouse' && e.button === 0, touch: e.pointerType !== 'mouse' };
    if (this.drag.paint && p && p.type === 'path') {
      const hit = this.view.pick(e.clientX, e.clientY);
      if (hit) { this.placeAt(hit.tx, hit.tz); this.commitPlacing(); this.drag.lastTile = `${hit.tx},${hit.tz}`; this.drag.painted = true; }
    }
  }

  onMove(e) {
    if (!this.state.started) return;
    if (this.pointers.has(e.pointerId)) this.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (this.pinch && this.pointers.size >= 2) {
      const [a, b] = [...this.pointers.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      const ang = Math.atan2(b.y - a.y, b.x - a.x);
      const rig = this.view.rig;
      rig.goalDist = Math.max(rig.min, Math.min(rig.max, this.pinch.dist * (this.pinch.d / Math.max(20, d))));
      rig.goalYaw = this.pinch.yaw - (ang - this.pinch.ang);
      return;
    }
    const dr = this.drag;
    if (dr && dr.id === e.pointerId) {
      const dx = e.clientX - dr.x;
      const dy = e.clientY - dr.y;
      dr.x = e.clientX;
      dr.y = e.clientY;
      if (Math.hypot(e.clientX - dr.x0, e.clientY - dr.y0) > 7) dr.moved = true;
      if (dr.moved) {
        if (dr.rotate) this.view.rig.rotate(-dx * 0.006);
        else if (dr.paint) this.paintAlong(e);
        else if (this.state.mode === 'view' || dr.touch) {
          const rig = this.view.rig;
          const k = (2 * rig.dist * Math.tan((15 * Math.PI) / 180)) / this.view.height;
          rig.pan(-dx * k, -dy * k / Math.sin(rig.pitch));
          if (this.state.mode === 'walk') this.walkPan = true;
        }
      }
    }
    if (e.pointerType === 'mouse' || (dr && !dr.moved)) {
      const hit = this.view.pick(e.clientX, e.clientY);
      this.state.hoverTile = hit ? [hit.tx, hit.tz] : null;
      if (hit && this.state.placing && e.pointerType === 'mouse') this.placeAt(hit.tx, hit.tz);
      this.hoverTip(e);
    }
  }

  paintAlong(e) {
    const hit = this.view.pick(e.clientX, e.clientY);
    if (!hit) return;
    const key = `${hit.tx},${hit.tz}`;
    if (key === this.drag.lastTile) return;
    const [lx, lz] = this.drag.lastTile ? this.drag.lastTile.split(',').map(Number) : [hit.tx, hit.tz];
    const n = Math.max(Math.abs(hit.tx - lx), Math.abs(hit.tz - lz));
    for (let i = 1; i <= n; i++) {
      const x = Math.round(lx + ((hit.tx - lx) * i) / n);
      const z = Math.round(lz + ((hit.tz - lz) * i) / n);
      if (this.state.placing) { this.placeAt(x, z); if (this.state.placing.ok) this.commitPlacing(); } else this.game.erasePath(x, z);
    }
    this.drag.lastTile = key;
  }

  hoverTip(e) {
    const rect = this.view.renderer.domElement.getBoundingClientRect();
    const near = this.game.tips.some(t => { const p = this.view.project(t.x - HALF, 0.55, t.z - HALF); return Math.hypot(p.x + rect.left - e.clientX, p.y + rect.top - e.clientY) < 34; });
    this.view.renderer.domElement.style.cursor = near ? 'pointer' : this.state.placing ? 'crosshair' : '';
  }

  onUp(e, cancelled = false) {
    this.pointers.delete(e.pointerId);
    if (this.pinch) { if (this.pointers.size < 2) this.pinch = null; this.drag = null; return; }
    const dr = this.drag;
    if (!dr || dr.id !== e.pointerId) return;
    this.drag = null;
    if (cancelled || dr.moved || dr.painted) return;
    this.clickWorld(e, dr.touch);
  }

  onKey(e, down) {
    const k = e.key.toLowerCase();
    if (!down) { this.keys.delete(k); return; }
    if (e.target && /input|textarea|select/i.test(e.target.tagName)) return;
    if (!this.state.started) return;
    this.keys.add(k);
    const modalOpen = !this.el('modal').hidden;
    if (k === 'escape') {
      if (modalOpen && !this.game.ledger) return this.closeModal();
      if (this.app.classList.contains('photo')) return this.app.classList.remove('photo');
      if (this.state.placing) return this.cancelPlacing();
      if (this.state.selected) return this.select(null);
      if (this.state.tool !== 'select') return this.setTool('select');
      return;
    }
    if (modalOpen) return;
    if (k === 'tab' || k === 'v') { e.preventDefault(); return this.setMode(this.state.mode === 'walk' ? 'view' : 'walk'); }
    if (this.state.mode === 'walk' && (k === 'e' || k === ' ' || k === 'enter')) { e.preventDefault(); return this.doInteract(); }
    if (k === 'q' || k === 'z') return this.view.rig.rotate(Math.PI / 4);
    if ((k === 'e' && this.state.mode === 'view') || k === 'x') return this.view.rig.rotate(-Math.PI / 4);
    if (k === 'r' && this.state.placing) return this.rotatePlacing();
    if (k === 't' && this.state.placing) return this.cyclePlacingStyle();
    if (k === 'b') return this.setTool(this.state.tool === 'build' ? 'select' : 'build');
    if (k === 'p') return this.setSpeed(this.game.speed ? 0 : 1);
    if (k === '1') return this.setSpeed(1);
    if (k === '2') return this.setSpeed(2);
    if (k === '3') return this.setSpeed(4);
    if (k === 'm') return this.marketAction();
    if (k === 'h' || k === '?') return this.openHelp();
    if ((k === 'delete' || k === 'backspace') && this.state.selected) return this.removeSelected();
    if (MOVE_KEYS[k]) e.preventDefault();
  }

  rotatePlacing() {
    const p = this.state.placing;
    if (!p) return;
    p.rot = (p.rot + 1) % 4;
    if (p.x !== undefined) {
      const { w, d } = this.game.size(p.type, (p.rot + 3) % 4);
      this.placeAt(p.x + Math.floor((w - 1) / 2), p.z + Math.floor((d - 1) / 2));
    }
  }

  cyclePlacingStyle() {
    const p = this.state.placing;
    const n = TYPES[p.type].variants || 1;
    if (n < 2) return;
    p.variant = (p.variant + 1) % n;
    this.view.overlay.setGhost(this.game, p.type, p.variant, p.goods);
  }

  setSpeed(s) { this.game.speed = s; this.refreshHud(); }

  removeSelected() {
    const g = this.game;
    const o = g.objects.get(this.state.selected);
    if (!o) return;
    const before = g.gold;
    if (g.remove(o.id)) { this.toast(`Removed ${TYPES[o.type].name} (+${g.gold - before} gold)`, 'info'); this.select(null); } else this.toast(g.lastError, 'bad');
  }

  marketAction() {
    const g = this.game;
    const act = this.el('market').dataset.act;
    if (act === 'open') { if (g.openMarket()) { this.audio.sfx('bell'); this.toast('The Lantern Market is open. Travelers are on the Old Road.', 'info'); if (!g.speed) g.speed = 1; } }
    else if (act === 'close') g.closeMarket();
    else if (act === 'skip') { g.skipToDusk(); this.toast('Dusk falls over Dawnmere.', 'info'); }
    else if (act === 'sleep') g.endNight();
    else if (act === 'ledger') this.openLedger();
    this.refreshHud();
  }

  // ─── HUD buttons ───────────────────────────────────────────────────────────
  onHudClick(e) {
    const t = e.target.closest('button, [data-act]');
    if (!t || !this.hud.contains(t)) return;
    const g = this.game;
    const d = t.dataset;
    if (t.id === 'market') return this.marketAction();
    if (t.id === 'btn-book') return this.openChronicle();
    if (t.id === 'btn-help') return this.openHelp();
    if (t.id === 'btn-settings') return this.openSettings();
    if (t.id === 'btn-sound') { this.audio.toggle(); this.syncSoundButton(); return; }
    if (t.id === 'photo-exit') { this.app.classList.remove('photo'); return; }
    if (d.speed !== undefined) return this.setSpeed(Number(d.speed));
    if (d.mode) return this.setMode(d.mode);
    if (d.tool) return this.setTool(d.tool === this.state.tool && d.tool !== 'select' ? 'select' : d.tool);
    if (d.cam === 'left') return this.view.rig.rotate(Math.PI / 4);
    if (d.cam === 'right') return this.view.rig.rotate(-Math.PI / 4);
    if (d.cam === 'photo') { this.app.classList.add('photo'); this.select(null); return; }
    if (d.cat) { this.state.cat = d.cat; this.renderCatalog(); return; }
    if (d.item) {
      if (t.getAttribute('aria-disabled') === 'true') { this.toast('Not unlocked yet. Check the tasks.', 'bad'); return; }
      if (this.state.placing && this.state.placing.type === d.item) return this.cancelPlacing();
      return this.startPlacing(d.item);
    }
    if (d.confirm) {
      if (d.confirm === 'rotate') this.rotatePlacing();
      if (d.confirm === 'style') this.cyclePlacingStyle();
      if (d.confirm === 'place') this.commitPlacing();
      if (d.confirm === 'cancel') this.cancelPlacing();
      return;
    }
    if (d.modal) return this.onModal(d.modal, t);
    if (d.act) this.onAct(d.act, t);
  }

  onAct(act, t) {
    const g = this.game;
    const id = this.state.selected;
    if (act === 'tasks-toggle') { this.tasksCollapsed = !this.tasksCollapsed; this.htmlCache.tasks = null; this.renderTasks(); return; }
    if (act === 'deselect') return this.select(null);
    if (act === 'goods') { g.setStallGoods(id, t.dataset.goods); this.htmlCache.inspect = null; this.renderInspect(); return; }
    if (act === 'upgrade') { if (g.upgradeStall(id)) { this.audio.sfx('task'); } else this.toast(g.lastError, 'bad'); this.renderInspect(); return; }
    if (act === 'beacon') { if (!g.upgradeBeacon()) this.toast(g.lastError, 'bad'); this.renderInspect(); return; }
    if (act === 'variant') { const o = g.objects.get(id); g.setVariant(id, o.variant + 1); this.renderInspect(); return; }
    if (act === 'move') { const o = g.objects.get(id); this.state.tool = 'move'; this.select(null); this.startPlacing(o.type, { moving: o.id, rot: o.rot, variant: o.variant, goods: o.goods }); return; }
    if (act === 'remove') return this.removeSelected();
    if (act === 'visit') {
      const o = g.objects.get(id);
      this.setMode('walk');
      if (g.walkPlayerTo(o.x + 1, o.z + 1)) this.pending = { id: o.id };
      return;
    }
    if (act === 'interact') this.doInteract();
  }

  syncSoundButton() {
    const b = this.el('btn-sound');
    b.innerHTML = this.audio.on ? ICON.sound : ICON.mute;
    b.setAttribute('aria-label', this.audio.on ? 'Turn sound off' : 'Turn sound on');
  }

  // ─── walking ───────────────────────────────────────────────────────────────
  walkStep(dt) {
    const g = this.game;
    const rig = this.view.rig;
    if (this.state.mode === 'walk') {
      let fx = 0;
      let fz = 0;
      for (const k of this.keys) if (MOVE_KEYS[k]) { fx += MOVE_KEYS[k][0]; fz += MOVE_KEYS[k][1]; }
      if (fx || fz) {
        // forward is away from the camera; right is to the camera's right
        const s = Math.sin(rig.yaw);
        const c = Math.cos(rig.yaw);
        g.movePlayer(fx * c - fz * s, -fx * s - fz * c, dt);
        this.pending = null;
        this.walkPan = false;
      } else g.stepPlayer(dt);
      if (!this.walkPan || g.player.moving) rig.follow(g.player.x - HALF, g.player.z - HALF);
      if (this.pending && !g.player.path.length) {
        const target = g.interactables().find(a => a.id === this.pending.id && a.ready) || g.interactables().find(a => a.id === this.pending.id);
        this.pending = null;
        if (target) g.interact(target);
      }
    } else {
      let fx = 0;
      let fz = 0;
      for (const k of this.keys) if (MOVE_KEYS[k]) { fx += MOVE_KEYS[k][0]; fz += MOVE_KEYS[k][1]; }
      if (fx || fz) rig.pan(fx * dt * rig.dist * 0.9, -fz * dt * rig.dist * 0.9);
      g.stepPlayer(dt);
    }
  }

  doInteract() {
    const t = this.game.interactables()[0];
    if (t) this.game.interact(t);
  }

  renderHint() {
    const g = this.game;
    const el = this.el('hint');
    let html = '';
    let bad = false;
    const p = this.state.placing;
    if (p && p.x !== undefined && !p.ok && p.reason) { html = esc(p.reason); bad = true; }
    else if (p && p.type === 'path') html = 'Click and drag to paint paths. Right-click or Esc to stop.';
    else if (p) html = `<kbd>R</kbd> rotate${(TYPES[p.type].variants || 1) > 1 ? ' · <kbd>T</kbd> style' : ''} · click to place · <kbd>Esc</kbd> stop`;
    else if (this.state.mode === 'walk') {
      const serving = g.market.open && g.stalls().find(s => g.sovereignAt(s));
      const t = g.interactables()[0];
      if (serving) html = `Serving at the ${TYPES[serving.type].name}: customers are served twice as fast.`;
      else if (t) html = `<kbd>E</kbd> ${esc(t.label)} <button type="button" data-act="interact">Do it</button>`;
    } else if (this.state.tool === 'remove') html = 'Click something to remove it for half its cost. Drag across paths to erase them.';
    else if (this.state.tool === 'move') html = 'Click a building or prop to pick it up.';
    if (this.htmlCache.hint !== html + bad) {
      this.htmlCache.hint = html + bad;
      el.innerHTML = html;
      el.classList.toggle('bad', bad);
    }
    el.hidden = !html || !this.el('talk').hidden;
  }

  // ─── events from the simulation ────────────────────────────────────────────
  drainEvents() {
    const g = this.game;
    const events = g.events.splice(0);
    for (const e of events) {
      if (e.type === 'toast') this.toast(e.text, e.kind);
      else if (e.type === 'task') this.audio.sfx('task');
      else if (e.type === 'ledger') setTimeout(() => this.openLedger(), 400);
      else if (e.type === 'rank') setTimeout(() => this.openCelebration(), 900);
      else if (e.type === 'talk') this.showTalk(e.who, e.text);
      else if (e.type === 'sale') {
        const o = g.objects.get(e.id);
        if (o) {
          const c = { x: o.x + o.w / 2 - HALF, z: o.z + o.d / 2 - HALF };
          this.addFloat(c.x, 1.9, c.z, `+${e.price}`, ICON.gold);
          this.view.fx.burst(c.x, 1.3, c.z, { n: 8, speed: 0.8, size: 0.09, life: 0.7, up: 1.2 });
          if (this.view.time - this.saleSound > 0.25) { this.audio.sfx('coin'); this.saleSound = this.view.time; }
        }
      } else if (e.type === 'tipCollected') {
        this.addFloat(e.x - HALF, 1, e.z - HALF, `+${e.value}`, ICON.gold);
        this.view.fx.burst(e.x - HALF, 0.55, e.z - HALF, { n: 14, speed: 1.4, size: 0.1, life: 0.8, up: 1.4 });
        this.audio.sfx('tip');
      } else if (e.type === 'tend') {
        const o = g.objects.get(e.id);
        if (o) { this.addFloat(o.x + o.w / 2 - HALF, 1.1, o.z + o.d / 2 - HALF, '+3', GOODS_ICON[Object.keys(TYPES[o.type].produce)[0]], 'green'); this.view.fx.burst(o.x + o.w / 2 - HALF, 0.4, o.z + o.d / 2 - HALF, { color: '#9FE07A', n: 18, speed: 1.2, size: 0.1, life: 0.9, up: 1.5 }); }
      } else if (e.type === 'produce') {
        const o = g.objects.get(e.id);
        const rig = this.view.rig;
        if (o && GOODS_ICON[e.goods] && rig.dist < 32 && Math.hypot(o.x + o.w / 2 - HALF - rig.target.x, o.z + o.d / 2 - HALF - rig.target.z) < 12) this.addFloat(o.x + o.w / 2 - HALF, 1.4, o.z + o.d / 2 - HALF, `+${e.n}`, GOODS_ICON[e.goods], 'green');
      } else if (e.type === 'upgrade') {
        const o = g.objects.get(e.id);
        if (o) this.view.fx.burst(o.x + o.w / 2 - HALF, 1.2, o.z + o.d / 2 - HALF, { n: 30, speed: 2.2, size: 0.13, life: 1.1, up: 2 });
      } else if (e.type === 'beacon') {
        this.view.fx.burst(22 - HALF, 1.8, 14 - HALF, { n: 60, speed: 3.2, size: 0.16, life: 1.6, up: 3 });
        this.audio.sfx('bell');
      } else if (e.type === 'dawn') {
        this.toast(`Morning, day ${e.day}. ${SEASON(e.day)}.`, 'info');
        this.save();
      } else if (e.type === 'page') this.toast(`A new page in the Royal Chronicle: “${PAGES[e.id].title}”`, 'task');
    }
  }

  toast(text, kind = 'info') {
    if (!text) return;
    const box = this.el('toasts');
    const t = document.createElement('div');
    t.className = `toast ${kind}`;
    t.textContent = text;
    box.appendChild(t);
    while (box.children.length > 3) box.firstChild.remove();
    setTimeout(() => t.remove(), kind === 'task' ? 5200 : 3800);
    if (kind === 'bad') this.audio.sfx('error');
  }

  showTalk(who, text) {
    const [name, init] = WHO[who] || ['', '?'];
    const el = this.el('talk');
    el.innerHTML = `<div class="face who-${who}">${init}</div><div><b>${esc(name)}</b><p>${esc(text)}</p></div>`;
    el.hidden = false;
    this.talkTimer = 7;
    el.onclick = () => { el.hidden = true; };
  }

  // ─── bubbles and floating numbers ──────────────────────────────────────────
  addFloat(x, y, z, text, icon = '', cls = '') {
    const el = document.createElement('div');
    el.className = `float ${cls}`;
    el.innerHTML = `${icon}${esc(text)}`;
    this.el('floats').appendChild(el);
    this.floats.push({ el, x, y, z, age: 0 });
    if (this.floats.length > 24) this.floats.shift().el.remove();
  }

  updateOverlay(dt) {
    const g = this.game;
    const view = this.view;
    // floating numbers rise and fade
    this.floats = this.floats.filter(f => {
      f.age += dt;
      if (f.age > 1.4) { f.el.remove(); return false; }
      const p = view.project(f.x, f.y + f.age * 0.7, f.z);
      f.el.style.transform = `translate(${p.x}px, ${p.y}px) translate(-50%, -50%)`;
      f.el.style.opacity = String(f.age < 0.9 ? 1 : 1 - (f.age - 0.9) / 0.5);
      return true;
    });
    // speech bubbles over visitors
    const now = g.clockSec;
    const cand = [];
    for (const h of view.agents.heads()) {
      const v = h.visitor;
      if (!v || !v.bubble || v.bubble.until <= now) continue;
      const p = view.project(h.x, h.y + 0.3, h.z);
      if (p.behind || p.x < -50 || p.y < 40 || p.x > view.width + 50 || p.y > view.height) continue;
      cand.push({ id: h.id, text: v.bubble.text, p, d: Math.hypot(p.x - view.width / 2, p.y - view.height / 2) });
    }
    cand.sort((a, b) => a.d - b.d);
    const show = this.app.classList.contains('photo') ? [] : cand.slice(0, 6);
    // Nudge overlapping bubbles upward so every line stays readable.
    const placed = [];
    for (const b of show) {
      const w = Math.min(190, 7.5 * b.text.length + 22);
      let y = b.p.y;
      for (let tries = 0; tries < 6; tries++) {
        const hit = placed.find(r => Math.abs(r.x - b.p.x) < (r.w + w) / 2 && Math.abs(r.y - y) < 36);
        if (!hit) break;
        y = hit.y - 38;
      }
      placed.push({ x: b.p.x, y, w });
      b.y = y;
    }
    const box = this.el('bubbles');
    while (this.bubbleEls.length < show.length) { const el = document.createElement('div'); el.className = 'bubble'; box.appendChild(el); this.bubbleEls.push(el); }
    this.bubbleEls.forEach((el, i) => {
      const b = show[i];
      if (!b) { el.style.display = 'none'; return; }
      el.style.display = '';
      if (el.textContent !== b.text) el.textContent = b.text;
      el.style.transform = `translate(${b.p.x}px, ${b.y}px) translate(-50%, calc(-100% - 6px))`;
    });
    if (this.talkTimer > 0) { this.talkTimer -= dt; if (this.talkTimer <= 0) this.el('talk').hidden = true; }
  }

  // ─── modals ────────────────────────────────────────────────────────────────
  openModal(html) {
    const m = this.el('modal');
    m.innerHTML = html;
    m.hidden = false;
    const focus = m.querySelector('.btn.primary, .btn, button');
    if (focus) focus.focus({ preventScroll: true });
  }

  closeModal() { const m = this.el('modal'); m.hidden = true; m.innerHTML = ''; }

  onModal(act, t) {
    const g = this.game;
    if (act === 'close') return this.closeModal();
    if (act === 'sleep') { this.closeModal(); g.sleep(); return; }
    if (act === 'page') { this.openChronicle(t.dataset.page); return; }
    if (act === 'quality') { this.closeModal(); this.onQuality(t.dataset.q); return; }
    if (act === 'music') { this.audio.musicOn = !this.audio.musicOn; if (this.audio.musicOn && !this.audio.on) this.audio.start(); this.syncSoundButton(); this.openSettings(); return; }
    if (act === 'dark') { this.forceDark = !this.forceDark; this.openSettings(); return; }
    if (act === 'save') { this.save(); this.toast('Saved in this browser.', 'info'); return; }
    if (act === 'restart') { t.outerHTML = '<button type="button" class="btn seal" data-modal="restart-yes">Yes, start over</button>'; return; }
    if (act === 'restart-yes') { this.closeModal(); this.onRestart(); return; }
    if (act === 'chronicle') { this.openChronicle(); return; }
    if (act === 'skip') { this.closeModal(); this.skipDays(Number(t.dataset.days) || 3); return; }
  }

  // Let Bram run the hamlet for a few days (the same simple player the tests use).
  skipDays(n) {
    const g = this.game;
    const before = { gold: g.gold, res: g.residents.length, day: g.day };
    this.cancelPlacing();
    this.select(null);
    if (g.market.open) g.closeMarket();
    const speed = g.speed || 1;
    g.speed = 4;
    for (let i = 0; i < 20000 && (g.market.closing || (g.minute >= DUSK && !g.ledger)); i++) { if (!g.market.open && !g.market.closing) g.endNight(); else g.update(0.1); }
    if (g.ledger) g.sleep();
    for (let d = 0; d < n; d++) playDay(g);
    g.speed = speed;
    this.closeModal();
    g.events.length = 0;
    this.toast(`Bram ran the hamlet for ${g.day - before.day} days: ${g.gold - before.gold >= 0 ? '+' : ''}${g.gold - before.gold} gold, ${g.residents.length - before.res} new residents.`, 'task');
    this.save();
    this.refreshHud();
  }

  openLedger() {
    const g = this.game;
    const L = g.ledger;
    if (!L) return;
    const total = (L.happy || 0) + (L.content || 0) + (L.unhappy || 0) + (L.turnedBack || 0);
    const pct = n => (total ? (100 * (n || 0)) / total : 0);
    const sold = Object.entries(L.sold || {}).filter(([, n]) => n > 0);
    const asked = Object.entries(L.none || {}).filter(([, n]) => n > 0);
    const lines = [];
    for (const [k, n] of asked) lines.push(`${n} wanted ${GOODS[k].name.toLowerCase()} (${GOODS[k].item}), but no stall sells it.`);
    if (L.soldOut) lines.push(`${L.soldOut} found the goods they wanted sold out. Make more, or sell something else.`);
    if (L.turnedBack) lines.push(`${L.turnedBack} turned back on a dark stretch of road. Light it with Lantern Posts.`);
    const settled = L.settled || [];
    const html = L.closed ? `<div class="sheet" role="dialog" aria-labelledby="lt">
        <div class="eyebrow">Night Ledger · Day ${L.day}</div><h2 id="lt">A quiet night</h2>
        <p>The market stayed closed. The Heartflame burned on its own, and the Old Road was empty.</p>
        ${L.tipsMissed ? `<p class="note">Flicker gathered ${L.tipsMissed} gold of old tips.</p>` : ''}
        ${settled.length ? `<p><b>${esc(settled.join(', '))}</b> moved in.</p>` : ''}
        <div class="acts"><button type="button" class="btn primary" data-modal="sleep">${ICON.moon}Rest until dawn</button></div></div>`
      : `<div class="sheet" role="dialog" aria-labelledby="lt">
        <div class="eyebrow">Night Ledger · Day ${L.day}</div><h2 id="lt">The Lantern Market</h2>
        <div class="big"><div><b>+${L.revenue}</b><span>gold from sales</span></div><div><b>+${L.tips + (L.tipsMissed || 0)}</b><span>gold in tips</span></div><div><b>${L.visitors}</b><span>visitors</span></div></div>
        <h4>How they felt</h4>
        <div class="bar"><i style="width:${pct(L.happy)}%;background:#6FAF5A"></i><i style="width:${pct(L.content)}%;background:#D7B068"></i><i style="width:${pct(L.unhappy)}%;background:#C9703E"></i><i style="width:${pct(L.turnedBack)}%;background:#6B4FD8"></i></div>
        <div class="legend"><span><i style="background:#6FAF5A"></i>Happy ${L.happy}</span><span><i style="background:#D7B068"></i>Content ${L.content}</span><span><i style="background:#C9703E"></i>Unhappy ${L.unhappy}</span><span><i style="background:#6B4FD8"></i>Turned back ${L.turnedBack}</span></div>
        <h4>Sold</h4>
        <div class="soldlist">${sold.length ? sold.map(([k, n]) => `<span>${GOODS_ICON[k]}${n} ${esc(GOODS[k].item)}</span>`).join('') : '<span>Nothing sold</span>'}</div>
        ${L.bestStall ? `<p class="note">Busiest stall: the one selling ${esc(GOODS[L.bestStall.goods].name)} (${L.bestStall.sold} sales).</p>` : ''}
        ${lines.length ? `<h4>What to fix</h4><ul>${lines.map(l => `<li>${esc(l)}</li>`).join('')}</ul>` : ''}
        <h4>Who stays</h4>
        <p>${settled.length ? `<b>${esc(settled.join(', '))}</b> ${settled.length > 1 ? 'are' : 'is'} moving in.` : 'Nobody asked to stay tonight.'}
        ${L.noBed ? ` ${L.noBed} more wanted to stay, but there was no free bed. Build a Hut.` : ''}</p>
        ${L.tipsMissed ? `<p class="note">Flicker gathered the tips you missed: +${L.tipsMissed} gold.</p>` : ''}
        <div class="acts"><button type="button" class="btn primary" data-modal="sleep">${ICON.moon}Rest until dawn</button></div></div>`;
    this.openModal(html);
  }

  openChronicle(pageId) {
    const g = this.game;
    const current = pageId && g.pages.includes(pageId) ? pageId : g.pages[g.pages.length - 1];
    this.readPages.add(current);
    const page = PAGES[current];
    this.openModal(`<div class="sheet" style="width:min(760px,100%)" role="dialog" aria-labelledby="ct">
      <button type="button" class="close" data-modal="close" aria-label="Close">${ICON.close}</button>
      <div class="eyebrow">The Royal Chronicle</div>
      <div class="book"><nav aria-label="Pages">${PAGE_ORDER.map(id => g.pages.includes(id) ? `<button type="button" data-modal="page" data-page="${id}" aria-selected="${id === current}">${esc(PAGES[id].title)}</button>` : '<button type="button" disabled>Not yet written</button>').join('')}</nav>
      <article><h3 id="ct">${esc(page.title)}</h3><p>${esc(page.text)}</p></article></div></div>`);
    this.refreshHud();
  }

  openHelp() {
    this.openModal(`<div class="sheet" role="dialog" aria-labelledby="ht">
      <button type="button" class="close" data-modal="close" aria-label="Close">${ICON.close}</button>
      <div class="eyebrow">How to play</div><h2 id="ht">Kingdom View and Walk</h2>
      <p>By day, build. At dusk, open the Lantern Market. Travelers walk up the Old Road, shop at your stalls, linger where it is lovely, and leave tips. Happy ones ask to stay if there is a free bed.</p>
      <h4>Kingdom View</h4>
      <dl class="keys"><dt>Drag</dt><dd>Move the camera (two fingers to zoom and turn)</dd><dt><kbd>Wheel</kbd></dt><dd>Zoom</dd><dt><kbd>Q</kbd> <kbd>E</kbd></dt><dd>Turn the camera</dd><dt><kbd>WASD</kbd></dt><dd>Move the camera</dd><dt><kbd>B</kbd></dt><dd>Build</dd><dt><kbd>R</kbd> <kbd>T</kbd></dt><dd>Rotate, change style while placing</dd><dt><kbd>Esc</kbd></dt><dd>Stop placing, close panels</dd></dl>
      <h4>Walk as the Sovereign</h4>
      <dl class="keys"><dt><kbd>Tab</kbd></dt><dd>Switch between Kingdom View and Walk</dd><dt><kbd>WASD</kbd> or tap</dt><dd>Walk</dd><dt><kbd>E</kbd></dt><dd>Talk, tend a field (+3 once a day)</dd><dt>Stand at a stall</dt><dd>Serve twice as fast during the market</dd><dt>Flicker</dt><dd>Your light keeps the Veil off the road around you</dd></dl>
      <h4>Time</h4>
      <dl class="keys"><dt><kbd>P</kbd></dt><dd>Pause</dd><dt><kbd>1</kbd> <kbd>2</kbd> <kbd>3</kbd></dt><dd>Normal, double, fast</dd><dt><kbd>M</kbd></dt><dd>Open or close the market</dd></dl>
      <div class="acts"><button type="button" class="btn primary" data-modal="close">Got it</button></div></div>`);
  }

  openSettings() {
    const q = this.quality;
    this.openModal(`<div class="sheet" role="dialog" aria-labelledby="st">
      <button type="button" class="close" data-modal="close" aria-label="Close">${ICON.close}</button>
      <div class="eyebrow">Settings</div><h2 id="st">Kingdom View</h2>
      <h4>Graphics</h4>
      <div class="opt">${['high', 'medium', 'low'].map(k => `<button type="button" class="btn" data-modal="quality" data-q="${k}" aria-pressed="${k === q}">${k[0].toUpperCase() + k.slice(1)}</button>`).join('')}</div>
      <p class="note">Low turns off shadows, glow and the miniature blur, for older phones.</p>
      <h4>Sound</h4>
      <div class="opt"><button type="button" class="btn" data-modal="music" aria-pressed="${this.audio.musicOn}">${ICON.music}Music: ${this.audio.musicOn ? 'on' : 'off'}</button></div>
      ${this.audio.on ? `<p class="note">Now playing: ${esc(this.audio.nowPlaying())} (generated as you play).</p>` : ''}
      <h4>Help</h4>
      <div class="opt"><button type="button" class="btn" data-modal="dark" aria-pressed="${!!this.forceDark}">Always show dark road marks</button></div>
      <h4>Skip ahead</h4>
      <p class="note">Bram builds and runs the market for you (lamps, stalls, homes, decor), so you can see later days quickly.</p>
      <div class="opt"><button type="button" class="btn" data-modal="skip" data-days="2">Skip 2 days</button><button type="button" class="btn" data-modal="skip" data-days="5">Skip 5 days</button></div>
      <h4>Your save</h4>
      <p class="note">The game saves in this browser every morning.</p>
      <div class="opt"><button type="button" class="btn" data-modal="save">Save now</button><button type="button" class="btn" data-modal="restart">Start over</button></div>
      <div class="acts"><button type="button" class="btn primary" data-modal="close">Done</button></div></div>`);
  }

  openCelebration() {
    const g = this.game;
    this.view.fx.celebrate(22 - HALF, 16 - HALF);
    this.audio.sfx('bell');
    this.openModal(`<div class="sheet" role="dialog" aria-labelledby="vt">
      <div class="eyebrow">Kingdom Rank 2</div><h2 id="vt">Dawnmere is a Village</h2>
      <p>${esc(PAGES.village.text)}</p>
      <div class="big"><div><b>${g.day}</b><span>days</span></div><div><b>${g.residents.length}</b><span>residents</span></div><div><b>${g.stats.visitors}</b><span>visitors welcomed</span></div></div>
      <p class="note">That is the end of this prototype. Keep building as long as you like, and tell us how it felt.</p>
      <div class="acts"><button type="button" class="btn" data-modal="chronicle">${ICON.book}Read the Chronicle</button><button type="button" class="btn primary" data-modal="close">Keep building</button></div></div>`);
  }

  // ─── per frame ─────────────────────────────────────────────────────────────
  renderState() {
    const s = this.state;
    const g = this.game;
    return {
      mode: s.mode === 'view' && (s.tool === 'build' || s.tool === 'move') ? 'build' : s.mode,
      placing: s.placing,
      selected: s.selected,
      hoverTile: s.mode === 'view' ? s.hoverTile : null,
      showDark: s.mode === 'view' && (s.tool === 'build' || this.forceDark || !g.tasksDone.has('light_road')),
    };
  }

  tick(dt) {
    this.walkStep(dt);
    this.drainEvents();
    this.hudTimer -= dt;
    if (this.hudTimer <= 0) { this.hudTimer = 0.12; this.refreshHud(); }
    const ledgerOpen = this.game.ledger && this.el('modal').hidden;
    if (ledgerOpen && !this.ledgerQueued) { this.ledgerQueued = true; setTimeout(() => { this.ledgerQueued = false; if (this.game.ledger && this.el('modal').hidden) this.openLedger(); }, 600); }
  }
}
