// ── HQ token (only needed when HQ_TOKEN is set on the server) ─────
const store = {
  get: (k) => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch {} },
};

async function api(path, opts = {}) {
  const headers = { "content-type": "application/json", ...(opts.headers || {}) };
  const token = store.get("hqToken");
  if (token) headers["x-hq-token"] = token;
  const res = await fetch(path, { ...opts, headers });
  if (res.status === 401) {
    const t = prompt("Masukkan HQ token:");
    if (t) { store.set("hqToken", t); return api(path, opts); }
  }
  return res;
}

const $ = (id) => document.getElementById(id);
const log = $("log");
let honorific = "Tuan";
let assistantName = "Jarvis";

// ── Orb ───────────────────────────────────────────────────────────
const orb = $("orb");
const ctx = orb.getContext("2d");
let mode = "idle"; // idle | listening | thinking | speaking
let level = 0;
let analyser = null;
let audioCtx = null;
const labels = { idle: "Siaga", listening: "Mendengarkan", thinking: "Berpikir", speaking: "Berbicara" };

function setMode(m) {
  mode = m;
  $("stateLabel").textContent = labels[m];
}

function drawOrb(t) {
  const dpr = window.devicePixelRatio || 1;
  const size = orb.clientWidth;
  if (orb.width !== size * dpr) { orb.width = orb.height = size * dpr; }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, size, size);

  let target = 0.08;
  if (mode === "speaking" && analyser) {
    const buf = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(buf);
    target = Math.min(1, buf.reduce((a, b) => a + b, 0) / buf.length / 90);
  } else if (mode === "speaking") target = 0.35 + 0.25 * Math.sin(t / 110);
  else if (mode === "listening") target = 0.3 + 0.15 * Math.sin(t / 300);
  else if (mode === "thinking") target = 0.2;
  level += (target - level) * 0.15;

  const c = size / 2;
  const base = size * 0.26;
  const hueA = mode === "thinking" ? "#b59cff" : "#7cc4ff";

  const glow = ctx.createRadialGradient(c, c, base * 0.2, c, c, size / 2);
  glow.addColorStop(0, hueA + "55");
  glow.addColorStop(1, "transparent");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, size, size);

  for (let ring = 0; ring < 3; ring++) {
    ctx.beginPath();
    const pts = 96;
    for (let i = 0; i <= pts; i++) {
      const a = (i / pts) * Math.PI * 2;
      const wobble =
        Math.sin(a * (3 + ring) + t / (700 - ring * 150)) * (4 + level * 18) +
        Math.sin(a * 5 - t / 900) * (2 + level * 8);
      const r = base + ring * 7 + wobble + level * 14;
      const x = c + Math.cos(a) * r;
      const y = c + Math.sin(a) * r;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.strokeStyle = ring === 0 ? hueA : ring === 1 ? "#b59cff99" : "#7cc4ff44";
    ctx.lineWidth = ring === 0 ? 2 : 1;
    ctx.stroke();
  }

  if (mode === "thinking") {
    ctx.beginPath();
    ctx.arc(c, c, base - 14, t / 300, t / 300 + Math.PI * 0.6);
    ctx.strokeStyle = "#e6e9ef88";
    ctx.lineWidth = 2;
    ctx.stroke();
  }
  requestAnimationFrame(drawOrb);
}
requestAnimationFrame(drawOrb);

// ── Chat log ──────────────────────────────────────────────────────
function addMsg(who, text = "") {
  const el = document.createElement("div");
  el.className = `msg ${who}`;
  if (who === "jarvis") {
    const w = document.createElement("span");
    w.className = "who";
    w.textContent = assistantName.toUpperCase();
    el.append(w);
  }
  const body = document.createElement("span");
  body.className = "body";
  body.textContent = text;
  el.append(body);
  log.append(el);
  log.scrollTop = log.scrollHeight;
  return el;
}

// ── Speech out ────────────────────────────────────────────────────
const voiceOn = () => $("voiceToggle").checked;
const speechQueue = [];
let speaking = false;
let currentAudio = null;

function cleanForSpeech(text) {
  return text
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/https?:\/\/\S+/g, "tautan")
    .replace(/[*_#`>~|]/g, "")
    .replace(/\[(.*?)\]\(.*?\)/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

function ensureAudioCtx() {
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 256;
    analyser.connect(audioCtx.destination);
  }
  if (audioCtx.state === "suspended") audioCtx.resume();
}

// Fetch audio as soon as a sentence is ready, play strictly in order.
function enqueueSpeech(sentence) {
  const text = cleanForSpeech(sentence);
  if (!text) return;
  const pending = api("/api/tts", { method: "POST", body: JSON.stringify({ text }) })
    .then(async (res) => (res.status === 200 ? { blob: await res.blob() } : { browser: true }))
    .catch(() => ({ browser: true }));
  speechQueue.push({ text, pending });
  if (!speaking) playNext();
}

function pickBrowserVoice() {
  const voices = speechSynthesis.getVoices();
  const id = voices.filter((v) => v.lang?.toLowerCase().startsWith("id"));
  return id.find((v) => /female|wanita|gadis|damayanti|google/i.test(v.name)) || id[0] || null;
}

function speakBrowser(text) {
  return new Promise((resolve) => {
    if (!("speechSynthesis" in window)) return resolve();
    const u = new SpeechSynthesisUtterance(text);
    const v = pickBrowserVoice();
    if (v) u.voice = v;
    u.lang = v?.lang || "id-ID";
    u.rate = 0.95;
    u.pitch = 1.05;
    u.onend = u.onerror = resolve;
    speechSynthesis.speak(u);
  });
}

function playBlob(blob) {
  return new Promise((resolve) => {
    ensureAudioCtx();
    const audio = new Audio(URL.createObjectURL(blob));
    currentAudio = audio;
    const src = audioCtx.createMediaElementSource(audio);
    src.connect(analyser);
    audio.onended = audio.onerror = () => { URL.revokeObjectURL(audio.src); resolve(); };
    audio.play().catch(resolve);
  });
}

async function playNext() {
  const item = speechQueue.shift();
  if (!item) {
    speaking = false;
    if (mode === "speaking") setMode("idle");
    maybeAutoListen();
    return;
  }
  speaking = true;
  setMode("speaking");
  const out = await item.pending;
  if (out.blob) await playBlob(out.blob);
  else await speakBrowser(item.text);
  playNext();
}

function stopSpeaking() {
  speechQueue.length = 0;
  if (currentAudio) { currentAudio.pause(); currentAudio = null; }
  if ("speechSynthesis" in window) speechSynthesis.cancel();
  speaking = false;
}

// ── Talking to the brain ──────────────────────────────────────────
let busy = false;

async function send(text, viaVoice = false) {
  text = text.trim();
  if (!text || busy) return;
  busy = true;
  stopSpeaking();
  addMsg("user", text);
  const el = addMsg("jarvis");
  const body = el.querySelector(".body");
  const status = document.createElement("span");
  status.className = "status";
  el.append(status);
  setMode("thinking");

  const speak = voiceOn();
  let pendingSentence = "";
  const flushSentences = (final = false) => {
    if (!speak) return;
    const parts = pendingSentence.split(/(?<=[.!?…])\s+/);
    pendingSentence = final ? "" : parts.pop();
    for (const p of parts) if (p.trim()) enqueueSpeech(p);
  };

  try {
    const res = await api("/api/chat", { method: "POST", body: JSON.stringify({ text, voice: speak || viaVoice }) });
    if (!res.ok || !res.body) throw new Error((await res.json().catch(() => ({}))).error || `HTTP ${res.status}`);
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) !== -1) {
        const chunk = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const event = /^event: (.*)$/m.exec(chunk)?.[1];
        const data = JSON.parse(/^data: (.*)$/m.exec(chunk)?.[1] || "null");
        if (event === "text") {
          body.textContent += data;
          pendingSentence += data;
          status.textContent = "";
          flushSentences();
          log.scrollTop = log.scrollHeight;
        } else if (event === "status") {
          status.textContent = data;
        } else if (event === "error") {
          throw new Error(data);
        }
      }
    }
    flushSentences(true);
  } catch (err) {
    el.classList.add("error");
    body.textContent = `Mohon maaf, ${honorific} — ${err.message}`;
  } finally {
    status.remove();
    busy = false;
    if (!speaking && speechQueue.length === 0) { setMode("idle"); maybeAutoListen(); }
    refreshMemory();
  }
}

$("composer").addEventListener("submit", (e) => {
  e.preventDefault();
  ensureAudioCtx();
  const input = $("input");
  send(input.value);
  input.value = "";
});

// ── Speech in (browser speech recognition) ────────────────────────
const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognizer = null;
let listening = false;

function startListening() {
  if (!Recognition) {
    alert("Browser ini belum mendukung pengenalan suara. Coba Chrome atau Edge.");
    return;
  }
  if (listening || busy) return;
  ensureAudioCtx();
  stopSpeaking();
  recognizer = new Recognition();
  recognizer.lang = "id-ID";
  recognizer.interimResults = true;
  recognizer.continuous = false;
  let finalText = "";
  recognizer.onresult = (e) => {
    let interim = "";
    for (const r of e.results) (r.isFinal ? (finalText = r[0].transcript) : (interim += r[0].transcript));
    $("input").value = finalText || interim;
  };
  recognizer.onend = () => {
    listening = false;
    $("micBtn").classList.remove("on");
    if (mode === "listening") setMode("idle");
    const text = $("input").value;
    $("input").value = "";
    if (text.trim()) send(text, true);
  };
  recognizer.onerror = () => {};
  listening = true;
  $("micBtn").classList.add("on");
  setMode("listening");
  recognizer.start();
}

function stopListening() {
  recognizer?.stop();
}

function maybeAutoListen() {
  if ($("handsFreeToggle").checked && !busy && !speaking) setTimeout(startListening, 350);
}

$("micBtn").addEventListener("click", () => (listening ? stopListening() : startListening()));
document.addEventListener("keydown", (e) => {
  if (e.code === "Space" && document.activeElement !== $("input") && !e.repeat) {
    e.preventDefault();
    listening ? stopListening() : startListening();
  }
  if (e.key === "Escape") { stopSpeaking(); setMode("idle"); }
});

$("resetBtn").addEventListener("click", async () => {
  await api("/api/reset", { method: "POST" });
  log.innerHTML = "";
  addMsg("jarvis", `Lembaran baru, ${honorific}. Ada yang bisa saya bantu?`);
});

// ── Side panels ───────────────────────────────────────────────────
const waLabels = {
  disabled: "nonaktif",
  connecting: "menghubungkan…",
  waiting_for_scan: "menunggu scan QR",
  connected: "terhubung",
  reconnecting: "menyambung ulang…",
  logged_out: "logout",
  error: "error",
};

async function refreshStatus() {
  const res = await api("/api/status");
  if (!res.ok) return;
  const s = await res.json();
  honorific = s.honorific;
  assistantName = s.name;
  $("brandName").textContent = s.name.toUpperCase();
  document.title = `${s.name} HQ`;
  $("brainDot").classList.add("ok");
  $("sysModel").textContent = s.model;
  $("sysTts").textContent = s.tts;
  const wa = s.whatsapp;
  $("sysWa").textContent = waLabels[wa.status] + (wa.me ? ` (+${wa.me})` : "");
  $("waQr").hidden = !wa.qrDataUrl;
  if (wa.qrDataUrl) $("waQr").src = wa.qrDataUrl;
  const hint = wa.qrDataUrl
    ? "Buka WhatsApp → Perangkat tertaut → Tautkan perangkat, lalu scan."
    : wa.lastError || "";
  $("waHint").hidden = !hint;
  $("waHint").textContent = hint;
}

async function refreshProjects() {
  const res = await api("/api/projects");
  if (!res.ok) return;
  const list = $("projects");
  list.innerHTML = "";
  const projects = await res.json();
  if (!projects.length) list.innerHTML = '<li class="muted">Belum ada. Tambah di config/projects.json</li>';
  for (const p of projects) {
    const li = document.createElement("li");
    const pill = document.createElement("span");
    pill.className = `pill ${p.health.status}`;
    pill.textContent = p.health.status;
    const name = document.createElement(p.url ? "a" : "span");
    if (p.url) { name.href = p.url; name.target = "_blank"; name.rel = "noopener"; name.style.color = "inherit"; }
    name.textContent = p.name;
    name.title = p.description || "";
    li.append(pill, name);
    list.append(li);
  }
}

async function refreshMemory() {
  const res = await api("/api/memory");
  if (!res.ok) return;
  const facts = await res.json();
  const list = $("memory");
  list.innerHTML = "";
  if (!facts.length) list.innerHTML = '<li class="muted">Belum ada yang diingat.</li>';
  for (const f of facts.slice().reverse()) {
    const li = document.createElement("li");
    const text = document.createElement("span");
    text.textContent = f.text;
    const x = document.createElement("button");
    x.className = "x";
    x.textContent = "×";
    x.title = "Lupakan";
    x.onclick = async () => { await api(`/api/memory/${f.id}`, { method: "DELETE" }); refreshMemory(); };
    li.append(text, x);
    list.append(li);
  }
}

$("refreshProjects").addEventListener("click", refreshProjects);

function tick() {
  $("clock").textContent = new Date().toLocaleString("id-ID", { weekday: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
setInterval(tick, 1000);
tick();

// Voice toggle is a per-viewer preference.
$("voiceToggle").checked = store.get("voice") !== "off";
$("voiceToggle").addEventListener("change", (e) => store.set("voice", e.target.checked ? "on" : "off"));
if ("speechSynthesis" in window) speechSynthesis.onvoiceschanged = () => {};

await refreshStatus();
refreshProjects();
refreshMemory();
setInterval(refreshStatus, 4000);

const hour = new Date().getHours();
const greet = hour < 11 ? "Selamat pagi" : hour < 15 ? "Selamat siang" : hour < 19 ? "Selamat sore" : "Selamat malam";
addMsg("jarvis", `${greet}, ${honorific}. Semua sistem siap.`);
