import fs from "node:fs/promises";
import path from "node:path";
import { DATA_DIR } from "./config.js";

const MEMORY_FILE = path.join(DATA_DIR, "memory.json");
const CONVO_DIR = path.join(DATA_DIR, "conversations");
const MAX_MESSAGES = 60;

async function readJson(file, fallback) {
  try {
    return JSON.parse(await fs.readFile(file, "utf8"));
  } catch {
    return fallback;
  }
}

async function writeJson(file, value) {
  await fs.mkdir(path.dirname(file), { recursive: true });
  const tmp = `${file}.tmp`;
  await fs.writeFile(tmp, JSON.stringify(value, null, 2));
  await fs.rename(tmp, file);
}

// ── Long-term facts ─────────────────────────────────────────────
export async function listFacts() {
  return readJson(MEMORY_FILE, []);
}

export async function addFact(text) {
  const facts = await listFacts();
  const fact = { id: Date.now().toString(36), text: text.trim(), at: new Date().toISOString() };
  facts.push(fact);
  await writeJson(MEMORY_FILE, facts);
  return fact;
}

export async function removeFact(id) {
  const facts = await listFacts();
  const next = facts.filter((f) => f.id !== id);
  await writeJson(MEMORY_FILE, next);
  return next.length !== facts.length;
}

// ── Conversation history per thread (hq, whatsapp:<number>, …) ──
function convoFile(threadId) {
  return path.join(CONVO_DIR, `${threadId.replace(/[^a-zA-Z0-9_-]/g, "_")}.json`);
}

export async function loadHistory(threadId) {
  return readJson(convoFile(threadId), []);
}

// Keep the tail of the conversation, cutting only at a plain user turn so
// tool_use / tool_result pairs are never split.
export async function saveHistory(threadId, messages) {
  let trimmed = messages;
  if (messages.length > MAX_MESSAGES) {
    const start = messages.findIndex(
      (m, i) => i >= messages.length - MAX_MESSAGES && m.role === "user" && typeof m.content === "string",
    );
    trimmed = start === -1 ? messages : messages.slice(start);
  }
  await writeJson(convoFile(threadId), trimmed);
}

export async function clearHistory(threadId) {
  await writeJson(convoFile(threadId), []);
}
