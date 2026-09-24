import crypto from "node:crypto";
import path from "node:path";
import express from "express";
import { config, ROOT } from "./config.js";
import { think } from "./brain.js";
import { synthesize } from "./tts.js";
import { listFacts, removeFact, clearHistory } from "./memory.js";
import { loadProjects, checkProject } from "./tools.js";
import { startWhatsApp, waState } from "./whatsapp.js";

const app = express();
app.use(express.json({ limit: "1mb" }));
app.use(express.static(path.join(ROOT, "hq")));

app.get("/api/health", (_req, res) => res.json({ ok: true }));

// Everything else under /api needs the HQ token when one is configured.
app.use("/api", (req, res, next) => {
  if (!config.hqToken) return next();
  const given = Buffer.from(String(req.get("x-hq-token") || ""));
  const expected = Buffer.from(config.hqToken);
  if (given.length === expected.length && crypto.timingSafeEqual(given, expected)) return next();
  res.status(401).json({ error: "HQ token salah atau belum diisi" });
});

app.get("/api/status", (_req, res) => {
  res.json({
    name: config.name,
    honorific: config.honorific,
    model: config.model,
    tts: config.tts.provider,
    whatsapp: waState,
  });
});

app.post("/api/chat", async (req, res) => {
  const text = typeof req.body?.text === "string" ? req.body.text.trim() : "";
  if (!text) return res.status(400).json({ error: "text kosong" });

  res.set({ "content-type": "text/event-stream", "cache-control": "no-cache", connection: "keep-alive" });
  res.flushHeaders();
  const send = (event, data) => res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);

  try {
    const reply = await think({
      threadId: "hq",
      text,
      channel: req.body.voice ? "voice" : "hq",
      onText: (delta) => send("text", delta),
      onStatus: (status) => send("status", status),
    });
    send("done", reply);
  } catch (err) {
    console.error("[chat]", err);
    send("error", err.message || "Terjadi kesalahan");
  }
  res.end();
});

app.post("/api/tts", async (req, res) => {
  const text = typeof req.body?.text === "string" ? req.body.text.trim() : "";
  if (!text) return res.status(400).json({ error: "text kosong" });
  try {
    const out = await synthesize(text.slice(0, 2000));
    if (!out) return res.status(204).end(); // browser speaks it itself
    res.set("content-type", out.mime).send(out.audio);
  } catch (err) {
    console.error("[tts]", err.message);
    res.status(502).json({ error: err.message });
  }
});

app.get("/api/projects", async (_req, res) => {
  const projects = await loadProjects();
  const health = await Promise.all(projects.map(checkProject));
  res.json(projects.map((p, i) => ({ ...p, health: health[i] })));
});

app.get("/api/memory", async (_req, res) => res.json(await listFacts()));
app.delete("/api/memory/:id", async (req, res) => res.json({ removed: await removeFact(req.params.id) }));
app.post("/api/reset", async (_req, res) => {
  await clearHistory("hq");
  res.json({ ok: true });
});

app.listen(config.port, config.host, () => {
  console.log(`\n  ${config.name} HQ menyala di http://${config.host}:${config.port}\n`);
  if (!process.env.ANTHROPIC_API_KEY && !process.env.ANTHROPIC_AUTH_TOKEN) {
    console.warn("  ⚠  ANTHROPIC_API_KEY belum diisi di .env — Jarvis belum bisa berpikir.\n");
  }
  if (config.host !== "127.0.0.1" && config.host !== "localhost" && !config.hqToken) {
    console.warn("  ⚠  HQ terbuka ke jaringan tanpa HQ_TOKEN. Isi HQ_TOKEN di .env!\n");
  }
});

startWhatsApp().catch((err) => {
  waState.status = "error";
  waState.lastError = err.message;
  console.error("[wa]", err);
});
