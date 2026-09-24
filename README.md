# NOZE — Jarvis HQ

Jarvis adalah asisten pribadi AI dengan gaya **butler**: sopan dan tertata, tapi bisa diajak bercanda. Dia bisa diajak ngobrol lewat **HQ dashboard** (teks atau suara) dan lewat **WhatsApp**, mengingat hal-hal penting tentang lu, dan bisa ngecek proyek-proyek lu yang lain.

```
            ┌──────────── HQ dashboard (browser) ────────────┐
  lu ──mic──▶  speech-to-text (browser)  ─┐        ┌─▶ orb + suara
            └─────────────────────────────┼────────┼──────────┘
                                          ▼        │
  WhatsApp ──▶ Baileys bridge ──▶  src/brain.js (Claude + tools) ──▶ src/tts.js
                                    │  memori · proyek · web search      │
                                    ▼                                     ▼
                              data/ (lokal)            ElevenLabs / OpenAI / Chatterbox / browser
```

## Mulai cepat

Butuh **Node.js 20.6+**.

```bash
npm install
cp .env.example .env      # isi ANTHROPIC_API_KEY minimal
npm start
```

Buka **http://127.0.0.1:3000** — itu HQ-nya. Pakai Chrome/Edge supaya mic (pengenalan suara bahasa Indonesia) jalan.

- Klik 🎤 atau tekan **Space** untuk bicara, **Esc** untuk memotong Jarvis.
- **Mode ngobrol**: setelah Jarvis selesai bicara, mic otomatis nyala lagi — kayak ngobrol beneran.
- Panel kanan: status sistem, QR WhatsApp, status proyek, dan daftar ingatan (bisa dihapus).

API key Claude diambil dari [console.anthropic.com](https://console.anthropic.com) — ini **terpisah** dari langganan claude.ai (ditagih per pemakaian).

## Suara

Atur `TTS_PROVIDER` di `.env`:

| Provider | Kualitas | Bahasa Indonesia | Biaya | Catatan |
|---|---|---|---|---|
| `elevenlabs` | ⭐ paling natural | ✅ bagus | berbayar | **Rekomendasi.** Pilih suara wanita soft-spoken di Voice Library, isi `ELEVENLABS_VOICE_ID`. |
| `openai` | bagus | ✅ | berbayar, murah | Bisa diarahkan gayanya lewat instruksi (sudah diset: lembut, hangat, rounded). |
| `chatterbox` | sangat natural (open-source) | ⚠️ belum resmi — pakai Malay (`ms`), aksen bisa agak melayu | gratis | Jalan lokal, butuh GPU. Bisa kloning warna suara dari rekaman 10–20 detik. |
| `browser` | standar | ✅ | gratis | Default, tanpa setup. |

Tips dapet suara "soft spoken, rounded":
- **ElevenLabs**: cari di Voice Library dengan kata kunci *soft, calm, warm, whisper-y, gentle*. Setting stabilitas sudah diset agak rendah (0.45) biar ekspresif tapi tenang. Model `eleven_multilingual_v2` untuk Indonesia; coba `eleven_v3` kalau mau lebih ekspresif.
- **Chatterbox lokal**:
  ```bash
  cd voice
  python -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  # taruh rekaman referensi di voice/ref.wav (suara yang kamu punya hak/izinnya)
  python chatterbox_server.py
  ```
  Lalu set `TTS_PROVIDER=chatterbox`. Atur `CHATTERBOX_EXAGGERATION` (lebih rendah = lebih kalem).

Teks dikirim ke TTS per kalimat selagi Jarvis masih "ngetik", jadi dia mulai bicara tanpa nunggu jawaban selesai.

## WhatsApp

```env
WHATSAPP_ENABLED=true
WHATSAPP_OWNER=628xxxxxxxxxx
```

Restart, lalu scan QR yang muncul di panel **Sistem** di HQ (WhatsApp → Perangkat tertaut → Tautkan perangkat). Jarvis **hanya** membalas nomor di `WHATSAPP_OWNER`; pesan dari orang lain dan grup diabaikan.

> ⚠️ Ini pakai [Baileys](https://github.com/WhiskeySockets/Baileys) (WhatsApp Web tidak resmi). Ada risiko nomor diblokir WhatsApp. Paling aman pakai **nomor kedua** khusus Jarvis, lalu chat ke nomor itu dari nomor utama lu. Versi resmi (WhatsApp Business Cloud API) bisa ditambahkan nanti.

Voice note belum didukung — Jarvis akan minta diketik.

## Menghubungkan proyek lain

Tambahkan proyek di `config/projects.json`:

```json
{
  "name": "Toko Online",
  "description": "Web jualan, Next.js di Vercel",
  "repo": "https://github.com/nozeoz/toko",
  "url": "https://toko.example.com",
  "healthUrl": "https://toko.example.com/api/health"
}
```

Jarvis bisa menyebutkan daftar proyek dan mengecek apakah proyek sedang online ("Jarvis, toko online aman?"). Kemampuan baru ditambahkan sebagai tool di `src/tools.js`.

## Struktur

| Path | Isi |
|---|---|
| `src/brain.js` | Loop percakapan dengan Claude (streaming, tools, web search) |
| `src/persona.js` | Kepribadian Jarvis — edit di sini kalau mau ubah gaya bicaranya |
| `src/tools.js` | Kemampuan Jarvis (ingat/lupa, jam, proyek) |
| `src/tts.js` | Penyedia suara |
| `src/whatsapp.js` | Bridge WhatsApp |
| `src/server.js` | Server HQ + API |
| `hq/` | Dashboard |
| `voice/` | Server TTS lokal Chatterbox |
| `data/` | Memori, riwayat chat, sesi WhatsApp (tidak di-commit) |

## Keamanan

- HQ default hanya bisa diakses dari komputer sendiri (`HOST=127.0.0.1`). Kalau mau dibuka dari HP/jaringan, **wajib** isi `HQ_TOKEN`.
- `.env` dan `data/` tidak ikut ke git.
