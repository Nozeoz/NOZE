import { config } from "./config.js";

// How we want the voice to feel. Used directly by providers that accept
// style instructions (OpenAI), and as guidance for picking ElevenLabs voices.
export const VOICE_STYLE =
  "Suara perempuan muda yang lembut dan soft-spoken, hangat, tenang, nada membulat (rounded) dan tidak tajam. " +
  "Tempo sedikit pelan dan rileks, seperti butler yang anggun berbicara pelan di ruangan yang sunyi. " +
  "Ada senyum tipis di suaranya saat bercanda. Jangan terdengar seperti penyiar atau robot.";

const providers = {
  async elevenlabs(text) {
    const { apiKey, voiceId, model } = config.tts.elevenlabs;
    if (!apiKey || !voiceId) throw new Error("ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID belum diisi");
    const res = await fetch(
      `https://api.elevenlabs.io/v1/text-to-speech/${encodeURIComponent(voiceId)}?output_format=mp3_44100_128`,
      {
        method: "POST",
        headers: { "xi-api-key": apiKey, "content-type": "application/json" },
        body: JSON.stringify({
          text,
          model_id: model,
          // Lower stability = more expressive; style kept low for a calm, soft delivery.
          voice_settings: { stability: 0.45, similarity_boost: 0.8, style: 0.15, use_speaker_boost: true },
        }),
      },
    );
    if (!res.ok) throw new Error(`ElevenLabs ${res.status}: ${await res.text()}`);
    return { audio: Buffer.from(await res.arrayBuffer()), mime: "audio/mpeg" };
  },

  async openai(text) {
    const { apiKey, voice } = config.tts.openai;
    if (!apiKey) throw new Error("OPENAI_API_KEY belum diisi");
    const res = await fetch("https://api.openai.com/v1/audio/speech", {
      method: "POST",
      headers: { authorization: `Bearer ${apiKey}`, "content-type": "application/json" },
      body: JSON.stringify({ model: "gpt-4o-mini-tts", voice, input: text, instructions: VOICE_STYLE, response_format: "mp3" }),
    });
    if (!res.ok) throw new Error(`OpenAI TTS ${res.status}: ${await res.text()}`);
    return { audio: Buffer.from(await res.arrayBuffer()), mime: "audio/mpeg" };
  },

  async chatterbox(text) {
    const res = await fetch(`${config.tts.chatterboxUrl}/tts`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) throw new Error(`Chatterbox ${res.status}: ${await res.text()}`);
    return { audio: Buffer.from(await res.arrayBuffer()), mime: res.headers.get("content-type") || "audio/wav" };
  },
};

/** Synthesize speech. Returns null when the browser should speak it itself. */
export async function synthesize(text) {
  const provider = providers[config.tts.provider];
  if (!provider) return null;
  return provider(text);
}
