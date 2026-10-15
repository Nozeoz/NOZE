"use strict";
/* NOZE web UI — vanilla JS, no build step. All user/remote text goes through
   textContent/setAttribute (never innerHTML) so saved content can't inject HTML. */
(() => {
  // ------------------------------------------------------------------ helpers
  const $ = (sel, el = document) => el.querySelector(sel);

  // Only http(s) links and our own paths may end up in href/src (no javascript:/data: URLs from saved content).
  const safeUrl = (u) => (typeof u === "string" && /^(https?:\/\/|\/(?!\/)|#\/)/i.test(u.trim()) ? u.trim() : "");
  const URL_ATTRS = new Set(["href", "src", "poster"]);  // iframes only get allow-listed player URLs (see mediaFor)

  function h(tag, props, ...children) {
    const el = document.createElement(tag);
    if (props) {
      for (const [k, v] of Object.entries(props)) {
        if (v === undefined || v === null || v === false) continue;
        if (URL_ATTRS.has(k)) {
          const u = safeUrl(String(v));
          if (u) el.setAttribute(k, u);
          continue;
        }
        if (k === "class") el.className = v;
        else if (k === "text") el.textContent = v;
        else if (k === "style") Object.assign(el.style, v);
        else if (k === "dataset") Object.assign(el.dataset, v);
        else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
        else if (k === "html") el.innerHTML = v; // only ever used with static, trusted markup (icons)
        else el.setAttribute(k, v === true ? "" : v);
      }
    }
    for (const c of children.flat()) {
      if (c === null || c === undefined || c === false) continue;
      el.append(c instanceof Node ? c : document.createTextNode(String(c)));
    }
    return el;
  }

  const ICONS = {
    image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m21 16-5-5-9 9"/>',
    video: '<rect x="2" y="5" width="15" height="14" rx="2"/><path d="m17 10 5-3v10l-5-3"/>',
    gif: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M8 10h-1.5a1.5 1.5 0 0 0 0 4H8v-2M11 10v4M14 14v-4h2.5M14 12h2"/>',
    motion: '<path d="M4 17c3 0 4-10 8-10s5 10 8 10"/><circle cx="12" cy="7" r="1.5"/>',
    audio: '<path d="M3 12h2M7 8v8M11 5v14M15 9v6M19 7v10M21 12h0"/>',
    "3d": '<path d="m12 2 9 5v10l-9 5-9-5V7z"/><path d="m3 7 9 5 9-5M12 12v10"/>',
    texture: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18M15 3v18"/>',
    hdri: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
    icon: '<path d="m12 3 2.6 5.6 6.1.7-4.5 4.2 1.2 6L12 16.6 6.6 19.5l1.2-6L3.3 9.3l6.1-.7z"/>',
    font: '<path d="M4 20 10 4h1l6 16M6.5 14h8M16 20h4"/>',
    code: '<path d="m8 8-5 4 5 4M16 8l5 4-5 4M14 4l-4 16"/>',
    template: '<path d="m12 3 9 5-9 5-9-5z"/><path d="m3 13 9 5 9-5"/>',
    link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    ext: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    down: '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
    x: '<path d="M6 6l12 12M18 6 6 18"/>',
    more: '<path d="M11 5l7 7-7 7M4 12h13"/>',
    play: '<path d="M8 5v14l11-7z" fill="currentColor"/>',
    pause: '<path d="M7 5h3v14H7zM14 5h3v14h-3z" fill="currentColor"/>',
    eyeoff: '<path d="M3 3l18 18M10.6 5.1A10 10 0 0 1 12 5c5 0 9 4.5 10 7a13 13 0 0 1-3 4.3M6.6 6.6C4.4 8 2.8 10 2 12c1 2.5 5 7 10 7 1.6 0 3.1-.4 4.4-1.1M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
    copy: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>',
    spark: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
  };
  const icon = (name, size = 16) =>
    h("span", { style: { display: "inline-flex" }, "aria-hidden": "true",
      html: `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ICONS.image}</svg>` });

  const USAGE = {
    free: ["Free", "Free to use — commercial OK, no credit required"],
    credit: ["Credit", "Commercial OK, but you must credit the creator"],
    noncommercial: ["Non-comm.", "Non-commercial use only"],
    reference: ["Ref only", "Reference/inspiration only — rights belong to the creator"],
    check: ["Check", "License unclear — check the source page before publishing"],
    own: ["Mine", "Your own asset"],
  };
  const KIND_LABEL = { image: "Image", video: "Video", gif: "GIF", motion: "Lottie", audio: "Audio", "3d": "3D",
    texture: "Texture", hdri: "HDRI", icon: "Icon", font: "Font", code: "Code", template: "Template", link: "Link" };
  const DEFAULT_RATIO = { font: 0.62, audio: 0.5, icon: 1, code: 0.5, link: 0.72, hdri: 0.5, "3d": 1, texture: 1, motion: 1 };

  const store = {
    get(k, d) { try { const v = localStorage.getItem("noze." + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v) { try { localStorage.setItem("noze." + k, JSON.stringify(v)); } catch { /* private mode */ } },
  };

  async function request(method, path, body, isForm) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
      if (isForm) opts.body = body;
      else { opts.body = JSON.stringify(body); opts.headers["Content-Type"] = "application/json"; }
    }
    const res = await fetch(path, opts);
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch { data = text; }
    if (!res.ok) {
      const detail = data && data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : res.statusText;
      throw new Error(detail || `HTTP ${res.status}`);
    }
    return data;
  }
  const api = {
    get: (path, params) => {
      const qs = params ? "?" + new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v !== undefined && v !== null)) : "";
      return request("GET", path + qs);
    },
    post: (path, body) => request("POST", path, body ?? {}),
    form: (path, fd) => request("POST", path, fd, true),
    patch: (path, body) => request("PATCH", path, body),
    del: (path) => request("DELETE", path),
  };
  const enc = encodeURIComponent;

  function toast(msg, err = false) {
    const t = h("div", { class: "toast" + (err ? " err" : ""), text: msg });
    $("#toasts").append(t);
    setTimeout(() => t.remove(), err ? 5200 : 2600);
  }

  const fmtDur = (s) => { if (!s && s !== 0) return ""; s = Math.round(s); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
  const fmtBytes = (n) => { n = n || 0; const u = ["B", "KB", "MB", "GB", "TB"]; let i = 0; while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; } return (i ? n.toFixed(1) : n) + " " + u[i]; };
  const plural = (n, word) => `${(n || 0).toLocaleString()} ${word}${n === 1 ? "" : "s"}`;
  const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
  const isTouch = matchMedia("(hover: none)").matches;

  // ------------------------------------------------------------------ theme
  const applyTheme = () => {
    const t = store.get("theme", "auto");
    if (t === "auto") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", t);
  };
  applyTheme();

  // ------------------------------------------------------------------ filters
  // "@inspiration" = visual mood-board mode (images, video, GIFs, links, textures); the query can still
  // ask for fonts/icons/sfx/lottie by name ("font retro", "whoosh sfx").
  const KIND_CHIPS = [
    ["@inspiration", "Inspiration"], ["", "Everything"], ["video,gif,motion", "Motion"], ["video", "Video"], ["motion", "Lottie"], ["gif", "GIF"],
    ["image", "Image"], ["icon", "Icon"], ["font", "Font"], ["texture", "Texture"], ["hdri", "HDRI"],
    ["3d", "3D"], ["audio", "Audio / SFX"], ["code,template", "Code & templates"],
  ];
  const filters = {
    kinds: "@inspiration",
    usage: store.get("usage", ""),
    sources: store.get("sources", ""),
    color: "",
    live: store.get("live", true),
  };
  let sourceList = [];

  function renderFilters() {
    const bar = $("#filters");
    bar.replaceChildren();
    for (const [value, label] of KIND_CHIPS) {
      bar.append(h("button", {
        class: "chip" + (filters.kinds === value ? " on" : ""), text: label, type: "button",
        onclick: () => { filters.kinds = value; renderFilters(); refreshView(); },
      }));
    }
    bar.append(h("span", { class: "sep" }));
    const usage = h("select", { class: "select", title: "What you're allowed to do with it",
      onchange: (e) => { filters.usage = e.target.value; store.set("usage", filters.usage); refreshView(); } },
      h("option", { value: "" }, "Any license"),
      h("option", { value: "usable" }, "✓ Usable commercially"),
      h("option", { value: "free" }, "✓ Free, no credit needed"),
      h("option", { value: "reference" }, "Reference only"));
    usage.value = filters.usage;
    bar.append(usage);
    const src = h("select", { class: "select", title: "Limit to one source",
      onchange: (e) => { filters.sources = e.target.value; store.set("sources", filters.sources); refreshView(); } },
      h("option", { value: "" }, "All sources"),
      ...sourceList.filter((s) => s.enabled).map((s) => h("option", { value: s.name }, s.label)));
    src.value = filters.sources;
    bar.append(src);
    const colorInput = h("input", { type: "color", value: filters.color || "#ff5a36", title: "Search by color",
      onchange: (e) => { filters.color = e.target.value; renderFilters(); refreshView(); } });
    const dot = h("span", { class: "swatch-dot", style: filters.color ? { background: filters.color } : {} });
    bar.append(h("label", { class: "chip color-pick" + (filters.color ? " on" : ""), title: "Search by color" }, dot, filters.color ? filters.color : "Color", colorInput));
    if (filters.color) bar.append(h("button", { class: "chip", type: "button", text: "✕ color", onclick: () => { filters.color = ""; renderFilters(); refreshView(); } }));
    bar.append(h("span", { class: "sep" }));
    const live = h("input", { type: "checkbox", onchange: (e) => { filters.live = e.target.checked; store.set("live", filters.live); } });
    live.checked = !!filters.live;
    bar.append(h("label", { class: "toggle", title: "Also ask the live sources (otherwise only your bank)" }, live, "Live sources"));
  }

  const filterParams = () => (filters.kinds === "@inspiration"
    ? { mode: "inspiration", usage: filters.usage, sources: filters.sources }
    : { kinds: filters.kinds, usage: filters.usage, sources: filters.sources });

  // ------------------------------------------------------------------ masonry grid + infinite feed
  class Masonry {
    constructor(el) {
      this.el = el;
      this.items = [];
      this.cols = [];
      this.heights = [];
      this.n = 0;
      this.ro = new ResizeObserver(debounce(() => this.layout(), 120));
      this.ro.observe(el);
    }
    columnsFor(width) {
      const min = width < 520 ? 150 : width < 900 ? 190 : 236;
      return Math.max(2, Math.floor((width + 16) / (min + 16)));
    }
    layout(force) {
      const width = this.el.clientWidth || window.innerWidth;
      const n = this.columnsFor(width);
      if (n === this.n && !force) return;
      this.n = n;
      this.cols = Array.from({ length: n }, () => h("div", { class: "col" }));
      this.heights = new Array(n).fill(0);
      this.el.replaceChildren(...this.cols);
      for (const it of this.items) this.place(it);
    }
    place(it) {
      let j = 0;
      for (let i = 1; i < this.n; i++) if (this.heights[i] < this.heights[j] - 1) j = i;
      this.cols[j].append(it.el);
      this.heights[j] += it.ratio + 0.28;
    }
    add(el, ratio) {
      const it = { el, ratio };
      this.items.push(it);
      if (!this.n) this.layout(true); else this.place(it);
    }
    remove(el) {
      this.items = this.items.filter((i) => i.el !== el);
      el.remove();
    }
    destroy() { this.ro.disconnect(); }
  }

  class Feed {
    constructor(container, loader, { empty, onPage } = {}) {
      this.loader = loader;
      this.onPage = onPage;
      this.emptyEl = empty;
      this.page = 0;
      this.more = true;
      this.busy = false;
      this.seen = new Set();
      this.gridEl = h("div", { class: "grid" });
      this.spin = h("div", { class: "loading" }, h("div", { class: "spinner" }));
      this.sentinel = h("div", { class: "sentinel" });
      container.append(this.gridEl, this.spin, this.sentinel);
      this.grid = new Masonry(this.gridEl);
      this.io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) this.next(); }, { rootMargin: "1400px" });
      this.io.observe(this.sentinel);
      this.next();
    }
    async next() {
      if (this.busy || !this.more) return;
      this.busy = true;
      this.spin.classList.remove("hidden");
      try {
        const res = await this.loader(this.page + 1);
        this.page += 1;
        const fresh = (res.items || []).filter((it) => !this.seen.has(it.id));
        fresh.forEach((it) => { this.seen.add(it.id); this.grid.add(card(it, this), ratioOf(it)); });
        this.more = !!res.has_more && (fresh.length > 0 || this.page < 3);
        if (this.onPage) this.onPage(res, this.page);
        if (this.page === 1 && this.seen.size === 0 && this.emptyEl) this.gridEl.replaceWith(this.emptyEl);
      } catch (e) {
        this.more = false;
        toast(e.message, true);
      } finally {
        this.busy = false;
        this.spin.classList.toggle("hidden", !this.more);
        if (this.more && this.sentinel.getBoundingClientRect().top < window.innerHeight + 1400) setTimeout(() => this.next(), 50);
      }
    }
    removeId(id) {
      const el = this.gridEl.querySelector(`[data-id="${CSS.escape(id)}"]`);
      if (el) this.grid.remove(el);
    }
    destroy() { this.io.disconnect(); this.grid.destroy(); }
  }

  function ratioOf(it) {
    let r = it.width && it.height ? it.height / it.width : DEFAULT_RATIO[it.kind] || 0.8;
    if (it.kind === "icon") r = 1;
    return Math.min(2.0, Math.max(0.42, r));
  }

  // ------------------------------------------------------------------ cards
  let currentAudio = null;
  const fontCache = new Map();
  function loadFont(it) {
    if (!it.preview_url || !window.FontFace) return "";
    const family = "nz-" + it.id.replace(/[^a-z0-9]/gi, "");
    if (!fontCache.has(family)) {
      const ff = new FontFace(family, `url(${JSON.stringify(it.preview_url)})`);
      fontCache.set(family, ff.load().then((f) => { document.fonts.add(f); return f; }).catch(() => null));
    }
    return family;
  }

  function thumbImg(it, cls) {
    const img = h("img", { class: cls || "", alt: it.title || "", loading: "lazy", decoding: "async", referrerpolicy: "no-referrer" });
    let triedLocal = false;
    img.addEventListener("error", () => {
      if (!triedLocal && !it.thumb.startsWith("/api/thumb/")) { triedLocal = true; img.src = "/api/thumb/" + enc(it.id); }
      else img.replaceWith(h("div", { class: "ph" }, icon(it.kind, 28)));
    });
    img.src = it.thumb || "/api/thumb/" + enc(it.id);
    return img;
  }

  function usageBadge(usage, withText = true) {
    const [label, tip] = USAGE[usage] || USAGE.check;
    return h("span", { class: "badge", title: tip }, h("span", { class: "u u-" + (usage || "check") }), withText ? label : null);
  }

  function hoverPreview(media, it) {
    if (isTouch) return;
    let timer = null;
    let node = null;
    const src = it.kind === "video" ? it.preview_url
      : it.kind === "gif" ? (it.video || it.preview_url)
      : it.kind === "motion" ? (it.video || "") : "";
    media.addEventListener("mouseenter", () => {
      timer = setTimeout(() => {
        if (src && /\.(mp4|webm|mov)(\?|$)|\/file$|mp4/i.test(src)) {
          node = h("video", { src, muted: true, loop: true, playsinline: true, autoplay: true, style: { position: "absolute", inset: "0" } });
          node.muted = true;
          node.addEventListener("error", () => node && node.remove());
          media.append(node);
        } else if (src && /\.gif(\?|$)/i.test(src)) {
          node = h("img", { src, referrerpolicy: "no-referrer", style: { position: "absolute", inset: "0" } });
          media.append(node);
        } else if (it.kind === "motion" && it.preview_url && window.lottie) {
          node = h("div", { style: { position: "absolute", inset: "0", background: "var(--tile)" } });
          media.append(node);
          try { node._anim = window.lottie.loadAnimation({ container: node, renderer: "svg", loop: true, autoplay: true, path: it.preview_url }); } catch { /* ignore */ }
        }
      }, 220);
    });
    media.addEventListener("mouseleave", () => {
      clearTimeout(timer);
      if (node) { if (node._anim) node._anim.destroy(); node.remove(); node = null; }
    });
  }

  function card(it, feed) {
    const ratio = ratioOf(it);
    const media = h("div", { class: "media" + (it.kind === "icon" ? " icon-tile" : ""), style: { aspectRatio: `1 / ${ratio}` } });
    if (it.kind === "font") {
      const family = loadFont(it);
      media.append(h("div", { class: "specimen", style: { fontFamily: `"${family}", var(--font)` } }, it.title || "Aa", h("small", { text: "Aa Bb Cc 0123" })));
    } else if (it.kind === "audio") {
      const bg = h("div", { class: "audio-bg" });
      if (it.thumb) bg.append(thumbImg(it));
      const btn = h("button", { class: "round play", title: "Play preview", onclick: (e) => {
        e.stopPropagation();
        if (currentAudio && currentAudio._id === it.id) { currentAudio.pause(); currentAudio = null; btn.replaceChildren(icon("play", 20)); return; }
        if (currentAudio) { currentAudio.pause(); if (currentAudio._btn) currentAudio._btn.replaceChildren(icon("play", 20)); }
        currentAudio = new Audio(it.preview_url);
        currentAudio._id = it.id; currentAudio._btn = btn;
        currentAudio.play().catch(() => toast("Can't play this preview", true));
        currentAudio.addEventListener("ended", () => btn.replaceChildren(icon("play", 20)));
        btn.replaceChildren(icon("pause", 20));
      } }, icon("play", 20));
      media.append(bg, btn);
    } else if (it.thumb || it.kind !== "link") {
      media.append(thumbImg(it));
    } else {
      media.append(h("div", { class: "ph" }, icon("link", 28)));
    }
    const badges = h("div", { class: "badges" });
    if (it.kind !== "image") badges.append(h("span", { class: "badge" }, icon(it.kind, 12), KIND_LABEL[it.kind] || it.kind));
    media.append(badges);
    if (it.duration) media.append(h("span", { class: "badge dur", text: fmtDur(it.duration) }));
    const saveBtn = h("button", { class: "save-btn" + (it.saved ? " saved" : ""), text: it.saved ? "Saved" : "Save", type: "button",
      onclick: (e) => { e.stopPropagation(); boardPicker(saveBtn, it, () => { it.saved = true; saveBtn.textContent = "Saved"; saveBtn.classList.add("saved"); }); } });
    const overlay = h("div", { class: "overlay" }, saveBtn,
      h("div", { class: "corner" }, usageBadge(it.usage)),
      h("div", { class: "corner-r" },
        it.page_url ? h("a", { class: "round", href: it.page_url, target: "_blank", rel: "noopener noreferrer", title: "Open on " + it.source_label, onclick: (e) => e.stopPropagation() }, icon("ext")) : null,
        h("button", { class: "round", title: "More like this", type: "button", onclick: (e) => { e.stopPropagation(); location.hash = "#/a/" + enc(it.id) + "?more=1"; } }, icon("more"))));
    media.append(overlay);
    hoverPreview(media, it);
    const el = h("div", { class: "card", tabindex: "0", dataset: { id: it.id }, role: "button", "aria-label": it.title || KIND_LABEL[it.kind],
      onclick: () => { location.hash = "#/a/" + enc(it.id); },
      onkeydown: (e) => { if (e.key === "Enter") location.hash = "#/a/" + enc(it.id); } },
      media,
      h("div", { class: "meta" },
        it.title ? h("div", { class: "title", text: it.title }) : null,
        h("div", { class: "sub", text: [it.source_label, it.author].filter(Boolean).join(" · ") })));
    el._feed = feed;
    return el;
  }

  // ------------------------------------------------------------------ board picker
  let boardsCache = null;
  async function getBoards(force) {
    if (!boardsCache || force) boardsCache = await api.get("/api/boards");
    return boardsCache;
  }

  async function saveTo(it, board) {
    if (board.id) await api.post(`/api/boards/${board.id}/items`, { asset_id: it.id });
    else await api.post("/api/save", { asset_id: it.id, board: board.name });
    store.set("lastBoard", board.name);
    boardsCache = null;
    toast(`Saved to “${board.name}” · downloading to your bank`);
  }

  let openPop = null;
  function closePop() { if (openPop) { openPop.remove(); openPop = null; } }
  document.addEventListener("click", (e) => { if (openPop && !openPop.contains(e.target)) closePop(); }, true);

  async function boardPicker(anchor, it, done) {
    closePop();
    const pop = h("div", { class: "pop", onclick: (e) => e.stopPropagation() });
    openPop = pop;
    const r = anchor.getBoundingClientRect();
    const left = Math.min(window.innerWidth - 300, Math.max(8, r.right - 290));
    const top = r.bottom + 440 > window.innerHeight ? Math.max(8, r.top - 430) : r.bottom + 8;
    Object.assign(pop.style, { left: left + "px", top: top + "px" });
    const list = h("div", { class: "list" });
    const input = h("input", { placeholder: "New board name…", maxlength: "120" });
    const create = async () => {
      const name = input.value.trim();
      if (!name) return;
      try { await saveTo(it, { name }); done && done(); closePop(); } catch (err) { toast(err.message, true); }
    };
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") create(); });
    pop.append(h("header", { text: "Save to board" }), list, h("div", { class: "new" }, input, h("button", { class: "btn primary small", text: "Create", onclick: create })));
    document.body.append(pop);
    input.focus();
    let boards = [];
    try { boards = await getBoards(); } catch (err) { toast(err.message, true); }
    const last = store.get("lastBoard", "Saved");
    boards = [...boards].sort((a, b) => (b.name === last) - (a.name === last));
    if (!boards.length) boards = [{ name: "Saved", covers: [] }];
    for (const b of boards) {
      const cover = (b.covers || [])[0];
      list.append(h("button", { class: "item", onclick: async () => {
        try { await saveTo(it, b); done && done(); closePop(); } catch (err) { toast(err.message, true); }
      } }, h("span", { class: "thumb" }, cover && cover.thumb ? h("img", { src: cover.thumb, alt: "", referrerpolicy: "no-referrer" }) : null),
        h("span", null, h("b", { text: b.name }), h("div", { class: "muted", text: plural(b.count, "item") }))));
    }
  }

  // ------------------------------------------------------------------ views
  const view = $("#view");
  let currentFeed = null;
  let baseRoute = "#/";

  function setNav(name) {
    document.querySelectorAll("[data-nav]").forEach((a) => a.classList.toggle("active", a.dataset.nav === name));
  }

  function resetView() {
    if (currentFeed) currentFeed.destroy();
    currentFeed = null;
    view.replaceChildren();
    window.scrollTo(0, 0);
  }

  function renderHome() {
    resetView();
    setNav("home");
    $("#q").value = "";
    const info = h("div", { class: "info-line" });
    view.append(info);
    const empty = h("div", { class: "empty" },
      h("h3", { text: "Your bank is empty — let's fill it" }),
      h("p", { text: "Search any vibe above (sources are searched live and everything found is kept), or add the starter pack of ~50 motion & design topics that keeps growing on its own." }),
      h("button", { class: "btn primary", text: "Add starter pack", onclick: async () => {
        await api.post("/api/interests/starter"); toast("Crawling ~50 topics in the background — refresh in a minute");
      } }));
    currentFeed = new Feed(view, (page) => api.get("/api/feed", { ...filterParams(), page }), {
      empty,
      onPage: (res, page) => {
        if (page === 1) info.replaceChildren(h("span", null, h("b", { text: "For you" }), ` · ${res.total} items in your bank · learns from what you open and save`));
      },
    });
  }

  function renderSearch(q) {
    resetView();
    setNav("");
    $("#q").value = q;
    const info = h("div", { class: "info-line" });
    view.append(info);
    const empty = h("div", { class: "empty" }, h("h3", { text: "Nothing yet" }),
      h("p", { text: "Try other words, remove filters, or turn on Live sources. Sources without API keys are listed under Bank." }));
    let startedAt = Date.now();
    currentFeed = new Feed(view, (page) => api.get("/api/search", { q, ...filterParams(), color: filters.color, page, live: filters.live ? 1 : 0 }), {
      empty,
      onPage: (res, page) => {
        if (page !== 1) return;
        info.replaceChildren();
        const qd = res.query || {};
        info.append(h("span", null, h("b", { text: `${res.total}` }), " results"));
        if (qd.translated && qd.text) info.append(h("span", { class: "muted", text: `· searching as “${qd.text}”` }));
        const ap = qd.applied || {};
        if (ap.kinds) info.append(h("span", { class: "chip on vibe", text: `only ${ap.kinds.join(", ")}` }));
        if (ap.usage) info.append(h("span", { class: "chip on vibe", text: ap.usage === "free" ? "no-credit only" : "usable only" }));
        if (res.live) {
          const st = res.live.sources || {};
          const vals = Object.values(st);
          const ok = vals.filter((v) => v.startsWith("ok") || v === "cached").length;
          const errs = Object.entries(st).filter(([, v]) => v.startsWith("error"));
          const pending = res.live.pending || [];
          const tip = Object.entries(st).map(([k, v]) => `${k}: ${v}`).join("\n");
          info.append(h("span", { class: "live", title: tip },
            h("span", { class: "pulse" + (pending.length ? " busy" : "") }),
            `${ok}/${vals.length} sources · +${res.live.new_items} new${errs.length ? ` · ${errs.length} failed` : ""} · ${((Date.now() - startedAt) / 1000).toFixed(1)}s`));
          if (pending.length) {
            info.append(h("button", { class: "chip", text: `↻ ${pending.length} slow source${pending.length > 1 ? "s" : ""} still loading`, onclick: () => renderSearch(q) }));
          }
        }
        for (const v of qd.vibes || []) {
          info.append(h("button", { class: "chip vibe", text: v, title: "Add this vibe", onclick: () => go(`${q} ${v}`) }));
        }
      },
    });
  }

  async function renderBoards() {
    resetView();
    setNav("boards");
    view.append(h("h1", { class: "page-title", text: "Boards" }), h("p", { class: "page-sub", text: "Everything you save is downloaded into your bank, so it stays yours even if the source disappears." }));
    const grid = h("div", { class: "boards" });
    view.append(grid);
    let boards = [];
    try { boards = await getBoards(true); } catch (e) { toast(e.message, true); }
    if (!boards.length) {
      view.append(h("div", { class: "empty" }, h("h3", { text: "No boards yet" }), h("p", { text: "Hover anything and press Save." })));
      return;
    }
    for (const b of boards) {
      const covers = b.covers || [];
      const cover = h("div", { class: "board-cover" }, ...[0, 1, 2].map((i) => h("div", null, covers[i] ? h("img", { src: covers[i].thumb || "/api/thumb/" + enc(covers[i].id), alt: "", loading: "lazy", referrerpolicy: "no-referrer" }) : null)));
      grid.append(h("div", { class: "board-card", onclick: () => { location.hash = "#/b/" + b.id; } }, cover,
        h("h3", { text: b.name }), h("p", { text: plural(b.count, "item") })));
    }
  }

  async function renderBoard(id) {
    resetView();
    setNav("boards");
    let board;
    try { board = await api.get(`/api/boards/${id}`, { per_page: 1 }); } catch (e) { toast(e.message, true); return; }
    const title = h("h1", { class: "page-title", text: board.name });
    const actions = h("div", { class: "actions", style: { marginBottom: "16px" } },
      h("a", { class: "btn primary", href: `/api/boards/${id}/export`, title: "Zip with files + CREDITS.txt" }, icon("down"), "Export pack (.zip)"),
      h("button", { class: "btn", text: "Rename", onclick: async () => {
        const name = prompt("Board name", board.name);
        if (name && name.trim()) { await api.patch(`/api/boards/${id}`, { name: name.trim() }); boardsCache = null; renderBoard(id); }
      } }),
      h("button", { class: "btn ghost", text: "Delete board", onclick: async () => {
        if (confirm(`Delete “${board.name}”? Items stay in your bank.`)) { await api.del(`/api/boards/${id}`); boardsCache = null; location.hash = "#/boards"; }
      } }));
    view.append(title, h("p", { class: "page-sub", text: `${plural(board.total, "item")} · export gives you a zip with every stored file and a CREDITS.txt grouped by license` }), actions);
    currentFeed = new Feed(view, (page) => api.get(`/api/boards/${id}`, { page }), {
      empty: h("div", { class: "empty" }, h("h3", { text: "Empty board" })),
    });
  }

  // ------------------------------------------------------------------ detail overlay
  let detailEl = null;
  let detailFeed = null;
  function closeDetail() {
    if (detailFeed) { detailFeed.destroy(); detailFeed = null; }
    if (detailEl) { detailEl.remove(); detailEl = null; document.body.style.overflow = ""; }
    if (currentAudio) { currentAudio.pause(); currentAudio = null; }
  }

  function mediaFor(a) {
    const box = h("div", { class: "detail-media" });
    const file = a.file_url && a.blob_mime ? a.file_url : "";
    const k = a.kind;
    const embed = a.extra && a.extra.embed;
    if (embed && /^https:\/\/(player\.vimeo\.com|www\.youtube-nocookie\.com)\//.test(embed)) {
      box.append(h("iframe", { src: embed, allow: "autoplay; fullscreen; picture-in-picture", allowfullscreen: true,
        style: { width: "100%", aspectRatio: "16 / 9", border: "0" }, title: a.title || "video" }));
    } else if (k === "video" || (k === "gif" && (a.video || /\.mp4/i.test(a.preview_url)))) {
      const src = (file && /^video\//.test(a.blob_mime)) ? file : (k === "gif" ? (a.video || a.preview_url) : a.preview_url);
      box.append(h("video", { src, poster: a.thumb || "", controls: true, autoplay: true, muted: true, loop: true, playsinline: true }));
    } else if (k === "audio") {
      box.append(h("div", { class: "audio-box" }, a.thumb ? h("img", { src: a.thumb, alt: "waveform", referrerpolicy: "no-referrer" }) : null,
        h("audio", { src: file || a.preview_url, controls: true, preload: "none" })));
    } else if (k === "font") {
      const family = loadFont(a);
      const weights = (a.extra && a.extra.weights) || [];
      box.classList.add("light");
      box.append(h("div", { class: "font-box", style: { fontFamily: `"${family}", var(--font)` } },
        h("div", { contenteditable: "true", spellcheck: "false", text: a.title || "The quick brown fox" }),
        h("div", { text: "ABCDEFGHIJKLMNOPQRSTUVWXYZ abcdefghijklmnopqrstuvwxyz 0123456789 !?&", style: { fontSize: "20px" } }),
        h("div", { class: "weights" }, ...weights.map((w) => h("span", { class: "tag", text: String(w) })))));
    } else if (k === "motion") {
      box.classList.add("light");
      const holder = h("div", { class: "lottie" });
      box.append(holder);
      if (window.lottie && a.preview_url) {
        try { window.lottie.loadAnimation({ container: holder, renderer: "svg", loop: true, autoplay: true, path: file || a.preview_url }); }
        catch { holder.replaceWith(h("img", { src: a.thumb, alt: "" })); }
      } else if (a.video) {
        holder.replaceWith(h("video", { src: a.video, autoplay: true, muted: true, loop: true, playsinline: true }));
      }
    } else if (k === "icon") {
      box.classList.add("light");
      box.append(h("img", { src: a.preview_url || a.thumb, alt: a.title, style: { width: "min(360px, 70%)", padding: "30px" }, referrerpolicy: "no-referrer" }));
    } else {
      const src = (file && /^image\//.test(a.blob_mime)) ? file : (a.preview_url && !/\.(zip|json|glb|gltf|hdr|exr)(\?|$)/i.test(a.preview_url) && k !== "link" && k !== "code" ? a.preview_url : a.thumb);
      // show the cached thumbnail instantly, swap in the big version once it has loaded
      const img = h("img", { src: a.thumb || src, alt: a.title, referrerpolicy: "no-referrer" });
      const big = src && src !== a.thumb ? safeUrl(src) : "";
      if (big) {
        const pre = new Image();
        pre.referrerPolicy = "no-referrer";
        pre.onload = () => { img.src = big; };
        pre.src = big;
      }
      box.append(img);
    }
    return box;
  }

  async function openDetail(id, scrollToMore) {
    closeDetail();
    document.body.style.overflow = "hidden";
    const inner = h("div", { class: "detail" }, h("div", { class: "loading" }, h("div", { class: "spinner" })));
    detailEl = h("div", { class: "overlay-bg", onclick: (e) => { if (e.target === detailEl || e.target === inner) closeRoute(); } },
      h("button", { class: "close-x", title: "Close (Esc)", onclick: closeRoute }, icon("x", 20)), inner);
    document.body.append(detailEl);
    let a;
    try { a = await api.get("/api/assets/" + enc(id)); } catch (e) { toast(e.message, true); closeRoute(); return; }
    api.post("/api/interactions", { asset_id: id, action: "open" }).catch(() => {});
    const [ulabel, utip] = USAGE[a.usage] || USAGE.check;
    const saveBtn = h("button", { class: "btn primary", text: a.saved ? "Saved ✓" : "Save",
      onclick: () => boardPicker(saveBtn, a, () => { saveBtn.textContent = "Saved ✓"; }) });
    const fileActions = h("span", { class: "actions" });
    const renderFileActions = () => {
      fileActions.replaceChildren();
      if (a.file_url) {
        fileActions.append(h("a", { class: "btn", href: a.file_url + "?download=1" }, icon("down"), `Download (${fmtBytes(a.blob_size)})`));
      } else {
        const b = h("button", { class: "btn", onclick: async () => {
          b.disabled = true; b.textContent = "Downloading…";
          try {
            const r = await api.post("/api/assets/" + enc(a.id) + "/download?wait=1");
            Object.assign(a, r.asset); toast("Stored in your bank"); renderFileActions();
          } catch (e) { toast(e.message, true); b.disabled = false; b.textContent = "Save file to bank"; }
        } }, icon("down"), "Save file to bank");
        fileActions.append(b);
      }
    };
    renderFileActions();
    const tags = h("div", { class: "tags" }, ...(a.tags || []).slice(0, 24).map((t) => h("button", { class: "tag", text: t, onclick: () => go(t) })));
    const palette = h("div", { class: "palette" }, ...(a.colors || []).map(([hex]) => h("button", { title: `Search ${hex}`, style: { background: hex },
      onclick: () => { filters.color = hex; renderFilters(); go(($("#q").value || (a.tags || [])[0] || a.title || "").trim()); } })));
    const kv = h("dl", { class: "kv" });
    const addKV = (k, v) => { if (v) kv.append(h("dt", { text: k }), h("dd", { text: String(v) })); };
    addKV("Type", KIND_LABEL[a.kind]);
    const realDims = a.width > 16 && a.height > 16 && !(a.extra && a.extra.dims_from_thumb);
    addKV("Size", realDims ? `${a.width} × ${a.height}` : "");
    addKV("Duration", a.duration ? fmtDur(a.duration) : "");
    addKV("Date", a.created_at);
    addKV("Prompt", a.extra && a.extra.prompt);
    addKV("Note", a.extra && a.extra.note);
    addKV("Boards", (a.boards || []).map((b) => b.name).join(", "));
    const side = h("div", { class: "detail-side" },
      h("div", { class: "detail-top" }, usageBadge(a.usage), h("span", { class: "badge" }, icon(a.kind, 12), KIND_LABEL[a.kind]), h("span", { class: "spacer" }), saveBtn),
      h("h1", { text: a.title || "Untitled" }),
      h("div", { class: "by" }, a.author ? (a.author_url ? h("a", { href: a.author_url, target: "_blank", rel: "noopener noreferrer", text: a.author }) : h("b", { text: a.author })) : null,
        a.author ? " · " : "", a.page_url ? h("a", { href: a.page_url, target: "_blank", rel: "noopener noreferrer", text: a.source_label }) : a.source_label,
        a.source_credit ? h("span", { class: "muted", text: ` · ${a.source_credit}` }) : null),
      h("div", { class: "lic" },
        h("div", { class: "row" }, h("span", { class: "u u-" + a.usage, style: { width: "10px", height: "10px", borderRadius: "50%", display: "inline-block" } }), ulabel,
          h("span", { class: "muted", style: { fontWeight: "500" }, text: "— " + utip })),
        h("p", null, a.license_url ? h("a", { href: a.license_url, target: "_blank", rel: "noopener noreferrer", text: a.license_label || a.license }) : (a.license_label || a.license)),
        a.attribution ? h("div", { class: "credit", text: a.attribution }) : null,
        a.attribution ? h("div", null, h("button", { class: "btn small", onclick: async () => {
          try { await navigator.clipboard.writeText(a.attribution); toast("Credit copied"); api.post("/api/interactions", { asset_id: a.id, action: "copy" }).catch(() => {}); }
          catch { toast("Copy failed — select the text manually", true); }
        } }, icon("copy", 14), "Copy credit")) : null),
      h("div", { class: "actions" }, fileActions,
        a.page_url ? h("a", { class: "btn", href: a.page_url, target: "_blank", rel: "noopener noreferrer" }, icon("ext"), "Open source") : null,
        h("button", { class: "btn ghost", title: "Hide it and show less like this", onclick: async () => {
          await api.post("/api/assets/" + enc(a.id) + "/hide");
          if (currentFeed) currentFeed.removeId(a.id);
          toast("Hidden — you'll see less like this"); closeRoute();
        } }, icon("eyeoff"), "Not my vibe")),
      a.description && a.description !== (a.extra && a.extra.prompt) ? h("div", { class: "desc", text: a.description }) : null,
      (a.colors || []).length ? palette : null,
      tags,
      kv);
    inner.replaceChildren(h("div", { class: "detail-card" }, mediaFor(a), side), h("div", { class: "related-title", text: "More like this" }));
    const relWrap = h("div");
    inner.append(relWrap);
    detailFeed = new Feed(relWrap, (page) => api.get("/api/assets/" + enc(a.id) + "/related", { page }), {
      empty: h("div", { class: "empty", style: { color: "#ccc" } }, h("p", { text: "Nothing similar in your bank yet — save a few things and search around; it gets better the more you use it." })),
    });
    if (scrollToMore) setTimeout(() => relWrap.scrollIntoView({ behavior: "smooth" }), 300);
  }

  function closeRoute() {
    closeDetail();
    if (history.length > 1 && lastWasBase) history.back();
    else location.hash = baseRoute;
  }

  // ------------------------------------------------------------------ bank page
  async function renderBank() {
    resetView();
    setNav("bank");
    view.append(h("h1", { class: "page-title", text: "Bank" }),
      h("p", { class: "page-sub", text: "What's in your bank, where it lives, which sources feed it, and what it crawls on its own." }));
    const [stats, sources, interests, jobs, health] = await Promise.all([
      api.get("/api/stats").catch(() => ({})), api.get("/api/sources").catch(() => []),
      api.get("/api/interests").catch(() => []), api.get("/api/jobs").catch(() => []), api.get("/api/health").catch(() => ({})),
    ]);
    sourceList = sources;
    const stat = (v, l) => h("div", { class: "stat" }, h("b", { text: v }), h("span", { text: l }));
    view.append(h("section", { class: "panel" }, h("h2", { text: "Your bank" }),
      h("p", { text: `Stored at ${stats.data_dir || "?"} · storage backend: ${stats.storage || "local"} · ${fmtBytes(stats.disk_free)} free on disk` }),
      h("div", { class: "stats" },
        stat((stats.assets || 0).toLocaleString(), "assets indexed"), stat((stats.saved || 0).toLocaleString(), "saved"),
        stat(fmtBytes(stats.stored_bytes), `${stats.stored_files || 0} full files`), stat(fmtBytes(stats.thumbs_bytes), "thumbnail cache"),
        stat(fmtBytes(stats.db_bytes), "index database"), stat((stats.embedded || 0).toLocaleString(), `vibe vectors · ${stats.embedder || ""}`)),
      !stats.semantic ? h("p", { class: "muted", style: { marginTop: "12px" } }, "Vibe search is in lightweight mode (keywords + colors). For real visual search install CLIP: ",
        h("code", { text: "pip install 'noze[clip]'" }), " then restart — see docs/ARCHITECTURE.md.", health.embedder_error ? ` (last error: ${health.embedder_error})` : "") : null));

    // interests (auto-crawl)
    const iq = h("input", { placeholder: "e.g. liquid chrome, film burn transition, batik pattern", maxlength: "200" });
    const ik = h("select", { class: "select" }, ...KIND_CHIPS.map(([v, l]) => h("option", { value: v }, l)));
    const pills = h("div", { class: "pill-list" });
    const drawInterests = (items) => {
      pills.replaceChildren(...items.map((i) => h("span", { class: "pill", title: `every ${i.every_hours}h · next page ${i.next_page}/${i.max_pages}` },
        i.query + (i.kinds ? ` · ${i.kinds}` : ""),
        h("button", { title: "Remove", onclick: async () => { await api.del(`/api/interests/${i.id}`); drawInterests(await api.get("/api/interests")); } }, icon("x", 12)))));
      if (!items.length) pills.append(h("span", { class: "muted", text: "No interests yet." }));
    };
    drawInterests(interests);
    view.append(h("section", { class: "panel" }, h("h2", { text: "Grow the bank automatically" }),
      h("p", { text: "Interests are crawled in the background every day, a few pages deeper each time — like Pinterest learning your taste, but you own the result." }),
      h("div", { class: "row-form" }, iq, ik,
        h("button", { class: "btn primary", text: "Add interest", onclick: async () => {
          if (!iq.value.trim()) return;
          const kv = ik.value === "@inspiration" ? "image,gif,video,link,texture" : ik.value;
          await api.post("/api/interests", { query: iq.value.trim(), kinds: kv ? kv.split(",") : [] });
          iq.value = ""; drawInterests(await api.get("/api/interests")); toast("Crawling in the background");
        } }),
        h("button", { class: "btn", text: "+ Starter pack (50 topics)", onclick: async () => {
          const r = await api.post("/api/interests/starter"); drawInterests(await api.get("/api/interests")); toast(`${r.added} topics queued`);
        } })),
      pills));

    // save from anywhere
    const origin = location.origin;
    // Runs on the page you're looking at when you click it. On Pinterest it keeps feed order (that's
    // Pinterest's own relevance), upgrades thumbnails to the 736px version and remembers each pin's link.
    const bm = `javascript:(()=>{const P=/(^|\\.)pinterest\\./.test(location.hostname);const U=s=>P?s.replace(/\\/(\\d+x\\d*)\\//,'/736x/'):s;const S=new Set();let I=[];for(const i of document.images){if(i.naturalWidth<140||i.naturalHeight<140)continue;const s=U(i.currentSrc||i.src);if(!s||s.startsWith('data:')||S.has(s))continue;S.add(s);const a=i.closest('a[href*="/pin/"]');I.push({src:s,w:i.naturalWidth,h:i.naturalHeight,t:(i.alt||'').slice(0,160),p:a?a.href.split('?')[0]:''})}if(!P)I.sort((a,b)=>b.w*b.h-a.w*a.h);I=I.slice(0,P?150:40);const o=document.querySelector('meta[property="og:image"]');if(o&&o.content&&!S.has(o.content))I.unshift({src:o.content,w:0,h:0,t:'',p:''});const V=[...document.querySelectorAll('video')].map(v=>({src:v.currentSrc||v.src,poster:v.poster})).filter(v=>v.src&&!v.src.startsWith('blob:'));const d={page:location.href,title:document.title,images:I,videos:V,sel:String(getSelection()).slice(0,500)};window.open('${origin}/save#'+encodeURIComponent(JSON.stringify(d)),'noze','width=900,height=820');})()`;
    const link = h("a", { class: "bookmarklet", title: "Drag me to your bookmarks bar", onclick: (e) => { e.preventDefault(); toast("Drag this button to your bookmarks bar"); } }, icon("spark"), "Save to NOZE");
    link.setAttribute("href", bm);
    view.append(h("section", { class: "panel" }, h("h2", { text: "Save from anywhere (Pinterest, Behance, Dribbble, X, AI galleries…)" }),
      h("p", { text: "Drag this button to your bookmarks bar. While browsing any site, click it, pick the images/videos you want and they're saved into your bank with the page link for credit — marked reference-only, because the rights stay with whoever made them. On Pinterest: open a pin (its \"More like this\" is Pinterest's own related engine), scroll a bit, click the button, \"Select all\" — every pin you're looking at lands in your bank in one go." }),
      link,
      h("p", { class: "muted", style: { marginTop: "12px" } }, "Import your own Pinterest boards via the official API: ", h("code", { text: "noze import-pinterest" }),
        " · index an existing asset folder: ", h("code", { text: "noze import-folder ~/Assets --board \"Old packs\"" }))));

    // AI generation
    if (stats.generate) {
      const gp = h("input", { placeholder: "Describe the clip or image you couldn't find…" });
      const gk = h("select", { class: "select" }, h("option", { value: "video" }, "Video (Seedance)"), h("option", { value: "image" }, "Image (FLUX)"));
      view.append(h("section", { class: "panel" }, h("h2", { text: "Generate what you can't find" }),
        h("p", { text: "Uses your Replicate account (paid per generation). The result is saved into your bank as your own asset." }),
        h("div", { class: "row-form" }, gp, gk, h("button", { class: "btn primary", onclick: async () => {
          if (gp.value.trim().length < 3) return;
          try { const r = await api.post("/api/generate", { prompt: gp.value.trim(), kind: gk.value }); toast(`Generating… (job ${r.job_id}) — it will appear on Home`); gp.value = ""; }
          catch (e) { toast(e.message, true); }
        } }, icon("spark"), "Generate"))));
    }

    // sources
    const table = h("table", { class: "src-table" }, h("tr", null, h("th", { text: "Source" }), h("th", { text: "Gives you" }), h("th", { text: "In bank" }), h("th", { text: "Status" })));
    for (const s of sources) {
      const cooling = s.cooldown_until && s.cooldown_until * 1000 > Date.now();
      const dot = h("span", { class: "status-dot" + (!s.enabled ? " off" : s.last_error && (!s.last_ok || s.last_error_at > s.last_ok) ? " err" : "") });
      let status;
      if (!s.enabled && s.missing_keys.length) status = h("span", null, "needs ", h("code", { text: s.missing_keys.join(" + ") }), " — ", h("a", { href: s.signup_url, target: "_blank", rel: "noopener noreferrer", text: "get a free key" }));
      else if (!s.enabled) status = "disabled";
      else if (cooling) status = `resting until ${new Date(s.cooldown_until * 1000).toLocaleTimeString()}`;
      else if (s.last_error && (!s.last_ok || s.last_error_at > s.last_ok)) status = h("span", { title: s.last_error, text: "last call failed: " + s.last_error.slice(0, 80) });
      else status = s.last_ok ? "ok" : "ready";
      table.append(h("tr", null,
        h("td", null, dot, h("a", { href: s.homepage, target: "_blank", rel: "noopener noreferrer", text: s.label }), h("div", { class: "desc-s", text: s.description })),
        h("td", { text: s.kinds.map((k) => KIND_LABEL[k] || k).join(", ") }),
        h("td", { text: (s.items || 0).toLocaleString() }),
        h("td", null, status)));
    }
    view.append(h("section", { class: "panel" }, h("h2", { text: "Sources" }),
      h("p", { text: "Keys go in a .env file next to where you run NOZE (see .env.example). Everything else works without any key." }), table));

    // jobs + theme
    const jl = h("div", { class: "jobs" }, ...jobs.slice(0, 25).map((j) => h("div", { text:
      `#${j.id} ${j.type} · ${j.status}${j.error ? " — " + j.error : ""}${j.payload && (j.payload.query || j.payload.prompt) ? " · " + (j.payload.query || j.payload.prompt) : ""}` })));
    const theme = h("select", { class: "select", onchange: (e) => { store.set("theme", e.target.value); applyTheme(); } },
      h("option", { value: "auto" }, "Theme: auto"), h("option", { value: "dark" }, "Theme: dark"), h("option", { value: "light" }, "Theme: light"));
    theme.value = store.get("theme", "auto");
    view.append(h("section", { class: "panel" }, h("h2", { text: "Background jobs" }), jl.childNodes.length ? jl : h("p", { text: "Nothing running." }),
      h("div", { style: { marginTop: "14px" } }, theme)));
    const credits = sources.filter((s) => s.credit).map((s) => s.credit);
    view.append(h("p", { class: "credits-line", text: credits.join(" · ") }));
  }

  // ------------------------------------------------------------------ add dialog
  function openAdd() {
    const url = h("input", { placeholder: "https://… image, video, or any page (Pinterest pin, Behance project…)" });
    const title = h("input", { placeholder: "Title (optional)" });
    const board = h("input", { placeholder: "Board (optional)", value: store.get("lastBoard", "") });
    const note = h("textarea", { placeholder: "Note / why you saved it (optional)" });
    const drop = h("label", { class: "drop" }, "Drop files here or click to upload (images, videos, audio, fonts, Lottie, .aep/.mogrt/.psd/LUTs…)",
      h("input", { type: "file", multiple: true, class: "hidden", onchange: (e) => upload([...e.target.files]) }));
    const dlg = h("div", { class: "dialog", onclick: (e) => { if (e.target === dlg) dlg.remove(); } },
      h("div", { class: "box" }, h("h2", { text: "Add to your bank" }),
        h("div", { class: "field" }, h("label", { text: "Save a link" }), url),
        h("div", { class: "field" }, title), h("div", { class: "field" }, board), h("div", { class: "field" }, note),
        h("div", { class: "actions" }, h("button", { class: "btn primary", text: "Save link", onclick: saveLink }), h("button", { class: "btn ghost", text: "Cancel", onclick: () => dlg.remove() })),
        drop));
    ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
    ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
    drop.addEventListener("drop", (e) => upload([...e.dataTransfer.files]));
    document.body.append(dlg);
    url.focus();
    async function saveLink() {
      if (!url.value.trim()) return;
      try {
        const a = await api.post("/api/ingest/url", { url: url.value.trim(), title: title.value.trim(), note: note.value.trim(), board: board.value.trim() || null });
        if (board.value.trim()) store.set("lastBoard", board.value.trim());
        toast(`Saved “${a.title}”`); dlg.remove(); location.hash = "#/a/" + enc(a.id);
      } catch (e) { toast(e.message, true); }
    }
    async function upload(files) {
      for (const f of files) {
        const fd = new FormData();
        fd.append("file", f); fd.append("board", board.value.trim()); fd.append("note", note.value.trim());
        try { await api.form("/api/ingest/upload", fd); toast(`Uploaded ${f.name}`); } catch (e) { toast(`${f.name}: ${e.message}`, true); }
      }
      dlg.remove();
      if (location.hash === "#/" || location.hash === "") renderHome();
    }
  }

  // ------------------------------------------------------------------ routing
  let lastWasBase = false;
  let inApp = false;
  function go(q) {
    q = (q || "").trim();
    location.hash = q ? "#/search?q=" + enc(q) : "#/";
  }
  function refreshView() { route(true); }

  function route(force) {
    const hash = location.hash || "#/";
    const [path, qs] = hash.slice(1).split("?");
    const params = new URLSearchParams(qs || "");
    if (path.startsWith("/a/")) {
      lastWasBase = inApp && view.childNodes.length > 0;
      if (!view.childNodes.length) renderBase(baseRoute);
      inApp = true;
      openDetail(decodeURIComponent(path.slice(3)), params.get("more") === "1");
      return;
    }
    closeDetail();
    if (!force && hash === baseRoute && view.childNodes.length) return; // came back from a detail view
    baseRoute = hash;
    lastWasBase = false;
    inApp = true;
    renderBase(hash);
  }

  function renderBase(hash) {
    const [path, qs] = hash.slice(1).split("?");
    const params = new URLSearchParams(qs || "");
    if (path === "/search") renderSearch(params.get("q") || "");
    else if (path === "/boards") renderBoards();
    else if (path.startsWith("/b/")) renderBoard(parseInt(path.slice(3), 10));
    else if (path === "/bank") renderBank();
    else renderHome();
  }

  $("#search-form").addEventListener("submit", (e) => { e.preventDefault(); go($("#q").value); $("#q").blur(); });
  $("#add-btn").addEventListener("click", openAdd);
  window.addEventListener("hashchange", () => route(false));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { if (openPop) closePop(); else if (detailEl) closeRoute(); }
    if (e.key === "/" && document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "TEXTAREA" && !document.activeElement.isContentEditable) { e.preventDefault(); $("#q").focus(); }
  });

  renderFilters();
  api.get("/api/sources").then((s) => { sourceList = s; renderFilters(); }).catch(() => {});
  route(true);
})();
