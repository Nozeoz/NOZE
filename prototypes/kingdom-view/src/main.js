// Boots the Kingdom View prototype: loads a save if there is one, builds the 3D view and the HUD,
// and runs the frame loop. Saves live in this browser only.
import { Game } from './sim/game.js';
import { View } from './render/view.js';
import { UI } from './ui/ui.js';
import { Audio } from './ui/audio.js';
import { HALF } from './render/veil.js';

const SAVE_KEY = 'kingsbloom-kingdom-view-v1';
const QUALITY_KEY = 'kingsbloom-kingdom-view-quality';

const readSave = () => { try { const s = localStorage.getItem(SAVE_KEY); return s ? JSON.parse(s) : null; } catch { return null; } };
const writeSave = game => { try { localStorage.setItem(SAVE_KEY, JSON.stringify(game.serialize())); } catch { /* storage unavailable */ } };
const clearSave = () => { try { localStorage.removeItem(SAVE_KEY); } catch { /* storage unavailable */ } };
const readQuality = () => { try { return localStorage.getItem(QUALITY_KEY); } catch { return null; } };
const writeQuality = q => { try { localStorage.setItem(QUALITY_KEY, q); } catch { /* storage unavailable */ } };

function defaultQuality() {
  const small = Math.min(window.innerWidth, window.innerHeight) < 700;
  const coarse = window.matchMedia && window.matchMedia('(pointer: coarse)').matches;
  return small || coarse ? 'medium' : 'high';
}

let app;
let scene;
let game;
let view;
let ui;
let raf = 0;
let last = 0;
let saveTimer = 45;
const audio = new Audio();

function boot(saved, { resume = false, quality } = {}) {
  quality = quality || readQuality() || defaultQuality();
  try { game = saved ? Game.load(saved) : new Game({ seed: (Math.random() * 1e9) | 0 }); } catch (e) { console.warn('Could not load the save, starting fresh.', e); game = new Game({ seed: 7 }); }
  try { view = new View(scene, game, quality); } catch (e) { console.error(e); noWebGL(); return; }
  const fresh = !saved;
  const morning = game.minute;
  if (fresh && !resume) game.minute = 18.5 * 60; // the title screen shows the clearing at dusk
  ui = new UI({
    app, view, game, audio, quality,
    hasSave: saved && !resume ? { day: game.day } : null,
    onRestart: () => { clearSave(); rebuild(null, { resume: true, quality }); },
    onQuality: q => { writeQuality(q); rebuild(game.serialize(), { resume: true, quality: q }); },
    save: () => writeSave(game),
  });
  const begin = ui.begin.bind(ui);
  ui.begin = () => { if (fresh && !resume) game.minute = morning; begin(); };
  if (resume) ui.begin();
  window.kingsbloom = { game, view, ui, skip: n => ui.skipDays(n) };
  last = performance.now();
  cancelAnimationFrame(raf);
  raf = requestAnimationFrame(loop);
}

function rebuild(saved, opts) {
  cancelAnimationFrame(raf);
  try { view.renderer.dispose(); view.renderer.forceContextLoss(); } catch { /* already gone */ }
  scene.innerHTML = '';
  app.querySelector('#hud').innerHTML = '';
  boot(saved, opts);
}

function noWebGL() {
  app.querySelector('#hud').innerHTML = `<div class="title"><div class="title-card"><h1>Kingsbloom</h1><div class="tag">Kingdom View · 3D prototype</div>
    <p class="card" style="padding:16px">This prototype needs WebGL 2, and your browser or device didn’t provide it. Try a current Chrome, Edge, Firefox or Safari, or turn on hardware acceleration.</p></div></div>`;
}

function loop(now) {
  raf = requestAnimationFrame(loop);
  const dt = Math.min(0.1, Math.max(0, (now - last) / 1000));
  last = now;
  if (!ui.state.started) view.rig.rotate(dt * 0.04);
  ui.tick(dt);
  game.update(dt);
  view.frame(game, dt, ui.renderState());
  ui.updateOverlay(dt);
  const t = view.rig.target;
  audio.update(game.nightFactor(), Math.max(0, 1 - Math.hypot(t.x - (22 - HALF), t.z - (14 - HALF)) / 12) * (view.rig.dist < 24 ? 1 : 0.4));
  saveTimer -= dt;
  if (saveTimer <= 0) {
    saveTimer = 45;
    if (ui.state.started && !game.market.open && !game.ledger) writeSave(game);
  }
}

function start(hot = {}) {
  app = document.getElementById('app');
  scene = document.getElementById('scene');
  boot(hot.save || readSave(), { resume: !!hot.save, quality: hot.quality });
  window.addEventListener('resize', () => view && view.resize());
  document.addEventListener('visibilitychange', () => { if (document.hidden && ui && ui.state.started) writeSave(game); });
  const hotApi = window.claude && window.claude.hot;
  if (hotApi && typeof hotApi.snapshot === 'function') hotApi.snapshot(() => ({ save: game && ui && ui.state.started ? game.serialize() : null, quality: view && view.qualityName }));
}

function ready() {
  const hotApi = window.claude && window.claude.hot;
  if (hotApi && typeof hotApi.ready === 'function') hotApi.ready(start);
  else start((hotApi && hotApi.data) || {});
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready);
else ready();
