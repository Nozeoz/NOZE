# NOZE Studio — perusahaan clipper otomatis

`noze agency` adalah studio clipping yang dijalankan satu tim agent: **Manager**, **Scout**, **Analyst**, **Editor**, dan **Reviewer**. Tim ini mengubah video panjang creator jadi clip vertikal (TikTok / Reels / Shorts), dari cari kerjaan sampai upload dan laporan. Studio ini nempel di bank NOZE, jadi referensi, musik, dan SFX bisa diambil dari bank kamu sendiri.

```
                ┌──────────── MANAGER / SUPERVISOR ────────────┐
                │ cari campaign clipping yang lagi buka        │
                │ → kualifikasi → brief + bukti izin           │
                │ bagi tugas · monitor · ACC final · upload    │
                │ · laporan tim                                 │
                └──┬───────────────────────────────────────▲───┘
                   ▼                                       │ lolos review
   SCOUT ──► ANALYST ──► EDITOR ──► REVIEWER ──────────────┘
   referensi  breakdown   rencana    QC terukur + review kreatif
              script →    edit (EDL) → kalau gagal: balik ke editor dengan
              kerangka    → render     poin-poin bertimecode
              video →                  (maks N ronde, lalu eskalasi
              kerangka                  ke manager)
              edit → flow
              + cari momen

   Semua tugas lewat state machine di kode. Yang "belajar" cuma playbook tiap role
   (lesson pendek, ada counter, diuji dulu, bisa rollback otomatis).
```

## Mulai

Butuh **ffmpeg** (dengan libass, sudah standar di hampir semua build) dan Python 3.10+.

```bash
pip install -e ".[agency,transcribe]"   # anthropic SDK + faster-whisper
export ANTHROPIC_API_KEY=sk-ant-...      # atau `ant auth login`; tanpa key studio tetap jalan pakai heuristik
noze agency init                         # bikin folder, unduh font caption (OFL), siapkan 9 SFX bawaan, cek tools
```

**1. Daftarkan campaign.** Tempel syarat campaign apa adanya. Teks ini jadi brief sekaligus bukti bahwa creator memang mengundang clipper:

```bash
noze agency campaign add grind --url https://whop.com/... --terms-file syarat.txt
```

**2. Masukkan video sumber.** Drop file ke `noze-data/agency/inbox/grind/` (studio mengambilnya sendiri), atau:

```bash
noze agency submit episode12.mp4 --campaign grind --clips 3
noze agency submit vlog.mp4 --own        # konten milikmu sendiri
```

**3. Jalankan.** Pilih salah satu:

```bash
noze agency run            # proses antrean sampai habis
noze agency run --forever  # jalan terus, ngecek inbox tiap beberapa detik
AGENCY_AUTORUN=1 noze serve   # jalan di background web app
```

**4. Pantau.** Buka dashboard di **http://localhost:8787/agency**:
- board per tahap,
- player video dan riwayat review,
- tombol approve / minta revisi / tolak,
- laporan tim, playbook, leads.

Dari terminal: `noze agency status`, `noze agency show <id>`, `noze agency report`.

Hasil akhir ada di `noze-data/agency/deliveries/<campaign>/<tanggal>/`: video `.mp4`, file `.txt` berisi caption, hashtag, dan link submit, plus laporan per clip.

## Siapa mengerjakan apa

Setiap role punya tiga lapis, dari yang paling kaku sampai paling cair:
- **SOP**: cara berpikir profesional, di [`noze/agency/sop/`](../noze/agency/sop). Ini statis dan direview manusia.
- **Playbook**: pelajaran dari job-job sebelumnya, yang cair.
- **Kontrak JSON**: format serah-terima ke role berikutnya, di [`schemas.py`](../noze/agency/schemas.py).

Kalau Claude tidak tersedia (tidak ada key, budget habis, atau error), tiap role punya **fallback deterministik**. Pekerjaan tidak pernah macet.

| Role | Tugas | Output |
|---|---|---|
| **Manager** | Mencari leads lewat jalur yang diizinkan (lihat bawah), menilai skor & risiko, menulis brief dan bukti izin. Memilih momen terbaik dan membagi tugas. Memantau job macet, gagal, dan budget. Memberi ACC final sebagai creative director (melihat frame + hasil review + brief). Mengirim hasil dan menulis laporan. | `Brief`, `LeadQualification`, `Approval`, laporan |
| **Scout** | Mengumpulkan kandidat referensi lalu memilih 1–3 yang paling cocok. Urutan sumber: contoh dari creator di brief, clip kita yang performanya paling bagus di campaign ini (pakai data views), folder `assets/references/`, video yang di-*save* di bank NOZE. | `ReferencePick` |
| **Analyst** | Membedah tiap referensi. Datanya **terukur**: panjang shot, cut/menit, loudness, jeda, onset, WPM, transkrip, dan contact sheet untuk vision. Hasilnya: script (hook, beat, payoff), kerangka video, kerangka edit (caption, zoom, transisi, warna), sound, dan trik retensi. Semua digabung jadi **blueprint**. Analyst juga membaca seluruh transkrip sumber untuk mencari **momen** (skor hook/flow/value/trend/emotion), lalu batasnya di-*snap* ke batas kalimat. | `ReferenceBreakdown`, `Blueprint`, `Moments` |
| **Editor** | Menulis **EDL** lengkap yang dieksekusi renderer persis seperti tertulis: potong rapat (jeda & filler dibuang), reframe per segmen, punch-in/push/pull, shake, transisi, hook title, label, CTA, caption, SFX, musik + ducking, warna, progress bar, teks post. Saat revisi, editor memperbaiki **setiap** poin dan mencatat issue-id → perubahan. | `EditPlan` + video |
| **Reviewer** | QC teknis terukur (lihat bawah), lint caption dan compliance, review kreatif lewat frame bertimecode, serta verifikasi fix dari ronde sebelumnya. Gagal kalau ada blocker/major atau skor < 7/10. | `Review` berisi poin bertimecode + instruksi fix |

### Alur (state machine)

```
source:  queued → research → select → producing → done
clip:    planning → rendering → reviewing ─lolos→ approval ─ACC→ approved → delivered
                        ▲            │gagal                │minta revisi
                        └─ revising ◄┘ (ronde < maks)      └─tolak→ rejected
                                     └─(ronde = maks)→ escalated → approved | rejected
```

- Tiap langkah menyimpan artefaknya dulu sebelum pindah state. Kalau proses mati, job lanjut dari titik terakhir (job di-*lease*, bukan di-*lock*).
- Error dicoba ulang dengan backoff, maksimal 3 kali, lalu `failed` dan manager memberi alert.
- Plan yang gagal di-render dikembalikan ke editor sebagai issue `technical:render_failed`.

Dengan `AGENCY_AUTO_APPROVE=0`, setiap clip berhenti di `awaiting_human` dan menunggu keputusanmu (dashboard atau `noze agency approve|changes|reject <id> --note "…"`).

## Mesin edit (yang benar-benar dirender)

Renderer ([`media/render.py`](../noze/agency/media/render.py)) berbasis ffmpeg + libass dan tidak butuh compositor tambahan. Kerjanya dua tahap:
1. Tiap segmen dirender dan di-*cache*. Saat revisi hanya caption/SFX yang berubah, segmen tidak dirender ulang.
2. Segmen dirakit, lalu diberi caption, dan audionya di-mix.

| Bagian | Pilihan |
|---|---|
| Reframe 16:9 → 9:16 | `center`, `fixed` (x subjek 0–1: dari Claude vision, atau OpenCV kalau terpasang), `fit_blur` (video utuh di atas background blur), `fill` |
| Zoom | `punch` (cepat 0.15 s, ganti framing tiap jump cut), `push` / `pull` (Ken Burns halus lewat zoompan di upscale 2×) |
| Gerak & transisi | `shake` (decay 0.35 s), `cut`, `flash` (putih), `fade` (dip), `whip` (motion blur horizontal), `zoom` (masuk 25% lalu settle) |
| Caption | `bold_pop` (kata aktif di-highlight + pop), `karaoke` (fill `\kf`), `minimal`, `boxed`, `outline`. Ukuran tiap caption 1–6 kata, posisi `upper`/`center`/`lower`, selalu di dalam safe zone platform |
| Teks motion | `hook_title`, `label`, `cta` dengan animasi `pop` / `slide` / `fade` / `typewriter` |
| Sound | 9 SFX bawaan hasil sintesis (`whoosh`, `swoosh`, `pop`, `click`, `hit`, `boom`, `riser`, `ding`, `glitch`). File di `assets/sfx/<jenis>*.wav` lebih diutamakan. Musik diambil dari `assets/music/` atau dari bank NOZE (hanya lisensi *usable*), di-loop, fade, dan **sidechain-ducked** di bawah suara |
| Finishing | Warna (`punchy` / `warm` / `cool` / `bw` / `cinematic`, atau LUT), progress bar, H.264 High yuv420p, AAC 48 kHz, **loudnorm dua pass** ke −14 LUFS dengan true peak ≤ −1.5 dBTP |

Font caption: `noze agency init` mengunduh Montserrat ExtraBold/Black dan Anton (OFL) ke `assets/fonts/`.

## QC Reviewer (tidak butuh LLM)

| Cek | Ambang |
|---|---|
| Resolusi, fps, codec, audio, ukuran file | sesuai spesifikasi delivery |
| Loudness / true peak | −14 ±1 LUFS, ≤ −1 dBTP |
| Hook | ada suara dalam 0.6 s; perubahan visual atau hook title dalam 1.6 s |
| Dead air | diam > 0.8 s = major (editor memotong rentang diam **yang terukur**) |
| Frame hitam / beku | hitam > 0.1 s (di luar dip yang disengaja), beku ≥ 1.5 s |
| Statis | tidak ada perubahan visual > 5 s |
| Caption | wajib kalau brief minta; kecepatan baca ≤ ~20 karakter/detik |
| Compliance | hashtag, mention, disclosure di 3 detik pertama dan di caption, CTA, kata terlarang, panjang clip |

Angka-angka ini ada di [`standards.py`](../noze/agency/standards.py), yang berfungsi sebagai "konstitusi". Pembelajaran **tidak bisa** melonggarkannya. Safe zone per platform (TikTok/Reels/Shorts) diambil dari template iklan resmi masing-masing platform.

Hashtag, mention, dan disclosure wajib dipasang ulang secara otomatis di dua titik: di setiap plan, dan sekali lagi saat delivery. Jadi tidak ada langkah (termasuk model) yang bisa menghilangkannya.

## Mencari kerja (leads), legal dan aman

Hasil riset Oktober 2026:
- **Whop Content Rewards, contentrewards.com, Vyro, ClipFarm**: tidak punya API untuk listing campaign, dan ToS-nya melarang scraping atau akses otomatis.
  - Studio **tidak pernah** mengambil halaman dari domain itu.
  - Buka campaign-nya, salin syaratnya, lalu jalankan `noze agency lead add <url> --terms-file syarat.txt`.
  - Manager akan memberi skor, menulis brief, mencatat kalimat izin, dan menyiapkan draft pesan lamaran. Draft ini **tidak pernah dikirim otomatis**.
- **Whop Bounties API** (resmi, beta): bounty clipping yang sedang buka untuk akunmu → `WHOP_API_KEY`.
- **Reddit API resmi**: r/VideoEditors_forhire, r/HireAnEditor, dll.
  - Butuh kredensial yang **sudah disetujui** Reddit.
  - Permintaan akses baru ditutup 31 Okt 2026, dan Data API publik ditutup Maret 2027.
- **YouTube search** "clipping campaign" (`YOUTUBE_API_KEY`).
- **RSS/Atom** yang kamu percaya (`AGENCY_LEAD_FEEDS`).
- **Discord, TikTok**: manual.

```bash
noze agency lead scout          # tarik dari semua sumber yang dikonfigurasi + kualifikasi
noze agency lead list
noze agency lead accept 7       # lead → campaign (brief + bukti izin)
```

Selama studio jalan terus (`run --forever` / `AGENCY_AUTORUN=1`), manager otomatis scouting tiap `AGENCY_LEAD_SCOUT_EVERY_H` jam (default 12) dan ngabarin lead yang layak ke webhook/Telegram-mu.

**Gerbang izin.** Video dari campaign tanpa bukti izin akan berhenti di `awaiting_human` dengan penjelasan. Konten sendiri ditandai dengan `--own`.

Aturan campaign yang sering muncul ikut ditangkap ke brief, antara lain:
- "use only provided footage",
- "no networks" (satu akun personal per clipper),
- disclosure di awal video,
- minimal views sebelum payout.

## Upload & laporan

- **Selalu:** clip dan caption dikirim ke folder `deliveries/`.
- **Opsional** (`AGENCY_PUBLISH_TARGETS`):
  - `rclone` ke Google Drive, Dropbox, OneDrive, R2, dll.
  - `webhook` ke Discord, Slack, atau Telegram.
  - `youtube`: Shorts ke channel **kamu**, via OAuth refresh token. Privasi default `private`. Bisa jadi upload dari project API yang belum diverifikasi tetap terkunci private; dokumentasi Google sendiri tidak konsisten soal ini.
  - `tiktok`: masuk ke **inbox TikTok kamu** sebagai draft (scope `video.upload`), lalu kamu yang menekan post. TikTok tidak mengizinkan tool agensi melakukan direct-post.
- Upload ke platform hanya terjadi kalau `AGENCY_AUTO_PUBLISH=1`, atau kamu menjalankan `noze agency publish <id> --target youtube`.
- **Submit ke campaign** (Whop dan sejenisnya) tetap manual karena tidak ada API-nya. Link submit sudah tertulis di file `.txt`.

Laporan:
- **Per clip** (`reports/clips/`): alasan momen dipilih, data output, riwayat review per ronde, fix yang dikerjakan editor, keputusan manager, caption post, dan biaya LLM.
- **Per batch** (`reports/sources/`).
- **Laporan tim** (`noze agency report [--days 7] [--notify]`) berisi:
  - throughput,
  - KPI tiap "karyawan": first-pass editor, rata-rata ronde, eskalasi, isu per clip, *miss* reviewer yang ketahuan manager atau kamu, hit-rate momen analyst, leads,
  - masalah yang berulang,
  - biaya per role,
  - data audiens,
  - perubahan playbook.

Laporan tim juga dibuat otomatis tiap `AGENCY_REPORT_EVERY_H` jam (default 24) selama studio jalan, dan dikirim ke webhook/Telegram kalau dikonfigurasi.

Masukkan performa clip yang sudah diposting supaya studio belajar dari audiens sungguhan. Scout lalu memprioritaskan clip terbaikmu sebagai referensi:

```bash
noze agency metrics 42 --views 18300 --retention 0.62 --url https://www.tiktok.com/@kamu/video/...
```

## Sistem belajar (cair, tapi flow tetap utuh)

Yang **tidak pernah** berubah karena pembelajaran:
- state machine,
- kontrak JSON,
- standar QC,
- batas ronde,
- gerbang izin.

Yang **tumbuh** adalah playbook tiap role. Siklus per clip yang selesai:

1. **Kredit.** Setiap role mengembalikan `used_lessons`, yaitu id lesson yang benar-benar dipakai. Lesson muncul di prompt dengan format ACE: `[edi-00012] helpful=5 harmful=0 :: Punch in on the first stressed word of the hook.`
2. **Refleksi.** Claude membaca jejak job: plan v1 → tiap review → fix → keputusan manager → miss reviewer. Hasilnya: tag *helpful/harmful* untuk lesson yang dipakai, dan maksimal 3 lesson baru. Refleksi hanya jalan kalau ada sinyal yang bisa diverifikasi (review atau approval).
3. **Kurasi deterministik** (delta, tidak pernah menulis ulang semuanya). Setiap operasi divalidasi:
   - panjang teks,
   - **tidak boleh melemahkan QC, brief, atau izin**,
   - lesson untuk reviewer hanya boleh membuat review *lebih tajam*, tidak lebih longgar,
   - dedup: ADD yang mirip lesson lama otomatis jadi UPVOTE,
   - maksimal 1 operasi per lesson per job.
4. **Trial.** Lesson baru berstatus *candidate* dan hanya dimuat di sebagian job (canary, `AGENCY_CANARY_SHARE`, default 20%).
5. **Promosi.** Candidate jadi *active* kalau `uses ≥ 3`, `helpful − harmful ≥ 2`, dan `harmful/uses < 0.2`. Maksimal 3 promosi per role per hari. Lesson dengan `harmful ≥ 2` dan `harmful ≥ helpful` diarsipkan. Batas: 25 lesson aktif per role.
6. **Miner isu berulang.** Isu QC yang terus muncul di review ronde pertama (≥ 30% dari 20 clip terakhir) otomatis menjadi aturan *preflight* untuk editor. Jadi masalahnya dicegah sejak tahap perencanaan, bukan baru ketahuan saat review.
7. **Regression guard.** Studio membandingkan first-pass rate dan eskalasi dari 10 clip terakhir dengan 10 clip sebelumnya. Kalau kualitas turun (first-pass −10 poin, atau eskalasi ×1.5), semua lesson yang mulai berlaku di antara dua periode itu **dikarantina otomatis**. Ini rollback ke kondisi terakhir yang diketahui bagus.
8. **Memori pendek tetap pendek.** Catatan revisi gaya Reflexion (3 ronde terakhir) hanya hidup di dalam job.

Kendali manusia:
- `noze agency playbook` — lihat isi playbook.
- `playbook add --role editor --text "…"` — lesson buatanmu langsung aktif dan kebal pruning.
- `playbook retire|restore <id>`
- `playbook versions`
- `noze agency learn` — paksa promosi, miner, dan guard jalan sekarang.

Semua ini juga ada di tab Playbook di dashboard.

Referensi riset (repo dan paper yang diamati, apa yang diambil, dan apa yang di-upgrade) ada di [AGENCY_REFERENCES.md](AGENCY_REFERENCES.md).

## Biaya

- Default model: `claude-opus-5-5` untuk semua role, dengan *effort* per role: manager `medium`, scout `low`, analyst/editor/reviewer `high`. Bisa diganti per role (`AGENCY_MODEL_EDITOR`, `AGENCY_EFFORT_REVIEWER`, …).
- SOP dan playbook di-*cache* sebagai system prompt.
- Budget: `AGENCY_JOB_BUDGET_USD` (per video sumber) dan `AGENCY_DAILY_BUDGET_USD`. Kalau habis, role memakai heuristik dan manager memberi peringatan.
- Biaya tercatat per panggilan (`llm_usage`) dan muncul di laporan.
- **Refusal fallback** server-side aktif (`AGENCY_FALLBACKS=1`): kalau model menolak sebuah request, API otomatis mencoba model fallback.

## Pakai dari Claude Code

Folder [`.claude/agents/`](../.claude/agents) berisi lima subagent (`clip-manager`, `clip-scout`, `clip-analyst`, `clip-editor`, `clip-reviewer`). Mereka memakai SOP yang sama dan menyetir studio lewat CLI `noze agency`. Contoh: "manager, cek status tim dan kasih laporan", atau "reviewer, cek ulang clip 12 dari sisi compliance".

## Kalau ada masalah

- `noze agency doctor` — cek ffmpeg/libass, transkripsi, yt-dlp, OpenCV, Claude, font, target publish, sumber leads, budget.
- **Tidak ada caption:** pasang `faster-whisper`, atau taruh `video.srt` / `video.en.vtt` di sebelah file video. yt-dlp menulis subtitle otomatis kalau `AGENCY_ALLOW_DOWNLOAD=1`.
- **Job berhenti di `awaiting_human`:** jalankan `noze agency show <id>`. Penyebab umum: tidak ada bukti izin, atau clip menunggu ACC-mu. Setelah diperbaiki, jalankan `noze agency retry <id>`.
- **Font caption tidak sesuai:** libass diam-diam memakai font lain kalau nama font salah. Pastikan font ada di `assets/fonts/` (`noze agency init`).
