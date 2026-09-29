// A small Roblox GUI layout engine for the browser, used by ui.mjs. It takes the ScreenGui trees
// dumped by tests/engine/ui_dump.luau and lays them out the way Roblox does, closely enough to
// catch overlaps, clipped text and things running off the screen:
//
//   * UDim2 Size and Position against the parent's content box (after UIPadding), AnchorPoint
//   * AutomaticSize from children (list, grid or free) and from text bounds
//   * UIListLayout (direction, padding, alignment, LayoutOrder) and UIGridLayout
//   * ScrollingFrame canvases (AutomaticCanvasSize) and ClipsDescendants
//   * TextScaled, TextWrapped, alignment, RichText <b>/<i>, UIStroke on text
//   * UICorner, UIStroke borders, UIGradient colour and transparency, UIScale, Rotation, ZIndex
//
// Text is measured with the page's fonts, so load them (FONTS=... in ui.mjs) for honest widths.
/* global window, document */
(function () {
  const EMOJI = "'Noto Color Emoji'";
  const FONTS = {
    FredokaOne: { family: `'Fredoka One','DejaVu Sans',${EMOJI},sans-serif`, weight: 400 },
    BuilderSansBold: { family: `'Inter','DejaVu Sans',${EMOJI},sans-serif`, weight: 700 },
    BuilderSansMedium: { family: `'Inter','DejaVu Sans',${EMOJI},sans-serif`, weight: 500 },
    GrenzeGotisch: { family: `'Grenze Gotisch','DejaVu Serif',${EMOJI},serif`, weight: 700 },
  };
  const LINE = 1.15; // line height as a multiple of TextSize

  const kids = (n) => (Array.isArray(n.children) ? n.children : []);
  const mods = (n) => {
    const m = {};
    for (const c of kids(n)) if (!c.pos) m[c.class] = c;
    return m;
  };
  const gui = (n) => kids(n).filter((c) => c.pos && c.visible !== false);
  const rgba = (c, t = 0) => `rgba(${c[0]},${c[1]},${c[2]},${Math.max(0, Math.min(1, 1 - t)).toFixed(3)})`;
  const mul = (a, b) => [Math.round((a[0] * b[0]) / 255), Math.round((a[1] * b[1]) / 255), Math.round((a[2] * b[2]) / 255)];
  const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const rich = (s) =>
    esc(s)
      .replace(/&lt;(\/?)(b|i)&gt;/g, '<$1$2>')
      .replace(/&lt;\/?font[^&]*&gt;/g, '')
      .replace(/\n/g, '<br>');

  // ─── text measurement ────────────────────────────────────────────────────
  const meter = document.createElement('div');
  meter.style.cssText = 'position:absolute;left:-10000px;top:0;visibility:hidden';
  document.body.appendChild(meter);
  function textStyle(n, size) {
    const f = FONTS[n.font] || FONTS.BuilderSansBold;
    return `font-family:${f.family};font-weight:${f.weight};font-size:${size}px;line-height:${LINE}`;
  }
  function measure(n, size, width) {
    meter.style.cssText = `position:absolute;left:-10000px;top:0;visibility:hidden;${textStyle(n, size)};` + (width != null ? `width:${Math.max(1, width)}px;white-space:normal;overflow-wrap:break-word` : 'white-space:nowrap');
    meter.innerHTML = n.rich ? rich(n.text) : esc(n.text).replace(/\n/g, '<br>');
    return { w: meter.scrollWidth, h: meter.offsetHeight };
  }
  function fitScaled(n, w, h) {
    const limit = mods(n).UITextSizeConstraint;
    let lo = 1;
    let hi = limit ? limit.maxText : 100;
    while (hi - lo > 0.5) {
      const mid = (lo + hi) / 2;
      const m = measure(n, mid, w);
      if (m.w <= w + 0.5 && m.h <= h + 0.5) lo = mid;
      else hi = mid;
    }
    return Math.floor(lo);
  }
  const hasText = (n) => n.text !== undefined && n.text !== '';

  // ─── sizing (bottom-up for AutomaticSize) ────────────────────────────────
  function padOf(n) {
    const p = mods(n).UIPadding;
    return p ? { l: p.pad[0], r: p.pad[1], t: p.pad[2], b: p.pad[3] } : { l: 0, r: 0, t: 0, b: 0 };
  }

  function size(n, pw, ph, cell) {
    const m = mods(n);
    let w = cell ? cell.w : n.size[0] * pw + n.size[1];
    let h = cell ? cell.h : n.size[2] * ph + n.size[3];
    const autoX = n.auto === 'X' || n.auto === 'XY';
    const autoY = n.auto === 'Y' || n.auto === 'XY';
    const pad = padOf(n);
    n._pad = pad;
    let cw = Math.max(0, w - pad.l - pad.r);
    let ch = Math.max(0, h - pad.t - pad.b);
    if (n.scroll) {
      // children live on the canvas: the window size, grown along the automatic axis
      n._canvas = { w: cw, h: ch };
    }
    const children = gui(n);
    const grid = m.UIGridLayout;
    for (const c of children) {
      if (grid) size(c, cw, ch, { w: grid.cell[0] * cw + grid.cell[1], h: grid.cell[2] * ch + grid.cell[3] });
      else size(c, cw, ch, null);
    }
    // text bounds
    if (hasText(n)) {
      if (n.scaled) {
        n._fs = fitScaled(n, Math.max(1, cw), Math.max(1, ch));
      } else {
        n._fs = n.textSize;
        const tb = n.wrapped && !autoX ? measure(n, n._fs, cw) : measure(n, n._fs, null);
        n._tb = tb;
        if (autoX) w = Math.max(w, tb.w + pad.l + pad.r);
        if (autoY) h = Math.max(h, tb.h + pad.t + pad.b);
      }
    }
    // content extent
    if (autoX || autoY || n.scroll) {
      const ext = extent(n, children, cw, ch);
      if (autoX) w = Math.max(w, ext.w + pad.l + pad.r);
      if (autoY) h = Math.max(h, ext.h + pad.t + pad.b);
      if (n.scroll) {
        n._canvas = {
          w: n.canvasAuto === 'X' || n.canvasAuto === 'XY' ? Math.max(cw, ext.w) : cw,
          h: n.canvasAuto === 'Y' || n.canvasAuto === 'XY' ? Math.max(ch, ext.h) : ch,
        };
      }
    }
    n._w = w;
    n._h = h;
  }

  function extent(n, children, cw, ch) {
    const m = mods(n);
    if (m.UIListLayout) {
      const l = m.UIListLayout;
      const vertical = l.dir === 'Vertical';
      let main = 0;
      let cross = 0;
      children.forEach((c, i) => {
        main += (vertical ? c._h : c._w) + (i > 0 ? l.gap : 0);
        cross = Math.max(cross, vertical ? c._w : c._h);
      });
      return vertical ? { w: cross, h: main } : { w: main, h: cross };
    }
    if (m.UIGridLayout) {
      const g = m.UIGridLayout;
      const cellW = g.cell[0] * cw + g.cell[1];
      const cellH = g.cell[2] * ch + g.cell[3];
      const padX = g.cellPad[0] * cw + g.cellPad[1];
      const padY = g.cellPad[2] * ch + g.cellPad[3];
      const perRow = Math.max(1, Math.floor((cw + padX) / (cellW + padX)));
      const rows = Math.ceil(children.length / perRow);
      return { w: Math.min(children.length, perRow) * (cellW + padX) - padX, h: rows * (cellH + padY) - padY };
    }
    let w = 0;
    let h = 0;
    for (const c of children) {
      const x = c.pos[0] * cw + c.pos[1] - c.anchor[0] * c._w;
      const y = c.pos[2] * ch + c.pos[3] - c.anchor[1] * c._h;
      w = Math.max(w, x + c._w);
      h = Math.max(h, y + c._h);
    }
    return { w, h };
  }

  // ─── placing (top-down) ──────────────────────────────────────────────────
  function place(n, x, y) {
    n._x = x;
    n._y = y;
    const m = mods(n);
    const pad = n._pad;
    const box = n._canvas || { w: n._w - pad.l - pad.r, h: n._h - pad.t - pad.b };
    const ox = pad.l;
    const oy = pad.t;
    const children = gui(n);
    if (m.UIListLayout) {
      const l = m.UIListLayout;
      const vertical = l.dir === 'Vertical';
      const sorted = [...children].sort((a, b) => (a.order || 0) - (b.order || 0));
      const ext = extent(n, sorted, box.w, box.h);
      const total = vertical ? ext.h : ext.w;
      const room = vertical ? box.h : box.w;
      const mainAlign = vertical ? l.va : l.ha;
      let cursor = mainAlign === 'Center' ? (room - total) / 2 : mainAlign === 'Right' || mainAlign === 'Bottom' ? room - total : 0;
      for (const c of sorted) {
        const crossAlign = vertical ? l.ha : l.va;
        const crossRoom = vertical ? box.w : box.h;
        const crossSize = vertical ? c._w : c._h;
        const cross = crossAlign === 'Center' ? (crossRoom - crossSize) / 2 : crossAlign === 'Right' || crossAlign === 'Bottom' ? crossRoom - crossSize : 0;
        if (vertical) place(c, ox + cross, oy + cursor);
        else place(c, ox + cursor, oy + cross);
        cursor += (vertical ? c._h : c._w) + l.gap;
      }
    } else if (m.UIGridLayout) {
      const g = m.UIGridLayout;
      const cellW = g.cell[0] * box.w + g.cell[1];
      const cellH = g.cell[2] * box.h + g.cell[3];
      const padX = g.cellPad[0] * box.w + g.cellPad[1];
      const padY = g.cellPad[2] * box.h + g.cellPad[3];
      const perRow = Math.max(1, Math.floor((box.w + padX) / (cellW + padX)));
      const sorted = [...children].sort((a, b) => (a.order || 0) - (b.order || 0));
      sorted.forEach((c, i) => place(c, ox + (i % perRow) * (cellW + padX), oy + Math.floor(i / perRow) * (cellH + padY)));
    } else {
      for (const c of children) {
        place(c, ox + c.pos[0] * box.w + c.pos[1] - c.anchor[0] * c._w, oy + c.pos[2] * box.h + c.pos[3] - c.anchor[1] * c._h);
      }
    }
  }

  // ─── drawing ─────────────────────────────────────────────────────────────
  const issues = [];
  function draw(n, parentEl) {
    const m = mods(n);
    const el = document.createElement('div');
    el.dataset.name = n.name;
    const st = [`position:absolute`, `left:${n._x}px`, `top:${n._y}px`, `width:${n._w}px`, `height:${n._h}px`];
    const tr = [];
    if (n.rot) tr.push(`rotate(${n.rot}deg)`);
    if (m.UIScale && m.UIScale.scale !== 1) tr.push(`scale(${m.UIScale.scale})`);
    if (tr.length) st.push(`transform:${tr.join(' ')}`, `transform-origin:${n.anchor[0] * 100}% ${n.anchor[1] * 100}%`);
    if (n.bgT < 1) {
      const g = m.UIGradient;
      if (g) {
        const a = rgba(mul(n.bg, g.from), 1 - (1 - n.bgT) * (1 - (g.tFrom || 0)));
        const b = rgba(mul(n.bg, g.to), 1 - (1 - n.bgT) * (1 - (g.tTo || 0)));
        st.push(`background:linear-gradient(${(g.rotation || 0) + 90}deg, ${a}, ${b})`);
      } else st.push(`background:${rgba(n.bg, n.bgT)}`);
    }
    if (m.UICorner) {
      const r = m.UICorner.radius;
      const s = Math.min(n._w, n._h);
      st.push(`border-radius:${Math.min(s / 2, r[0] * s + r[1])}px`);
    }
    const border = kids(n).find((c) => c.class === 'UIStroke' && c.mode !== 'Contextual');
    if (border && border.t < 1 && border.thickness > 0) st.push(`box-shadow:0 0 0 ${border.thickness}px ${rgba(border.color, border.t)}`);
    if (n.scroll || n.clips) st.push('overflow:hidden');
    el.style.cssText = st.join(';');
    if (hasText(n)) {
      const t = document.createElement('div');
      const pad = n._pad;
      const ts = [
        'position:absolute',
        `left:${pad.l}px`,
        `top:${pad.t}px`,
        `width:${n._w - pad.l - pad.r}px`,
        `height:${n._h - pad.t - pad.b}px`,
        textStyle(n, n._fs),
        `color:${rgba(n.textColor, n.textT)}`,
        'display:flex',
        `align-items:${n.ya === 'Top' ? 'flex-start' : n.ya === 'Bottom' ? 'flex-end' : 'center'}`,
        `justify-content:${n.xa === 'Left' ? 'flex-start' : n.xa === 'Right' ? 'flex-end' : 'center'}`,
        `text-align:${(n.xa || 'Center').toLowerCase()}`,
        n.wrapped || n.scaled ? 'white-space:normal;overflow-wrap:break-word' : 'white-space:nowrap',
      ];
      const stroke = kids(n).find((c) => c.class === 'UIStroke' && c.mode === 'Contextual');
      if (stroke && stroke.t < 1) ts.push(`-webkit-text-stroke:${stroke.thickness * 2}px ${rgba(stroke.color, stroke.t)}`, 'paint-order:stroke fill');
      t.style.cssText = ts.join(';');
      const span = document.createElement('span');
      span.innerHTML = n.rich ? rich(n.text) : esc(n.text).replace(/\n/g, '<br>');
      t.appendChild(span);
      el.appendChild(t);
      // overflow check: text taller or wider than its box
      if (!n.scaled && n.textT < 1) {
        const bw = n._w - pad.l - pad.r;
        const bh = n._h - pad.t - pad.b;
        const tb = n.wrapped ? measure(n, n._fs, bw) : measure(n, n._fs, null);
        if (tb.h > bh + 2 || (!n.wrapped && tb.w > bw + 2)) issues.push({ name: n.name, text: n.text.slice(0, 60), box: [Math.round(bw), Math.round(bh)], text_size: [tb.w, tb.h] });
      }
    }
    const sorted = gui(n)
      .map((c, i) => [c, i])
      .sort((a, b) => (a[0].z || 1) - (b[0].z || 1) || a[1] - b[1])
      .map((p) => p[0]);
    const holder = n._canvas ? document.createElement('div') : el;
    if (n._canvas) {
      holder.style.cssText = `position:absolute;left:0;top:0;width:${n._canvas.w}px;height:${n._canvas.h}px`;
      el.appendChild(holder);
    }
    for (const c of sorted) draw(c, holder);
    parentEl.appendChild(el);
  }

  window.layoutScreen = function (guis, vw, vh, topbar, root) {
    const sorted = [...guis].sort((a, b) => (a.order || 0) - (b.order || 0));
    for (const g of sorted) {
      if (g.enabled === false) continue;
      const m = mods(g);
      const s = m.UIScale ? m.UIScale.scale : 1;
      const top = g.ignoreInset || g.insets === 'None' ? 0 : topbar;
      const w = vw / s;
      const h = (vh - top) / s;
      const layer = document.createElement('div');
      layer.dataset.gui = g.name;
      layer.style.cssText = `position:absolute;left:0;top:${top}px;width:${w}px;height:${h}px;transform:scale(${s});transform-origin:0 0`;
      const children = gui(g);
      for (const c of children) {
        size(c, w, h, null);
        place(c, c.pos[0] * w + c.pos[1] - c.anchor[0] * c._w, c.pos[2] * h + c.pos[3] - c.anchor[1] * c._h);
      }
      const byZ = children
        .map((c, i) => [c, i])
        .sort((a, b) => (a[0].z || 1) - (b[0].z || 1) || a[1] - b[1])
        .map((p) => p[0]);
      for (const c of byZ) draw(c, layer);
      root.appendChild(layer);
    }
    return issues;
  };
})();
