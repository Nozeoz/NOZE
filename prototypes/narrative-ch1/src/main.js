// Boots the prototype page: reads the compiled Ink story embedded in the page and hands the UI a game factory.
import { Game } from './sim.js';
import { UI } from './ui.js';

function start(hotData = {}) {
  const json = document.getElementById('story-json').textContent;
  const Story = window.inkjs && window.inkjs.Story;
  if (!Story) {
    document.getElementById('stage').innerHTML = '<div class="page bg-day"><h2>The story engine didn\'t load</h2><p>This page loads inkjs from cdn.jsdelivr.net. Check your connection and reload.</p></div>';
    return;
  }
  const ui = new UI({ makeGame: seed => new Game(new Story(json), { seed }) });
  window.kingsbloom = ui;
  // When the page is republished while open, carry the current game across.
  if (hotData && hotData.save) ui.loadSave(hotData.save);
  const hot = window.claude && window.claude.hot;
  if (hot && typeof hot.snapshot === 'function') hot.snapshot(() => ({ save: ui.game ? ui.game.serialize() : null }));
}

function boot() {
  const hot = window.claude && window.claude.hot;
  if (hot && typeof hot.ready === 'function') hot.ready(start);
  else start((hot && hot.data) || {});
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
else boot();
