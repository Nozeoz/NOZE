// Turns the GUI trees dumped by tests/engine/ui_dump.luau into HTML pages (one per screen), laid
// out by ui_layout.js the way Roblox would. Roblox's own UI is drawn as grey shapes so overlaps
// show: the top bar, then the chat and player list on a desktop, or the thumbstick and jump
// button on a phone.
//
//   node ui.mjs <ui.json> <outDir> <prefix> <width> <height> [touch] [screen ...]
//
// Use the width and height the dump was made with. FONTS=<dir> embeds web fonts close to
// Roblox's: fredoka-one-latin-400-normal.woff2, inter-latin-500-normal.woff2,
// inter-latin-700-normal.woff2 and grenze-gotisch-latin-700-normal.woff2 (from @fontsource).
// Without them the pages fall back to DejaVu, which is wider than Builder Sans.
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const here = path.dirname(fileURLToPath(import.meta.url));
const [jsonPath, outDir, prefix, W, H, mode = '', ...only] = process.argv.slice(2);
const touch = mode === 'touch';
const vw = +W;
const vh = +H;
const TOPBAR = 58;
const screens = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
const engine = fs.readFileSync(path.join(here, 'ui_layout.js'), 'utf8');

let fontFaces = '';
if (process.env.FONTS) {
  const face = (family, file, weight) => {
    const f = path.join(process.env.FONTS, file);
    if (!fs.existsSync(f)) return '';
    return `@font-face{font-family:'${family}';font-weight:${weight};src:url(data:font/woff2;base64,${fs.readFileSync(f).toString('base64')}) format('woff2')}`;
  };
  fontFaces =
    face('Fredoka One', 'fredoka-one-latin-400-normal.woff2', 400) +
    face('Inter', 'inter-latin-700-normal.woff2', 700) +
    face('Inter', 'inter-latin-500-normal.woff2', 500) +
    face('Grenze Gotisch', 'grenze-gotisch-latin-700-normal.woff2', 700);
}

const controls = touch
  ? `<div style="position:absolute;left:${Math.round(vw * 0.06)}px;bottom:${Math.round(vh * 0.08)}px;width:120px;height:120px;border-radius:50%;border:3px solid rgba(255,255,255,.55);background:rgba(0,0,0,.18)"></div>
     <div style="position:absolute;left:${vw - 95}px;top:${vh - 90}px;width:70px;height:70px;border-radius:50%;background:rgba(255,255,255,.35);border:3px solid rgba(255,255,255,.6);display:flex;align-items:center;justify-content:center;font:12px sans-serif;color:#fff">jump</div>`
  : `<div style="position:absolute;left:12px;top:${TOPBAR + 6}px;width:${Math.min(360, vw * 0.4)}px;height:${Math.min(170, vh * 0.3)}px;border-radius:10px;background:rgba(0,0,0,.28);color:#fff;font:12px sans-serif;padding:6px">chat</div>
     <div style="position:absolute;right:12px;top:${TOPBAR + 6}px;width:190px;height:104px;border-radius:10px;background:rgba(0,0,0,.28);color:#fff;font:12px sans-serif;padding:6px">player list</div>`;
const topbar = `<div style="position:absolute;left:12px;top:10px;width:40px;height:40px;border-radius:12px;background:rgba(0,0,0,.55)"></div>
  <div style="position:absolute;left:60px;top:10px;width:40px;height:40px;border-radius:12px;background:rgba(0,0,0,.55)"></div>
  <div style="position:absolute;right:12px;top:10px;width:40px;height:40px;border-radius:12px;background:rgba(0,0,0,.55)"></div>`;

fs.mkdirSync(outDir, { recursive: true });
const modes = screens.__modes || {};
const names = only.length ? only : Object.keys(screens).filter((k) => !k.startsWith('__'));
for (const name of names) {
  const guis = screens[name];
  if (!guis) throw new Error(`no screen ${name}; have ${Object.keys(screens).join(', ')}`);
  // Build mode turns the character controls off, and Roblox hides the thumbstick and jump with them
  const core = touch && modes[name] === 'build' ? '' : controls;
  const html = `<!doctype html><html><head><meta charset="utf-8"><title>loading</title>
<style>${fontFaces}html,body{margin:0;width:${vw}px;height:${vh}px;overflow:hidden;position:relative}*{box-sizing:border-box}</style></head>
<body>
<div style="position:absolute;inset:0;background:linear-gradient(180deg,#9cc3d8 0%,#cfe0ea 35%,#7fa85a 36%,#5e8a45 100%)"></div>
<div id="ui" style="position:absolute;inset:0"></div>
<div style="position:absolute;inset:0;pointer-events:none">${topbar}${core}</div>
<script>${engine}</script>
<script>
const guis = ${JSON.stringify(guis)};
document.fonts.ready.then(() => {
  window.__issues = window.layoutScreen(guis, ${vw}, ${vh}, ${TOPBAR}, document.getElementById('ui'));
  document.title = 'done';
});
</script></body></html>`;
  fs.writeFileSync(path.join(outDir, `${prefix}_${name}.html`), html);
}
console.log(`wrote ${names.length} pages to ${outDir}`);
