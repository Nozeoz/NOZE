import Anthropic from "@anthropic-ai/sdk";
import { config } from "./config.js";
import { personaPrompt, channelNote } from "./persona.js";
import { listFacts, loadHistory, saveHistory } from "./memory.js";
import { toolDefinitions, runTool } from "./tools.js";

const client = new Anthropic();
const MAX_TOOL_ROUNDS = 8;

// One conversation turn at a time per thread, so history writes never interleave.
const locks = new Map();
function withLock(threadId, fn) {
  const prev = locks.get(threadId) || Promise.resolve();
  const next = prev.then(fn, fn);
  locks.set(threadId, next.catch(() => {}));
  return next;
}

async function buildSystem(channel) {
  const facts = await listFacts();
  const memory = facts.length
    ? "Hal yang kamu ingat tentang pemilik:\n" + facts.map((f) => `- [${f.id}] ${f.text}`).join("\n")
    : "Kamu belum menyimpan ingatan apa pun tentang pemilik.";
  return [
    { type: "text", text: personaPrompt(), cache_control: { type: "ephemeral" } },
    { type: "text", text: `${memory}\n\n${channelNote(channel)}` },
  ];
}

function openStream(params) {
  if (config.fallbacks) {
    return client.beta.messages.stream({
      ...params,
      betas: ["server-side-fallback-2026-07-01"],
      fallbacks: "default",
    });
  }
  return client.messages.stream(params);
}

// After a mid-output fallback, blocks the declined model produced before the
// last `fallback` marker must not be echoed back (except text).
function sanitizeForEcho(content) {
  const lastFallback = content.map((b) => b.type).lastIndexOf("fallback");
  if (lastFallback === -1) return content;
  return content.filter((b, i) => i > lastFallback || b.type === "text");
}

/**
 * Run one user turn through Claude, with tools.
 * @param {object} opts
 * @param {string} opts.threadId  conversation id ("hq", "whatsapp:628…")
 * @param {string} opts.text      what the owner said
 * @param {"hq"|"voice"|"whatsapp"} opts.channel
 * @param {(delta: string) => void} [opts.onText]    streamed text deltas
 * @param {(status: string) => void} [opts.onStatus] tool activity for the UI
 * @returns {Promise<string>} the full reply text
 */
export function think({ threadId, text, channel, onText = () => {}, onStatus = () => {} }) {
  return withLock(threadId, async () => {
    // Stored history is plain text turns only — thinking and tool blocks are
    // not replayed across turns, which keeps it valid if memory or trimming changes.
    const history = await loadHistory(threadId);
    const messages = [...history, { role: "user", content: text }];
    const system = await buildSystem(channel);
    let reply = "";

    for (let round = 0; round < MAX_TOOL_ROUNDS; round++) {
      const stream = openStream({
        model: config.model,
        max_tokens: 16000,
        output_config: { effort: config.effort },
        system,
        tools: toolDefinitions,
        messages,
      });
      stream.on("text", (delta) => {
        reply += delta;
        onText(delta);
      });

      let message;
      try {
        message = await stream.finalMessage();
      } catch (err) {
        if (err instanceof Anthropic.APIError) throw err;
        // A tool input that could not be parsed: re-issue the turn once more.
        if (round < MAX_TOOL_ROUNDS - 1) continue;
        throw err;
      }

      if (message.stop_reason === "refusal") {
        const sorry = `Mohon maaf, ${config.honorific}, yang satu itu tidak bisa saya bantu.`;
        reply += (reply ? " " : "") + sorry;
        onText(sorry);
        break;
      }
      if (message.stop_reason === "pause_turn") {
        messages.push({ role: "assistant", content: sanitizeForEcho(message.content) });
        continue;
      }
      if (message.stop_reason !== "tool_use") break;

      const content = sanitizeForEcho(message.content);
      const toolUses = content.filter((b) => b.type === "tool_use");
      if (toolUses.length === 0) break;
      messages.push({ role: "assistant", content });

      const results = await Promise.all(
        toolUses.map(async (block) => {
          onStatus(`${block.name}…`);
          const result = await runTool(block.name, block.input);
          return { type: "tool_result", tool_use_id: block.id, ...result };
        }),
      );
      messages.push({ role: "user", content: results });
      if (reply && !/\s$/.test(reply)) {
        reply += " ";
        onText(" ");
      }
    }

    reply = reply.trim();
    await saveHistory(threadId, [...history, { role: "user", content: text }, { role: "assistant", content: reply || "…" }]);
    return reply;
  });
}
