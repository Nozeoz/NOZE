// Kingsbloom Chapter 1 prototype: the page. Plain DOM, no framework.
import { NPCS, ITEMS, PHASES, DECREES, RANKS, SWORN_ORDER } from './content.js';
import { autoplay } from './autoplay.js';

const $ = (sel, root = document) => root.querySelector(sel);
const esc = s => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const store = {
  get(k) { try { return window.localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { window.localStorage.setItem(k, v); } catch { /* storage may be blocked */ } },
  del(k) { try { window.localStorage.removeItem(k); } catch { /* ignore */ } },
};
const SAVE_KEY = 'kingsbloom-ch1-save-v1';
const reduceMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
const PORTRAIT_BOX = { chr_flicker: '0 2 64 70', default: '12 6 72 72' };
const PHASE_MOOD = { Morning: 'The day is young.', Afternoon: 'The sun is high over the Vale.', Evening: 'The light is going gold.', Night: 'The Veil is rolling in.' };
const TONE_LABEL = { regal: 'Regal', warm: 'Warm', wry: 'Wry' };

const PRESETS = [
  { id: 'founding', label: 'The Founding', desc: 'Day ~10: name your kingdom and design its banner', stop: g => g.mode === 'scene' && g.scene.knot === 'mq107_founding' },
  { id: 'rook', label: "Rook's night", desc: 'The Crowfeather raid: Spare or Banish?', stop: g => g.mode === 'scene' && g.scene.knot === 'mq108_crowfeather' },
  { id: 'feast', label: 'The Founding Feast', desc: 'The end of the Vertical Slice', stop: g => g.mode === 'scene' && g.scene.knot === 'mq113_feast' },
  { id: 'court', label: 'Court Day', desc: 'Your first Court and first Royal Decree', stop: g => g.mode === 'scene' && g.scene.knot === 'mq116_court' },
];

export class UI {
  constructor({ makeGame, sprite }) {
    this.makeGame = makeGame;
    this.game = null;
    this.tab = store.get('kingsbloom-tab') || 'quests';
    this.rendered = 0;
    this.sceneKnot = null;
    this.lastFlags = {};
    this.changedFlags = new Set();
    this.recent = [];
    this.logMark = 0;
    if (sprite) document.body.insertAdjacentHTML('afterbegin', sprite);
    this.el = {
      stage: $('#stage'), panel: $('#panel'), tabs: $('#tabs'), clock: $('#clock'), meters: $('#meters'),
      toasts: $('#toasts'), overlay: $('#overlay'),
    };
    this.bind();
    this.showTitle();
  }

  // ─────────── wiring
  bind() {
    document.addEventListener('click', e => {
      const b = e.target.closest('[data-do]');
      if (!b || b.disabled) return;
      this.handle(b.dataset.do, b.dataset.arg, b);
    });
    document.addEventListener('submit', e => {
      e.preventDefault();
      const f = e.target;
      if (f.id === 'input-form') this.run(() => this.game.submitInput($('#input-value').value));
    });
    document.addEventListener('keydown', e => {
      if (!this.game || e.target.matches('input, select, textarea') || this.el.overlay.classList.contains('open')) return;
      const sc = this.game.scene;
      if (this.game.mode === 'scene' && sc?.wait?.type === 'choice' && /^[1-9]$/.test(e.key)) {
        const c = sc.choices[Number(e.key) - 1];
        if (c) { e.preventDefault(); this.run(() => this.game.choose(c.index)); }
      } else if (this.game.mode === 'scene' && sc?.wait?.type === 'end' && (e.key === 'Enter' || e.key === ' ')) {
        e.preventDefault(); this.run(() => this.game.closeScene());
      }
    });
    this.el.tabs.addEventListener('click', e => {
      const t = e.target.closest('[data-tab]');
      if (!t) return;
      this.tab = t.dataset.tab;
      store.set('kingsbloom-tab', this.tab);
      this.renderSide();
    });
  }
  handle(what, arg, el) {
    const g = this.game;
    switch (what) {
      case 'new': return this.newGame();
      case 'continue': return this.loadSave();
      case 'preset': return this.preset(arg);
      case 'menu': return this.openMenu();
      case 'close-menu': return this.closeMenu();
      case 'title': this.closeMenu(); return this.showTitle();
      case 'choose': return this.run(() => g.choose(Number(arg)));
      case 'close-scene': return this.run(() => g.closeScene());
      case 'act': return this.run(() => g.act(arg), true);
      case 'talk': return this.run(() => g.talk(arg));
      case 'gift': {
        const sel = $(`#gift-${arg}`);
        if (!sel?.value) return this.toast({ text: 'Pick something to give first.', kind: 'warn' });
        return this.run(() => g.gift(arg, sel.value));
      }
      case 'cook': return this.run(() => g.cook(arg));
      case 'eat': return this.run(() => g.eat(arg));
      case 'stock': return this.run(() => g.stock(arg, 1));
      case 'stock-all': return this.run(() => g.stock(arg, 999));
      case 'build': return this.run(() => g.build(arg));
      case 'deliver': { const [p, b] = arg.split('/'); return this.run(() => g.deliver(p, b)); }
      case 'focus': return this.run(() => g.setFocus(arg));
      case 'summon': return this.run(() => g.summon());
      case 'buy': return this.run(() => g.buy(arg, 1));
      case 'sell': return this.run(() => g.sell(arg, 1));
      case 'sell-all': return this.run(() => g.sell(arg, 999));
      case 'leave-shop': return this.run(() => g.leaveCaravan(), true);
      case 'flicker': return this.run(() => g.talk('flicker'));
      case 'banner-pick': { el.parentElement.querySelectorAll('[aria-pressed]').forEach(x => x.setAttribute('aria-pressed', 'false')); el.setAttribute('aria-pressed', 'true'); return this.previewBanner(); }
      case 'banner-done': return this.run(() => g.submitBanner(this.readBanner()));
      default: return undefined;
    }
  }
  run(fn, markLog = false) {
    try {
      if (markLog) this.logMark = this.game.s.log.length;
      fn();
    } catch (err) {
      this.toast({ text: err.message, kind: 'warn' });
    }
    this.afterChange();
  }
  afterChange() {
    const g = this.game;
    for (const n of g.takeNews()) this.toast(n);
    this.trackFlags();
    if (g.mode === 'plan' || g.mode === 'shop' || g.mode === 'ended') this.save();
    this.render();
  }

  // ─────────── game lifecycle
  newGame(seed = Math.floor(Math.random() * 1e6)) {
    this.closeMenu();
    this.game = this.makeGame(seed);
    this.resetView();
    this.game.begin();
    this.afterChange();
  }
  loadSave(raw = store.get(SAVE_KEY)) {
    if (!raw) return this.newGame();
    this.game = this.makeGame(1);
    this.resetView();
    try { this.game.load(raw); } catch { store.del(SAVE_KEY); return this.newGame(); }
    this.afterChange();
  }
  preset(id) {
    const p = PRESETS.find(x => x.id === id);
    this.closeMenu();
    this.game = this.makeGame(Math.floor(Math.random() * 1e6));
    this.resetView();
    this.game.begin();
    try { autoplay(this.game, { path: 'spare', stopWhen: p.stop }); } catch (err) { this.toast({ text: err.message, kind: 'warn' }); }
    this.game.takeNews();
    this.toast({ text: `Skipped ahead to ${p.label}: ${this.game.season} ${this.game.seasonDay}. The bot played as Aria, so everything before this point was chosen for you.`, kind: 'story' });
    this.afterChange();
  }
  resetView() { this.rendered = 0; this.sceneKnot = null; this.lastFlags = {}; this.changedFlags = new Set(); this.logMark = 0; this.el.toasts.innerHTML = ''; }
  save() { if (this.game && this.game.mode !== 'scene') store.set(SAVE_KEY, this.game.serialize()); }
  trackFlags() {
    const now = {};
    for (const name of window.KB_FLAG_NAMES || []) now[name] = this.game.v(name);
    if (Object.keys(this.lastFlags).length) {
      const changed = Object.keys(now).filter(k => now[k] !== this.lastFlags[k]);
      if (changed.length) this.changedFlags = new Set(changed);
    }
    this.lastFlags = now;
  }

  // ─────────── rendering
  render() {
    this.renderBar();
    this.renderStage();
    this.renderSide();
  }
  renderBar() {
    const g = this.game;
    if (!g) { this.el.clock.innerHTML = ''; this.el.meters.innerHTML = ''; return; }
    const s = g.s;
    const phases = PHASES.map((p, i) => `<i class="pip${i === s.phase ? ' on' : ''}${i < s.phase ? ' past' : ''}" title="${p}"></i>`).join('');
    this.el.clock.innerHTML = `<b>${g.season} ${g.seasonDay}</b><span>${g.weekday} · ${g.phaseName}</span><span class="pips" aria-hidden="true">${phases}</span>`;
    const rank = RANKS[g.rank()]?.name || '';
    this.el.meters.innerHTML =
      `<div class="meter energy" title="Energy"><span>Energy</span><i><b style="width:${s.energy}%"></b></i><em>${s.energy}</em></div>` +
      `<div class="stat" title="Gold"><span>Gold</span><b>${s.gold}</b></div>` +
      (g.flag('ch1_founded') ? `<div class="stat" title="Food Stock"><span>Food</span><b>${s.food}<small>/${g.foodCap()}</small></b></div>` : '') +
      (s.exposure > 0 ? `<div class="stat veil" title="Exposure"><span>Exposure</span><b>${s.exposure}</b></div>` : '') +
      `<div class="stat rank" title="Kingdom Rank"><span>Rank</span><b>${esc(rank)}</b></div>`;
  }
  renderStage() {
    const g = this.game;
    if (!g) return;
    if (g.mode === 'scene') return this.renderScene();
    this.sceneKnot = null;
    this.rendered = 0;
    if (g.mode === 'shop') return this.renderShop();
    if (g.mode === 'ended') return this.renderEnd();
    return this.renderPlanner();
  }

  renderScene() {
    const g = this.game, sc = g.scene;
    const dark = ['night', 'cellar'].includes(sc.bg);
    if (this.sceneKnot !== sc || !$('#lines')) {
      this.sceneKnot = sc;
      this.rendered = 0;
      this.el.stage.innerHTML = `<div class="page scene bg-${esc(sc.bg)}${dark ? ' dark' : ''}" id="page">
        <div class="scene-head"><span class="place" id="place"></span><span class="when">${g.season} ${g.seasonDay} · ${g.weekday} · ${g.phaseName}</span></div>
        <div class="lines" id="lines"></div><div class="answer" id="answer"></div></div>`;
    }
    const page = $('#page');
    page.className = `page scene bg-${sc.bg}${dark ? ' dark' : ''}`;
    $('#place').textContent = sc.place || '';
    const lines = $('#lines');
    const fresh = sc.lines.slice(this.rendered);
    fresh.forEach((line, i) => {
      const node = document.createElement('div');
      node.innerHTML = this.lineHTML(line);
      const el = node.firstElementChild;
      if (!reduceMotion()) { el.classList.add('enter'); el.style.animationDelay = `${Math.min(i, 12) * 70}ms`; }
      lines.appendChild(el);
    });
    this.rendered = sc.lines.length;
    $('#answer').innerHTML = this.answerHTML(sc);
    if (sc.wait?.type === 'banner') this.previewBanner();
    const target = $('#answer .choice, #answer input, #answer .continue');
    const last = lines.lastElementChild;
    requestAnimationFrame(() => {
      last?.scrollIntoView({ block: 'nearest', behavior: reduceMotion() ? 'auto' : 'smooth' });
      if (sc.wait?.type === 'input') $('#input-value')?.focus();
      else if (target && document.activeElement === document.body) target.focus({ preventScroll: true });
    });
  }
  lineHTML(l) {
    if (l.picked) {
      const tone = l.tone ? `<span class="tone">${TONE_LABEL[l.tone] || esc(l.tone)}</span>` : '';
      return l.speaker === 'you'
        ? `<div class="line you"><div class="bubble"><b class="who">You${tone}</b><p>${esc(l.text)}</p></div>${this.portrait('you', 'sm')}</div>`
        : `<div class="line picked"><p>${esc(l.text)}</p></div>`;
    }
    if (l.style === 'note') return `<div class="line note"><p>${esc(l.text)}</p></div>`;
    if (l.style === 'memory') return `<div class="line memory"><p>${esc(l.text)}</p></div>`;
    if (l.style === 'hymn') return `<div class="line hymn"><p>${esc(l.text)}</p></div>`;
    if (l.vs_end) return `<div class="line card-vs"><b>End of the Vertical Slice</b><p>${esc(l.text)} Everything up to here is the Vertical Slice scope. Chapter 1 carries on: two more Sworn to meet, a Court to hold, a road to open.</p></div>`;
    if (l.chapter_end) return `<div class="line card-vs"><b>${esc(l.text)}</b></div>`;
    if (l.speaker) {
      const id = l.speaker;
      const known = NPCS[id];
      const name = id === 'you' ? 'You' : known?.name || id;
      const emote = l.emote === 'heart' ? '<span class="emote" aria-hidden="true">♥</span>' : '';
      return `<div class="line say" style="--c:${known?.color || '#7A6A55'}">${this.portrait(id)}<div class="bubble"><b class="who">${esc(name)}${emote}</b><p>${esc(l.text)}</p></div></div>`;
    }
    return `<div class="line narr"><p>${esc(l.text)}</p></div>`;
  }
  portrait(id, size = '') {
    const p = NPCS[id];
    if (p?.art) {
      const box = PORTRAIT_BOX[p.art] || PORTRAIT_BOX.default;
      return `<span class="por ${size}" style="--c:${p.color}"><svg viewBox="${box}" aria-hidden="true"><use href="#p-${p.art}"/></svg></span>`;
    }
    const name = p?.name || String(id);
    return `<span class="por mono ${size}" style="--c:${p?.color || '#7A6A55'}" aria-hidden="true">${esc(name.charAt(0).toUpperCase())}</span>`;
  }
  answerHTML(sc) {
    const w = sc.wait;
    if (!w) return '';
    if (w.type === 'choice') {
      return `<div class="choices">${sc.choices.map((c, i) => `<button type="button" class="choice" data-do="choose" data-arg="${c.index}">
        <span class="key" aria-hidden="true">${i + 1}</span><span class="txt">${c.tone ? `<span class="tone">${TONE_LABEL[c.tone] || esc(c.tone)}</span>` : ''}${esc(c.text)}</span></button>`).join('')}</div>`;
    }
    if (w.type === 'input') {
      const label = w.variable === 'var_kingdom_name' ? 'Kingdom name' : 'Your name';
      return `<form class="input-row" id="input-form"><label for="input-value">${label}</label>
        <input id="input-value" maxlength="24" autocomplete="off" placeholder="${w.variable === 'var_kingdom_name' ? 'Brightwater' : 'Aria'}">
        <button type="submit" class="btn gold">Confirm</button></form>`;
    }
    if (w.type === 'banner') return this.bannerDesigner();
    if (w.type === 'end') return `<button type="button" class="btn gold continue" data-do="close-scene">Continue</button>`;
    return '';
  }

  // ─────────── banner designer (the Founding)
  bannerDesigner() {
    const fields = [['navy', '#243A6B'], ['forest', '#2F5A4A'], ['crimson', '#8E2F35'], ['plum', '#5A3A6E'], ['ochre', '#B07A1E'], ['slate', '#46505E']];
    const emblems = ['sun', 'crown', 'oak', 'flame', 'feather', 'bloom'];
    const accents = [['gold', '#E9B949'], ['silver', '#D5DAE0'], ['cream', '#F4E7C8']];
    const group = (name, list, render) => `<div class="bd-group" data-group="${name}"><span class="bd-label">${name}</span>${list.map((x, i) => render(x, i)).join('')}</div>`;
    return `<div class="banner-designer"><div class="bd-controls">
      ${group('Field', fields, ([n, c], i) => `<button type="button" class="sw" style="--c:${c}" data-do="banner-pick" data-val="${n}" data-color="${c}" aria-label="${n}" aria-pressed="${i === 0}"></button>`)}
      ${group('Emblem', emblems, (n, i) => `<button type="button" class="em" data-do="banner-pick" data-val="${n}" aria-pressed="${i === 0}">${n}</button>`)}
      ${group('Accent', accents, ([n, c], i) => `<button type="button" class="sw" style="--c:${c}" data-do="banner-pick" data-val="${n}" data-color="${c}" aria-label="${n}" aria-pressed="${i === 0}"></button>`)}
      <button type="button" class="btn gold" data-do="banner-done">Raise the banner</button></div>
      <div class="bd-preview" id="banner-preview"></div></div>`;
  }
  readBanner() {
    const get = g => $(`.bd-group[data-group="${g}"] [aria-pressed="true"]`);
    const f = get('Field'), e = get('Emblem'), a = get('Accent');
    return { field: f?.dataset.val || 'navy', fieldColor: f?.dataset.color || '#243A6B', emblem: e?.dataset.val || 'sun', accent: a?.dataset.val || 'gold', accentColor: a?.dataset.color || '#E9B949' };
  }
  previewBanner() { const box = $('#banner-preview'); if (box) box.innerHTML = bannerSVG(this.readBanner()); }

  // ─────────── the day planner
  renderPlanner() {
    const g = this.game, s = g.s;
    const acts = g.actions();
    const groups = [];
    for (const a of acts) { let grp = groups.find(x => x.name === a.group); if (!grp) groups.push(grp = { name: a.group, list: [] }); grp.list.push(a); }
    const recent = s.log.slice(this.logMark).filter(e => ['item', 'gold', 'food', 'info', 'build', 'people', 'warn'].includes(e.kind)).slice(-12);
    this.el.stage.innerHTML = `<div class="page planner bg-${g.phaseName === 'Evening' ? 'dusk' : g.phaseName === 'Morning' ? 'dawn' : 'day'}">
      <div class="plan-head"><div><h2>${g.season} ${g.seasonDay}, ${fullDay(g.weekday)}</h2><p>${g.phaseName}. ${PHASE_MOOD[g.phaseName]} What will you do?</p></div>
        <button type="button" class="btn ghost" data-do="flicker">Ask Flicker</button></div>
      ${recent.length ? `<div class="recent"><b>Since your last choice</b><ul>${recent.map(e => `<li class="k-${e.kind}">${esc(e.text)}</li>`).join('')}</ul></div>` : ''}
      <div class="groups">${groups.map(grp => `<section class="grp"><h3>${esc(grp.name)}</h3><div class="acts">${grp.list.map(a => `
        <button type="button" class="act" data-do="act" data-arg="${esc(a.id)}"${a.disabled ? ' disabled' : ''}>
          <span class="t">${esc(a.label)}</span><span class="d">${esc(a.disabled || a.desc)}</span>${a.energy ? `<span class="e">−${a.energy} energy</span>` : ''}</button>`).join('')}</div></section>`).join('')}</div>
      <p class="tip">Talking, gifts, cooking, building and stocking the stores use no time. You'll find them in the side panel.</p></div>`;
    this.logMark = s.log.length;
  }

  // ─────────── Mira's caravan
  renderShop() {
    const g = this.game;
    const buy = g.shop(), sell = g.sellable();
    this.el.stage.innerHTML = `<div class="page shop bg-day">
      <div class="plan-head"><div><h2>Mira's caravan</h2><p>Humphrey is asleep in the shafts. Mira is not. You have ${g.s.gold} gold.</p></div>
        <div class="row">${this.portrait('mira')}<button type="button" class="btn ghost" data-do="talk" data-arg="mira"${g.talkedToday('mira') ? ' disabled' : ''}>Talk</button></div></div>
      <div class="cols"><section><h3>Buy</h3><ul class="ledger">${buy.map(x => `<li><span>${esc(x.name)}</span><em>${x.price}g</em><button type="button" class="btn sm" data-do="buy" data-arg="${x.id}"${x.can ? '' : ' disabled'}>Buy</button></li>`).join('')}</ul></section>
      <section><h3>Sell</h3>${sell.length ? `<ul class="ledger">${sell.map(x => `<li><span>${esc(x.name)} <small>×${x.count}</small></span><em>${x.price}g</em><span class="row"><button type="button" class="btn sm" data-do="sell" data-arg="${x.id}">Sell 1</button><button type="button" class="btn sm" data-do="sell-all" data-arg="${x.id}">All</button></span></li>`).join('')}</ul>` : '<p class="muted">Nothing Mira wants yet. Crops, forage, ore and Veilglass all sell.</p>'}</section></div>
      <div class="row end">${this.giftRow('mira')}<button type="button" class="btn gold" data-do="leave-shop">Leave the caravan</button></div></div>`;
  }

  // ─────────── the end of the chapter
  renderEnd() {
    const g = this.game, s = g.s;
    const sworn = SWORN_ORDER.filter(id => g.flag(`npc_${id}_recruited`));
    const decree = DECREES[g.decree()]?.name || 'None';
    const choices = [
      ['Rook', g.flag('deed_spared_rook') ? `Spared (${g.v('npc_rook_trial') === 'done' ? 'joined' : 'trial'})` : 'Banished: he returns, wounded, in Chapter 2'],
      ['Reputation', cap(g.v('kingdom_reputation'))], ['First Decree', decree], ['Blossom Dance', cap(g.v('blossom_partner') || 'skipped')],
      ['Linnea on her birthday', g.flag('deed_saved_linnea_on_birthday') ? 'Saved on Spring 5' : 'Saved later'], ['Your tone', cap(g.v('var_tone'))],
    ];
    this.el.stage.innerHTML = `<div class="page end bg-dusk">
      <p class="eyebrow">Chapter 1 · Ashes and Embers</p><h2>The road north is open.</h2>
      <p>${esc(g.v('var_kingdom_name'))} became a Village on day ${s.milestones.court_held || '?'} and opened the way to Whisperwood on day ${s.day} (${g.season} ${g.seasonDay}).</p>
      ${bannerSVG(s.banner || {}, 'end-banner')}
      <dl class="facts"><div><dt>Residents</dt><dd>${g.residents()}</dd></div><div><dt>Sworn</dt><dd>${sworn.length}</dd></div><div><dt>Settlers</dt><dd>${s.settlers.length}</dd></div><div><dt>Dives</dt><dd>${s.stats.dives}</dd></div><div><dt>Thefts</dt><dd>${s.stats.thefts}</dd></div></dl>
      <h3>Choices that stuck</h3><dl class="kv">${choices.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl>
      <h3>Your people</h3><ul class="people-end">${sworn.map(id => `<li>${this.portrait(id, 'sm')}<b>${NPCS[id].name}</b>${heartsHTML(g.heartsOf(id))}</li>`).join('')}</ul>
      <div class="row"><button type="button" class="btn gold" data-do="new">Play again</button><button type="button" class="btn ghost" data-do="title">Title screen</button></div></div>`;
  }

  // ─────────── title screen
  showTitle() {
    const saved = store.get(SAVE_KEY);
    let when = '';
    if (saved) { try { const d = JSON.parse(saved).s.day; when = `Day ${d}`; } catch { when = ''; } }
    this.game = null;
    this.el.clock.innerHTML = '';
    this.el.meters.innerHTML = '';
    this.el.stage.innerHTML = `<div class="page title bg-dawn">
      <svg class="title-mark" viewBox="0 0 256 256" aria-hidden="true"><use href="#p-logo"/></svg>
      <h1>Kingsbloom</h1><p class="sub">Chapter 1 · Ashes and Embers</p>
      <p class="lede">A thousand years after your fall, you wake beside a broken throne with a talking flame for company. Survive the first night, find people worth keeping, and turn a campfire into a Village.</p>
      <div class="row">${saved ? `<button type="button" class="btn gold" data-do="continue">Continue · ${esc(when)}</button>` : ''}<button type="button" class="btn ${saved ? 'ghost' : 'gold'}" data-do="new">New game</button></div>
      <div class="skip"><b>Or skip ahead to</b><div class="row wrap">${PRESETS.map(p => `<button type="button" class="btn ghost sm" data-do="preset" data-arg="${p.id}" title="${esc(p.desc)}">${esc(p.label)}</button>`).join('')}</div></div>
      <div class="two"><section><h3>How to play</h3><ul>
        <li>Every day has a morning, an afternoon and an evening. Pick one thing to do in each; night comes on its own.</li>
        <li>Talking, gifts, cooking, building and stocking the stores use no time. They live in the side panel.</li>
        <li>Stuck? Ask Flicker. The Quests tab always shows what's next.</li></ul></section>
      <section><h3>What we're testing</h3><ul>
        <li>Does each person's purpose in the kingdom feel clear?</li><li>Is the pace of Chapter 1 right?</li>
        <li>Does sparing (or banishing) Rook feel like it matters?</li><li>Would you play one more day?</li></ul></section></div>
      <p class="fine">Narrative prototype (Step 4). Placeholder art from the in-house kit; words and systems are what's being tested. Progress saves in this browser.</p></div>`;
    this.renderSide();
  }

  // ─────────── side panel
  renderSide() {
    const g = this.game;
    this.el.tabs.querySelectorAll('[data-tab]').forEach(t => t.setAttribute('aria-selected', String(t.dataset.tab === this.tab)));
    if (!g) { this.el.panel.innerHTML = '<p class="muted pad">Start a game to see your quests, realm, people and story flags here.</p>'; return; }
    const fn = { quests: this.sideQuests, realm: this.sideRealm, people: this.sidePeople, bag: this.sideBag, log: this.sideLog, flags: this.sideFlags }[this.tab] || this.sideQuests;
    this.el.panel.innerHTML = fn.call(this);
  }
  sideQuests() {
    const g = this.game;
    let out = '';
    try { out = String(g.story.EvaluateFunction('quest_log', [], true).output || ''); } catch { out = ''; }
    const rows = out.split('\n').map(l => l.split('¦').map(x => x.trim())).filter(x => x.length === 3);
    return `<div class="pad"><div class="row between"><h3>Quests</h3><button type="button" class="btn sm ghost" data-do="flicker"${g.mode === 'plan' ? '' : ' disabled'}>Ask Flicker</button></div>
      ${rows.length ? `<ul class="quests">${rows.map(([id, title, obj]) => `<li><span class="qid${id === 'Ask' ? ' ask' : ''}">${esc(id)}</span><b>${esc(title)}</b><p>${esc(obj)}</p></li>`).join('')}</ul>` : '<p class="muted">Nothing pressing. Farm, forage, talk to people.</p>'}</div>`;
  }
  sideRealm() {
    const g = this.game, s = g.s;
    const needs = g.nextRankNeeds();
    const nextName = RANKS[g.rank() + 1]?.name;
    const builds = g.buildable();
    const projects = g.projects();
    const summonWhy = g.canSummon();
    return `<div class="pad">
      <h3>${esc(g.v('var_kingdom_name') === 'the realm' ? 'Your realm' : g.v('var_kingdom_name'))} <small>${esc(RANKS[g.rank()].name)}</small></h3>
      ${nextName ? `<div class="card"><b>Next rank: ${esc(nextName)}</b><ul class="checks">${needs.map(n => {
        const ok = n.ok ?? n.have >= n.need;
        return `<li class="${ok ? 'ok' : ''}"><span>${esc(n.label)}</span><em>${n.need ? `${n.have}/${n.need}` : ok ? 'Yes' : 'Not yet'}</em></li>`;
      }).join('')}</ul></div>` : ''}
      <div class="grid2">
        ${statBox('Food Stock', g.flag('ch1_founded') ? `${s.food}/${g.foodCap()}` : '—', g.flag('ch1_founded') ? `${g.residents()} eat a ration a day` : 'Starts at the Founding')}
        ${statBox('Joy', g.joy(), s.hungry ? 'People went hungry' : 'Food, a cook, festivals')}
        ${statBox('Safety', g.safety(), 'Beacon, reputation, decrees')}
        ${statBox('Royal Authority', `${s.ra}/${g.raCap()}`, 'Grows every day')}
        ${statBox('Beacon', `Tier ${s.beacon}`, s.beacon >= 2 ? 'Radius 18 tiles' : s.beacon ? 'Radius 10 tiles' : 'Unlit')}
        ${statBox('Beds', `${g.bedsNeeded()}/${g.beds()}`, 'Settlers need beds')}
      </div>
      ${g.flag('ch1_founded') ? `<div class="card"><b>Work orders</b><p class="muted">Settlers work on their own. Point them at food or at wood and stone.</p>
        <div class="seg"><button type="button" data-do="focus" data-arg="food" aria-pressed="${s.focus === 'food'}">Food</button><button type="button" data-do="focus" data-arg="materials" aria-pressed="${s.focus === 'materials'}">Materials</button></div>
        <div class="row between top"><span class="muted">Royal Summons: invite a settler (15 Royal Authority)</span><button type="button" class="btn sm" data-do="summon"${summonWhy || g.mode !== 'plan' ? ' disabled' : ''} title="${esc(summonWhy)}">Summon</button></div></div>` : ''}
      ${g.decree() ? `<div class="card"><b>Decree: ${esc(DECREES[g.decree()].name)}</b><p class="muted">${esc(DECREES[g.decree()].effect)}</p></div>` : ''}
      ${s.construction ? `<div class="card busy"><b>Under construction</b><p>${esc(builds.find(b => b.id === s.construction.id)?.name || s.construction.id)}: ${s.construction.daysLeft} day(s) left</p></div>` : ''}
      ${builds.length ? `<h4>Build</h4><ul class="builds">${builds.map(b => `<li><div><b>${esc(b.name)}</b>${b.count && b.repeat ? ` <small>×${b.count}</small>` : ''}<p>${esc(b.desc)}</p><p class="cost">${costText(b.cost)} · ${b.days ? `${b.days} day(s)` : 'instant'}</p></div>
        <button type="button" class="btn sm" data-do="build" data-arg="${b.id}"${b.why || g.mode !== 'plan' ? ' disabled' : ''}>${esc(b.why || 'Build')}</button></li>`).join('')}</ul>` : ''}
      ${projects.map(p => `<h4>${esc(p.name)}${p.done ? ' <small>restored</small>' : ''}</h4><ul class="builds">${p.bundles.map(b => `<li><div><b>${esc(b.name)}</b><p class="cost">${costText(b.needs)}</p></div>
        <button type="button" class="btn sm" data-do="deliver" data-arg="${p.id}/${b.id}"${b.delivered || !b.can || g.mode !== 'plan' ? ' disabled' : ''}>${b.delivered ? 'Delivered' : 'Deliver'}</button></li>`).join('')}</ul>`).join('')}
      ${s.settlers.length ? `<h4>Settlers</h4><ul class="settlers">${s.settlers.map(x => `<li><b>${esc(x.name)}</b><span>${esc(x.role)}${x.trait ? ` · ${esc(x.trait)}` : ''}</span></li>`).join('')}</ul>` : ''}
    </div>`;
  }
  sidePeople() {
    const g = this.game;
    const ids = ['bram', 'linnea', 'rook', 'tamsin', 'juniper', 'marigold', 'hob', 'mira'];
    const known = ids.filter(id => knownNPC(g, id));
    if (!known.length) return '<p class="muted pad">You haven\'t met anyone yet. Well, apart from Flicker.</p>';
    const here = new Set(g.talkable());
    return `<div class="pad"><h3>People</h3><p class="muted">Talk once a day for hearts. Two gifts a week each. Hearts open requests (3♥) and personal scenes (2♥, 4♥).</p>
      <ul class="people">${known.map(id => {
        const p = NPCS[id];
        const status = g.flag(`npc_${id}_recruited`) ? (p.sworn ? 'Sworn' : '') : id === 'hob' ? 'Settler' : id === 'mira' ? 'Tue & Fri' : g.v('deed_banished_rook') && id === 'rook' ? 'Banished' : 'Not yet joined';
        const canAct = here.has(id) && (g.mode === 'plan' || (g.mode === 'shop' && id === 'mira'));
        return `<li><div class="ph">${this.portrait(id)}<div><b>${esc(p.full || p.name)}</b><span class="role">${esc(p.role || '')}${p.building ? ` · ${esc(p.building)}` : ''}${status ? ` · ${esc(status)}` : ''}</span>${heartsHTML(g.heartsOf(id))}</div></div>
          ${p.purpose ? `<p class="purpose">${esc(p.purpose)}</p>` : ''}
          ${canAct ? `<div class="row"><button type="button" class="btn sm" data-do="talk" data-arg="${id}"${g.talkedToday(id) ? ' disabled' : ''}>${g.talkedToday(id) ? 'Talked today' : 'Talk'}</button>${this.giftRow(id)}</div>` : ''}</li>`;
      }).join('')}</ul></div>`;
  }
  giftRow(id) {
    const g = this.game;
    const items = Object.keys(g.s.inv).filter(k => g.s.inv[k] > 0 && ITEMS[k] && !ITEMS[k].key && !k.startsWith('seed_'));
    const left = g.giftsLeft(id);
    if (!items.length) return '';
    return `<span class="gift"><label class="sr" for="gift-${id}">Gift for ${esc(NPCS[id].name)}</label><select id="gift-${id}"><option value="">Gift…</option>${items.map(k => `<option value="${k}">${esc(ITEMS[k].name)} (${g.s.inv[k]})</option>`).join('')}</select>
      <button type="button" class="btn sm" data-do="gift" data-arg="${id}"${left <= 0 && !g.isBirthday(id) ? ' disabled' : ''}>Give</button><small>${g.isBirthday(id) ? 'Birthday!' : `${Math.max(0, left)} left`}</small></span>`;
  }
  sideBag() {
    const g = this.game, s = g.s;
    const inv = Object.keys(s.inv).filter(k => s.inv[k] > 0).sort();
    const recipes = g.recipes();
    const planning = g.mode === 'plan';
    return `<div class="pad"><h3>Bag</h3>
      ${inv.length ? `<ul class="bag">${inv.map(k => {
        const it = ITEMS[k] || { name: k };
        const btns = [];
        if (it.dish) btns.push(`<button type="button" class="btn sm" data-do="eat" data-arg="${k}"${planning ? '' : ' disabled'}>Eat +${it.energy}</button>`);
        if (it.ration && g.flag('ch1_founded')) btns.push(`<button type="button" class="btn sm" data-do="stock" data-arg="${k}"${planning ? '' : ' disabled'} title="Put one in the stores">Stock</button><button type="button" class="btn sm" data-do="stock-all" data-arg="${k}"${planning ? '' : ' disabled'}>All</button>`);
        return `<li><span>${esc(it.name)}</span><em>×${s.inv[k]}</em><span class="row">${btns.join('')}</span></li>`;
      }).join('')}</ul>` : '<p class="muted">Empty pockets. Go and gather something.</p>'}
      ${g.flag('ch1_campfire') ? `<h4>Cook & craft</h4><ul class="bag">${recipes.map(r => `<li><span>${esc(r.name)}</span><em>${costText(r.needs)}</em><button type="button" class="btn sm" data-do="cook" data-arg="${r.id}"${r.can && planning ? '' : ' disabled'}>Make</button></li>`).join('')}</ul>` : '<p class="muted">Light a campfire to cook.</p>'}
      <p class="muted">Power in the Cellars: ${g.power()} · Familiars: ${s.familiars}${s.copperHoe ? ' · Copper Hoe' : ''}</p></div>`;
  }
  sideLog() {
    const g = this.game;
    const rows = g.s.log.slice(-80).reverse();
    return `<div class="pad"><h3>Log</h3><ol class="log">${rows.map(e => `<li class="k-${e.kind}"><span>D${e.day} ${PHASES[e.phase]?.charAt(0) || ''}</span>${esc(e.text)}</li>`).join('')}</ol></div>`;
  }
  sideFlags() {
    const g = this.game;
    const names = window.KB_FLAG_NAMES || [];
    const groups = [['Chapter 1', 'ch1_'], ['People', 'npc_'], ['Deeds', 'deed_'], ['Kingdom & world', /^(kingdom_|world_|court_|lore_|omen_)/], ['Heart events', 'ev_'], ['Requests', 'ask_'], ['Player', /^(var_|tone_)/]];
    const used = new Set();
    const sec = groups.map(([label, m]) => {
      const list = names.filter(n => !used.has(n) && (typeof m === 'string' ? n.startsWith(m) : m.test(n)));
      list.forEach(n => used.add(n));
      return `<h4>${label}</h4><dl class="flags">${list.map(n => `<div class="${this.changedFlags.has(n) ? 'changed' : ''}"><dt>${esc(n)}</dt><dd>${esc(fmtVal(g.v(n)))}</dd></div>`).join('')}</dl>`;
    }).join('');
    return `<div class="pad"><h3>Story flags</h3><p class="muted">Every variable the Ink scripts track (docs/14 §9.4). Highlighted rows changed in the last step.</p>${sec}</div>`;
  }

  // ─────────── menu & toasts
  openMenu() {
    this.el.overlay.innerHTML = `<div class="sheet" role="dialog" aria-modal="true" aria-labelledby="menu-title"><h2 id="menu-title">Menu</h2>
      <div class="col"><button type="button" class="btn gold" data-do="new">New game</button>
      ${PRESETS.map(p => `<button type="button" class="btn ghost" data-do="preset" data-arg="${p.id}">Skip ahead: ${esc(p.label)}<small>${esc(p.desc)}</small></button>`).join('')}
      <button type="button" class="btn ghost" data-do="title">Title screen</button>
      <button type="button" class="btn ghost" data-do="close-menu">Back to the game</button></div></div>`;
    this.el.overlay.classList.add('open');
    $('.sheet .btn', this.el.overlay)?.focus();
  }
  closeMenu() { this.el.overlay.classList.remove('open'); this.el.overlay.innerHTML = ''; }
  toast(n) {
    const el = document.createElement('div');
    el.className = `toast k-${n.kind || 'info'}`;
    el.textContent = n.text;
    this.el.toasts.appendChild(el);
    while (this.el.toasts.children.length > 3) this.el.toasts.firstElementChild.remove();
    setTimeout(() => el.classList.add('out'), 4400);
    setTimeout(() => el.remove(), 5000);
  }
}

// ─────────── helpers
function knownNPC(g, id) {
  if (id === 'mira') return g.flag('npc_mira_met');
  if (id === 'hob') return g.flag('npc_hob_arrived');
  if (id === 'rook') return g.flag('npc_rook_met');
  if (id === 'tamsin') return g.flag('npc_tamsin_found');
  if (id === 'marigold') return g.flag('npc_marigold_met');
  if (id === 'juniper') return g.flag('npc_juniper_met');
  if (id === 'bram') return g.flag('npc_bram_found');
  return g.flag(`npc_${id}_recruited`);
}
function heartsHTML(n) {
  return `<span class="hearts" role="img" aria-label="${n} of 10 hearts">${Array.from({ length: 10 }, (_, i) => `<i class="${i < n ? 'on' : ''}"></i>`).join('')}</span>`;
}
function statBox(label, value, note) { return `<div class="statbox"><span>${esc(label)}</span><b>${esc(value)}</b><small>${esc(note)}</small></div>`; }
function costText(cost) {
  return Object.entries(cost).map(([k, n]) => `${n} ${k === 'gold' ? 'gold' : k === 'crop_any' ? 'crops (any)' : ITEMS[k]?.name || k}`).join(', ');
}
function fmtVal(v) { return typeof v === 'string' ? (v === '' ? '""' : v) : String(v); }
function cap(t) { t = String(t || ''); return t ? t.charAt(0).toUpperCase() + t.slice(1).replace(/_/g, ' ') : '—'; }
function fullDay(d) { return { Mon: 'Monday', Tue: 'Tuesday', Wed: 'Wednesday', Thu: 'Thursday', Fri: 'Friday', Sat: 'Saturday', Sun: 'Sunday' }[d]; }

const EMBLEMS = {
  sun: '<circle cx="50" cy="52" r="13"/><g stroke-width="5" stroke-linecap="round">' + Array.from({ length: 8 }, (_, i) => `<path d="M50 30v-8" transform="rotate(${i * 45} 50 52)"/>`).join('') + '</g>',
  crown: '<path d="M28 66V44l11 9 11-17 11 17 11-9v22Z"/>',
  oak: '<path d="M50 30c10 6 14 14 10 20 8 2 10 10 4 16-6 4-10 2-14-2-4 4-8 6-14 2-6-6-4-14 4-16-4-6 0-14 10-20Z"/><path d="M50 66v12" stroke-width="4"/>',
  flame: '<path d="M50 28c10 12 18 20 14 32-2 8-8 12-14 12s-12-4-14-12c-4-12 6-16 8-26 3 6 2 10 6 12 2-6 0-12 0-18Z"/>',
  feather: '<path d="M64 28C44 34 36 52 38 72l4 4c8-2 22-18 22-48Z"/><path d="M40 74l18-34" stroke-width="3"/>',
  bloom: '<g>' + Array.from({ length: 5 }, (_, i) => `<ellipse cx="50" cy="40" rx="7" ry="12" transform="rotate(${i * 72} 50 52)"/>`).join('') + '</g><circle cx="50" cy="52" r="5"/>',
};
export function bannerSVG(b, cls = 'banner') {
  const field = b.fieldColor || '#243A6B', accent = b.accentColor || '#E9B949';
  const emblem = EMBLEMS[b.emblem] || EMBLEMS.sun;
  return `<svg class="${cls}" viewBox="0 0 100 140" role="img" aria-label="Your banner: ${esc(b.emblem || 'sun')} on ${esc(b.field || 'navy')}">
    <path d="M10 6h80v8H10z" fill="#6B4A33"/><path d="M14 14h72v104l-36-18-36 18Z" fill="${field}" stroke="${accent}" stroke-width="3"/>
    <path d="M20 20h60v88l-30-15-30 15Z" fill="none" stroke="${accent}" stroke-width="1.5" opacity=".6"/>
    <g fill="${accent}" stroke="${accent}">${emblem}</g></svg>`;
}
