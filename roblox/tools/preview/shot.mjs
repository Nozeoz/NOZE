// Screenshots a preview page:  node shot.mjs <page.html> <out.png> "view=close" [width] [height]
// Views: overview, plot, close, road, hub, cat1..cat5, hearts, actors, actors2 (add &night=1 for night).
import { chromium } from 'playwright-core';
const [file, out, query = '', w = '1280', h = '800'] = process.argv.slice(2);
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM || '/opt/pw-browsers/chromium',
  args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
});
const page = await browser.newPage({ viewport: { width: +w, height: +h } });
page.on('pageerror', (e) => console.log('pageerror: ' + e));
await page.goto('file://' + file + (query ? '?' + query : ''));
await page.waitForFunction(() => document.title.startsWith('done'), null, { timeout: 120000 });
await page.screenshot({ path: out });
await browser.close();
