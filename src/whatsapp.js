import path from "node:path";
import QRCode from "qrcode";
import { config, DATA_DIR } from "./config.js";
import { think } from "./brain.js";

// Unofficial WhatsApp Web bridge via Baileys. Jarvis links as a device on the
// owner's (or a dedicated) number and only ever answers the numbers in WHATSAPP_OWNER.
export const waState = { status: "disabled", qrDataUrl: null, me: null, lastError: null };

const digits = (jid) => (jid || "").split("@")[0].split(":")[0].replace(/\D/g, "");

function senderNumbers(key) {
  // Newer WhatsApp may address chats by LID; the phone number then sits in an alt field.
  return [key.remoteJid, key.remoteJidAlt, key.senderPn, key.participant, key.participantPn]
    .filter((j) => j && !j.endsWith("@lid"))
    .map(digits);
}

function textOf(message) {
  return (
    message?.conversation ||
    message?.extendedTextMessage?.text ||
    message?.imageMessage?.caption ||
    message?.videoMessage?.caption ||
    ""
  ).trim();
}

export async function startWhatsApp() {
  if (!config.whatsapp.enabled) return;
  if (config.whatsapp.owners.length === 0) {
    waState.status = "error";
    waState.lastError = "WHATSAPP_OWNER belum diisi — demi keamanan WhatsApp tidak dinyalakan.";
    console.warn(`[wa] ${waState.lastError}`);
    return;
  }

  let baileys, pino;
  try {
    baileys = await import("@whiskeysockets/baileys");
    pino = (await import("pino")).default;
  } catch {
    waState.status = "error";
    waState.lastError = "Paket @whiskeysockets/baileys belum terpasang (npm install).";
    console.warn(`[wa] ${waState.lastError}`);
    return;
  }
  const makeWASocket = typeof baileys.default === "function" ? baileys.default : baileys.default?.default || baileys.makeWASocket;
  const { useMultiFileAuthState, DisconnectReason } = baileys;
  const { state, saveCreds } = await useMultiFileAuthState(path.join(DATA_DIR, "whatsapp-auth"));

  const connect = () => {
    waState.status = "connecting";
    const sock = makeWASocket({ auth: state, logger: pino({ level: "silent" }), markOnlineOnConnect: false });
    sock.ev.on("creds.update", saveCreds);

    sock.ev.on("connection.update", async ({ connection, lastDisconnect, qr }) => {
      if (qr) {
        waState.status = "waiting_for_scan";
        waState.qrDataUrl = await QRCode.toDataURL(qr);
        console.log("[wa] Scan QR di HQ dashboard (WhatsApp → Perangkat tertaut → Tautkan perangkat).");
      }
      if (connection === "open") {
        waState.status = "connected";
        waState.qrDataUrl = null;
        waState.me = sock.user?.id ? digits(sock.user.id) : null;
        console.log(`[wa] Terhubung sebagai ${waState.me}`);
      }
      if (connection === "close") {
        const code = lastDisconnect?.error?.output?.statusCode;
        if (code === DisconnectReason.loggedOut) {
          waState.status = "logged_out";
          waState.lastError = "Perangkat di-logout dari HP. Hapus data/whatsapp-auth lalu restart untuk scan ulang.";
          console.warn(`[wa] ${waState.lastError}`);
        } else {
          waState.status = "reconnecting";
          setTimeout(connect, 3000);
        }
      }
    });

    sock.ev.on("messages.upsert", async ({ messages, type }) => {
      if (type !== "notify") return;
      for (const msg of messages) {
        const jid = msg.key.remoteJid;
        if (!msg.message || msg.key.fromMe || !jid || jid.endsWith("@g.us") || jid === "status@broadcast") continue;

        const from = senderNumbers(msg.key);
        const owner = from.find((n) => config.whatsapp.owners.includes(n));
        if (!owner) {
          console.log(`[wa] Pesan dari ${from.join("/") || jid} diabaikan (bukan owner).`);
          continue;
        }

        const text = textOf(msg.message);
        await sock.readMessages([msg.key]).catch(() => {});
        if (!text) {
          const note = msg.message.audioMessage
            ? `Mohon maaf, ${config.honorific}, telinga saya di WhatsApp belum bisa mendengar voice note. Boleh diketik saja?`
            : `Pesan itu belum bisa saya baca, ${config.honorific}. Teks saja, ya.`;
          await sock.sendMessage(jid, { text: note });
          continue;
        }

        try {
          await sock.sendPresenceUpdate("composing", jid);
          const reply = await think({ threadId: `whatsapp-${owner}`, text, channel: "whatsapp" });
          await sock.sendMessage(jid, { text: reply || "…" });
        } catch (err) {
          console.error("[wa] Gagal membalas:", err);
          await sock.sendMessage(jid, { text: `Maaf, ${config.honorific}, ada gangguan di sistem saya. Coba sebentar lagi.` });
        } finally {
          sock.sendPresenceUpdate("paused", jid).catch(() => {});
        }
      }
    });
  };

  connect();
}
