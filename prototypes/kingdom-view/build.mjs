// Builds the Kingdom View prototype into one self-contained page.
//   node build.mjs                    → dist/index.html (works offline; three.js is bundled in)
//   node build.mjs --fragment <file>  → also the page body without <html>/<head>/<body>, for publishing as an Artifact
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';

const HERE = dirname(fileURLToPath(import.meta.url));
const out = await build({
  entryPoints: [join(HERE, 'src', 'main.js')],
  bundle: true,
  format: 'iife',
  minify: true,
  write: false,
  target: 'es2020',
  legalComments: 'none',
});
const js = out.outputFiles[0].text.replace(/<\/script/gi, '<\\/script');
const css = readFileSync(join(HERE, 'src', 'ui', 'style.css'), 'utf8');

const head = `<title>Kingsbloom Kingdom View</title>
<meta name="description" content="Playable 3D prototype of Kingsbloom's Kingdom View: build the hamlet, light the Old Road, open the Lantern Market, and walk as the Sovereign.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700&family=Nunito:wght@400;600;700;800&display=swap">
<style>${css}</style>`;
const body = `<div id="app"><div id="scene" aria-label="The clearing at Dawnmere, seen from above"></div><div id="hud"></div></div>
<script>${js}</script>`;

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
</body>
</html>
`);
console.log(`dist/index.html: ${Math.round((head.length + body.length) / 1024)} KB`);

const f = process.argv.indexOf('--fragment');
if (f > 0 && process.argv[f + 1]) {
  writeFileSync(process.argv[f + 1], `${head}\n${body}\n`);
  console.log(`fragment → ${process.argv[f + 1]}`);
}
