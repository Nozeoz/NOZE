import path from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const DATA_DIR = path.join(ROOT, "data");

const env = process.env;

export const config = {
  model: env.JARVIS_MODEL || "claude-opus-5",
  effort: env.JARVIS_EFFORT || "low",
  fallbacks: (env.JARVIS_FALLBACKS || "default") !== "off",

  name: env.JARVIS_NAME || "Jarvis",
  ownerName: env.OWNER_NAME || "Tuan",
  honorific: env.OWNER_HONORIFIC || "Tuan",

  port: Number(env.PORT || 3000),
  host: env.HOST || "127.0.0.1",
  hqToken: env.HQ_TOKEN || "",

  tts: {
    provider: env.TTS_PROVIDER || "browser",
    elevenlabs: {
      apiKey: env.ELEVENLABS_API_KEY || "",
      voiceId: env.ELEVENLABS_VOICE_ID || "",
      model: env.ELEVENLABS_MODEL || "eleven_multilingual_v2",
    },
    openai: {
      apiKey: env.OPENAI_API_KEY || "",
      voice: env.OPENAI_TTS_VOICE || "shimmer",
    },
    chatterboxUrl: env.CHATTERBOX_URL || "http://127.0.0.1:8008",
  },

  whatsapp: {
    enabled: env.WHATSAPP_ENABLED === "true",
    owners: (env.WHATSAPP_OWNER || "")
      .split(",")
      .map((n) => n.replace(/\D/g, ""))
      .filter(Boolean),
  },
};
