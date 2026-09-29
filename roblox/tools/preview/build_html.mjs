import fs from 'fs';
const [json, out] = process.argv.slice(2);
const data = fs.readFileSync(json, 'utf8');
const js = fs.readFileSync(new URL('./scene.bundle.js', import.meta.url), 'utf8');
fs.writeFileSync(out, `<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;overflow:hidden;background:#000}</style></head><body><script>window.DATA=${data};</script><script>${js}</script></body></html>`);
