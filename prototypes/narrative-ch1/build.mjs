// Builds the Chapter 1 narrative prototype.
//   node build.mjs                    compile Ink → build/story.json, bundle the page → dist/index.html (self-contained, works offline)
//   node build.mjs --ink-only         compile Ink only (the tests use this)
//   node build.mjs --fragment <file>  also write the page body with inkjs loaded from a CDN (for publishing as an Artifact)
import { readFileSync, readdirSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Compiler } from 'inkjs/compiler/Compiler';
import { CompilerOptions } from 'inkjs/compiler/CompilerOptions';
import { JsonFileHandler } from 'inkjs/compiler/FileHandler/JsonFileHandler';

const HERE = dirname(fileURLToPath(import.meta.url));
const INK = join(HERE, 'ink');
const KIT = join(HERE, '..', '..', 'art', 'placeholder', 'svg');
const INKJS_CDN = 'https://cdn.jsdelivr.net/npm/inkjs@2.4.0/dist/ink.js';

function inkFiles() {
  return Object.fromEntries(readdirSync(INK).filter(f => f.endsWith('.ink')).map(f => [f, readFileSync(join(INK, f), 'utf8')]));
}

export function compileInk() {
  const files = inkFiles();
  const problems = [];
  const compiler = new Compiler(files['main.ink'], new CompilerOptions('main.ink', [], false, (msg, type) => problems.push({ msg, type }), new JsonFileHandler(files)));
  let story = null;
  try { story = compiler.Compile(); } catch (e) { problems.push({ msg: String(e), type: 2 }); }
  const errors = problems.filter(p => p.type === 2 || /ERROR/i.test(p.msg));
  const warnings = problems.filter(p => !errors.includes(p));
  if (errors.length || !story) {
    console.error(errors.map(e => e.msg).join('\n'));
    throw new Error(`Ink compile failed with ${errors.length} error(s)`);
  }
  return { json: story.ToJson(), warnings: warnings.map(w => w.msg) };
}

const { json, warnings } = compileInk();
mkdirSync(join(HERE, 'build'), { recursive: true });
writeFileSync(join(HERE, 'build', 'story.json'), json);
if (warnings.length) console.log(`Ink warnings (${warnings.length}):\n` + warnings.join('\n'));
console.log(`Compiled Ink → build/story.json (${Math.round(json.length / 1024)} KB)`);
if (process.argv.includes('--ink-only')) process.exit(0);

// ─── bundle the page
const { build } = await import('esbuild');
const out = await build({ entryPoints: [join(HERE, 'src', 'main.js')], bundle: true, format: 'iife', write: false, target: 'es2020', legalComments: 'none' });
const appJs = out.outputFiles[0].text.replace(/<\/script/gi, '<\\/script');
const css = readFileSync(join(HERE, 'src', 'style.css'), 'utf8');
const flagNames = [...new Set(Object.values(inkFiles()).flatMap(src => [...src.matchAll(/^VAR\s+(\w+)/gm)].map(m => m[1])))];
const portraits = ['chr_sovereign', 'chr_flicker', 'chr_bram', 'chr_linnea', 'chr_rook', 'chr_tamsin', 'logo_kingsbloom'];
const sprite = `<svg class="sprite" aria-hidden="true" focusable="false" width="0" height="0"><defs>${portraits.map(id => {
  const svg = readFileSync(join(KIT, `${id}.svg`), 'utf8').trim();
  const [, w, h] = svg.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/);
  return `<image id="p-${id === 'logo_kingsbloom' ? 'logo' : id}" width="${w}" height="${h}" href="data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}"/>`;
}).join('')}</defs></svg>`;

const head = `<title>Kingsbloom Chapter One</title>
<meta name="description" content="Playable narrative prototype of Kingsbloom's first chapter: days, people, choices, and a kingdom that remembers.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=IBM+Plex+Mono:wght@500;600&family=Nunito:ital,wght@0,400;0,600;0,700;0,800;1,600&display=swap">
<style>${css}</style>`;
const body = `${sprite}
<div id="app">
<header class="bar">
<button type="button" class="brand" data-do="menu" aria-label="Kingsbloom: open the menu"><svg viewBox="0 0 256 256" aria-hidden="true"><use href="#p-logo"/></svg><span><b>Kingsbloom</b><small>Chapter 1 · narrative prototype</small></span></button>
<div class="clock" id="clock"></div>
<div class="meters" id="meters"></div>
<button type="button" class="btn ghost sm menu-btn" data-do="menu">Menu</button>
</header>
<main class="layout">
<section class="stage" id="stage" aria-live="polite"></section>
<aside class="side" aria-label="Quests, realm, people, bag, log and story flags">
<div class="tabs" id="tabs" role="tablist">${['quests', 'realm', 'people', 'bag', 'log', 'flags'].map(t => `<button type="button" role="tab" data-tab="${t}" aria-selected="false">${t === 'flags' ? 'Flags' : t.charAt(0).toUpperCase() + t.slice(1)}</button>`).join('')}</div>
<div class="panel" id="panel"></div>
</aside>
</main>
<div class="toasts" id="toasts" aria-live="polite"></div>
<div class="overlay" id="overlay"></div>
</div>
<script>window.KB_FLAG_NAMES = ${JSON.stringify(flagNames)};</script>
<script type="application/json" id="story-json">${json.replace(/<\//g, '<\\/')}</script>`;

const inkjsLocal = readFileSync(join(HERE, 'node_modules', 'inkjs', 'dist', 'ink.js'), 'utf8').replace(/<\/script/gi, '<\\/script');
mkdirSync(join(HERE, 'dist'), { recursive: true });
writeFileSync(join(HERE, 'dist', 'index.html'), `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
${head}
</head>
<body>
${body}
<script>${inkjsLocal}</script>
<script>${appJs}</script>
</body>
</html>
`);
const fi = process.argv.indexOf('--fragment');
if (fi > 0) writeFileSync(process.argv[fi + 1], `${head}\n${body}\n<script src="${INKJS_CDN}"></script>\n<script>${appJs}</script>\n`);
console.log(`Wrote dist/index.html (${Math.round(readFileSync(join(HERE, 'dist', 'index.html')).length / 1024)} KB)`);
