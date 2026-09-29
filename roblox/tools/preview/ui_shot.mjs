// Screenshots the pages ui.mjs wrote and prints any text that overflows its box.
//
//   node ui_shot.mjs <outDir> <width> <height> [page.html ...]    (default: every .html in outDir)
import fs from 'fs';
import path from 'path';
import { chromium } from 'playwright-core';

const [outDir, w, h, ...pages] = process.argv.slice(2);
const files = pages.length ? pages : fs.readdirSync(outDir).filter((f) => f.endsWith('.html'));
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM || '/opt/pw-browsers/chromium',
  args: ['--no-sandbox'],
});
const page = await browser.newPage({ viewport: { width: +w, height: +h } });
page.on('pageerror', (e) => console.log('pageerror: ' + e));
for (const f of files) {
  await page.goto('file://' + path.resolve(outDir, f));
  await page.waitForFunction(() => document.title === 'done', null, { timeout: 60000 });
  await page.screenshot({ path: path.resolve(outDir, f.replace(/\.html$/, '.png')) });
  const issues = await page.evaluate(() => window.__issues || []);
  for (const i of issues) console.log(`${f}: overflow in ${i.name} "${i.text}" box ${i.box} text ${i.text_size}`);
}
await browser.close();
