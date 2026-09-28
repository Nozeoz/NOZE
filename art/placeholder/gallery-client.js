// Runtime for gallery.html: Veil fog texture, the Beacon demo, and pausing off-screen animation.
(() => {
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Tileable fractal value noise, tinted from Veil violet (#6B4FD8) to Veil teal (#3FD6C6).
  function fogTexture(w, h, seed) {
    let s = seed;
    const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
    const grid = (gx, gy) => ({ gx, gy, g: Float32Array.from({ length: gx * gy }, rnd) });
    const octaves = [[grid(4, 2), 0.5], [grid(8, 4), 0.28], [grid(16, 8), 0.14], [grid(32, 16), 0.08]];
    const hue = grid(3, 2);
    const ease = t => t * t * (3 - 2 * t);
    const sample = (L, u, v) => {
      const x = u * L.gx, y = v * L.gy, x0 = Math.floor(x), y0 = Math.floor(y);
      const x1 = (x0 + 1) % L.gx, y1 = (y0 + 1) % L.gy, tx = ease(x - x0), ty = ease(y - y0);
      const top = L.g[y0 * L.gx + x0] + (L.g[y0 * L.gx + x1] - L.g[y0 * L.gx + x0]) * tx;
      const bot = L.g[y1 * L.gx + x0] + (L.g[y1 * L.gx + x1] - L.g[y1 * L.gx + x0]) * tx;
      return top + (bot - top) * ty;
    };
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    const img = ctx.createImageData(w, h);
    for (let j = 0; j < h; j++) {
      for (let i = 0; i < w; i++) {
        const u = i / w, v = j / h;
        let n = 0;
        for (const [L, amp] of octaves) n += amp * sample(L, u, v);
        const k = ease(Math.min(1, Math.max(0, sample(hue, u, v) * 1.4 - 0.2)));
        const p = (j * w + i) * 4;
        img.data[p] = 107 - 44 * k;
        img.data[p + 1] = 79 + 135 * k;
        img.data[p + 2] = 216 - 18 * k;
        img.data[p + 3] = 255 * Math.min(1, Math.max(0, (n - 0.36) * 2.3));
      }
    }
    ctx.putImageData(img, 0, 0);
    return canvas.toDataURL('image/png');
  }

  try {
    const fog = { a: fogTexture(256, 136, 7), b: fogTexture(256, 136, 23) };
    document.querySelectorAll('.fog-sheet').forEach(el => {
      el.style.backgroundImage = `url(${fog[el.dataset.fog] || fog.a})`;
    });
  } catch (e) {
    // No canvas: the pages still read fine without fog.
  }

  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver(entries => {
      entries.forEach(e => e.target.classList.toggle('offscreen', !e.isIntersecting));
    });
    document.querySelectorAll('.animated').forEach(el => io.observe(el));
  }

  // The Veil & Beacon demo.
  const frame = document.getElementById('veil-frame');
  if (!frame) return;
  const TIERS = [
    { t: 'T1', name: 'Heartflame Brazier', r: 10 },
    { t: 'T2', name: 'Beacon Tower', r: 18 },
    { t: 'T3', name: 'Great Beacon', r: 28, stand: true },
    { t: 'T4', name: 'Sunspire', r: 40, stand: true },
  ];
  const tierButtons = [...document.querySelectorAll('[data-tier]')];
  const timeButtons = [...document.querySelectorAll('[data-time]')];
  const beacons = [...frame.querySelectorAll('[data-beacon]')];
  const readout = document.getElementById('veil-readout');
  let tier = 1;
  let night = frame.classList.contains('is-night');
  let r = TIERS[tier].r;
  let raf = 0;

  const setRadius = v => {
    r = v;
    frame.style.setProperty('--r', v.toFixed(3));
  };
  const tween = to => {
    cancelAnimationFrame(raf);
    if (reduce) return setRadius(to);
    const from = r, t0 = performance.now(), dur = 900;
    const step = now => {
      const t = Math.min(1, (now - t0) / dur);
      setRadius(from + (to - from) * (1 - Math.pow(1 - t, 3)));
      if (t < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
  };
  const render = () => {
    const T = TIERS[tier];
    const area = Math.round(Math.PI * T.r * T.r).toLocaleString('en-US');
    const outside = night
      ? 'Outside the light at night: Exposure climbs +4 every 10 minutes and the Hollowed hunt.'
      : 'Outside the light by day: colour drains and Veil soil spreads. Exposure only builds in Fog weather.';
    readout.innerHTML =
      `<strong>${T.t} · ${T.name}</strong> Realm radius <strong>${T.r} tiles</strong>, about <strong>${area}</strong> tiles of safe ground.` +
      `<span>${outside}${T.stand ? ' (Drawn with the Beacon Tower placeholder.)' : ''}</span>`;
  };

  tierButtons.forEach(b => b.addEventListener('click', () => {
    tier = +b.dataset.tier;
    tierButtons.forEach(x => x.setAttribute('aria-pressed', String(x === b)));
    beacons.forEach(x => { x.style.display = +x.dataset.beacon === tier ? '' : 'none'; });
    tween(TIERS[tier].r);
    render();
  }));
  timeButtons.forEach(b => b.addEventListener('click', () => {
    night = b.dataset.time === 'night';
    frame.classList.toggle('is-night', night);
    timeButtons.forEach(x => x.setAttribute('aria-pressed', String(x === b)));
    render();
  }));
})();
