# Referensi: dari repo & paper apa saja studio ini belajar

Sebelum membangun, kami membaca kode dan dokumentasi repo serta paper berikut (Oktober 2026). Tidak ada yang dijiplak: tiap baris di bawah menjelaskan **apa yang kami amati → apa yang diambil → apa yang diubah atau di-upgrade**, plus di mana hasilnya di kode.

## 1. Organisasi tim & SOP

| Sumber | Yang diamati | Dipakai di NOZE Studio |
|---|---|---|
| **MetaGPT** (FoundationAgents/MetaGPT), "Code = SOP(Team)" | Tiap role = profil + tujuan + batasan + aksi. Role berlangganan pesan role lain lewat *message pool*. Serah-terima berupa artefak terstruktur (`ActionNode`), bukan chat bebas. | Kontrak JSON per serah-terima ([`schemas.py`](../noze/agency/schemas.py)). SOP per role di [`sop/`](../noze/agency/sop). Tabel `events` jadi *message pool* yang bisa diaudit. **Upgrade:** setiap kontrak punya `conform()`, jadi output Claude, heuristik, atau manusia selalu pas di role berikutnya. |
| **ChatDev** (OpenBMB/ChatDev) | "Perusahaan" berisi role + *chat chain* bertahap. Fase review→modifikasi dibatasi `cycleNum: 3`. Reviewer menulis komentar prioritas tertinggi atau `<INFO> Finished`. | Loop Editor↔Reviewer dibatasi `AGENCY_MAX_ROUNDS` (default 3). Setelah itu eskalasi ke manager. **Upgrade:** reviewer memberi **semua** isu bertimecode dengan severity dan instruksi fix yang bisa langsung dieksekusi. Editor wajib memetakan issue-id → perubahan. Isu ronde lalu diverifikasi (`resolved_previous`). |
| **CrewAI**, *hierarchical process* | Manager mendelegasikan ke "coworker" dan memvalidasi hasil. Ada `guardrail` per task dan `guardrail_max_retries`. | Manager memilih momen, membagi tugas, dan memberi ACC final. **Beda:** delegasi tidak diserahkan ke LLM. Yang mendelegasikan adalah state machine di kode, supaya flow tidak bisa "dikreasikan" model. |
| **LangGraph** | Graf state + checkpointer + `interrupt()` untuk human-in-the-loop. Node diulang dari awal saat resume. | [`pipeline.py`](../noze/agency/pipeline.py): artefak disimpan sebelum state pindah, job di-*lease* (bisa lanjut setelah crash), dan ada state `awaiting_human`. Langkah dibuat idempoten, termasuk cache segmen render. |
| **OpenAI Agents SDK** | *Guardrails* dengan tripwire, *handoffs*. | Gerbang izin (`Blocked`) dan QC sebagai tripwire yang tidak bisa dilewati. |
| **Anthropic, "Building effective agents"** | Pola *evaluator-optimizer* dan *orchestrator-workers*. Gate terprogram di antara langkah. Batas iterasi. "Poka-yoke your tools." | Reviewer = evaluator dengan kriteria terukur. Fungsi `finalize()`/`comply_post()` = poka-yoke: hashtag/mention/disclosure wajib dipasang ulang di setiap plan dan saat delivery, jadi tidak bisa hilang. |

## 2. Belajar terus tanpa merusak flow

| Sumber | Yang diamati | Dipakai |
|---|---|---|
| **ACE — Agentic Context Engineering** (ace-agent/ace, arXiv 2510.04618) | *Playbook* berupa bullet `[id] helpful=X harmful=Y :: teks`. Generator mengembalikan id bullet yang dipakai. Reflector memberi tag helpful/harmful. Curator hanya menambah **delta**. Peringatan soal *context collapse* (rewrite penuh: 18k → 122 token, akurasi jatuh) dan *brevity bias*. Di kode rilisnya hanya operasi ADD yang jalan. Dedup ≥ 0.90 cosine dimatikan secara default. | Format bullet dan `used_lessons` ([`learning.py`](../noze/agency/learning.py)). Kurasi delta saja. **Upgrade:** UPVOTE/archive/quarantine benar-benar jalan. Dedup selalu aktif (n-gram + Jaccard, tanpa model embedding). Kredit hanya diberikan ke lesson yang *benar-benar dipakai* di job itu. |
| **ExpeL** (LeapLabTHU/ExpeL) | Operasi ADD/EDIT/AGREE/REMOVE dengan *importance count*: ADD mulai dari 2, REMOVE −3 kalau pool penuh. Maks 4 operasi per refleksi, 1 operasi per rule. Rule yang tidak diakhiri "." ditolak (output terpotong). | Maks 6 operasi per job dan 1 per lesson. Lesson dirapikan agar diakhiri titik. Batas 25 lesson aktif per role, pruning berdasarkan skor. **Upgrade:** validator keamanan, yaitu lesson yang melemahkan QC/brief/izin ditolak dan lesson reviewer dilarang lebih longgar. |
| **Reflexion** | Refleksi verbal setelah gagal, memori dibatasi 1–3 entri. | Catatan revisi per job (3 ronde terakhir) hanya hidup di job dan tidak bocor ke playbook jangka panjang. |
| **Dynamic Cheatsheet** | Rewrite penuh cheatsheet. Kalau output rusak, cheatsheet lama dipertahankan. | Pelajaran yang diambil: **jangan** rewrite penuh. Output refleksi yang rusak = playbook tidak berubah. |
| **Voyager** | Skill disimpan hanya kalau critic bilang sukses. Versi baru = file baru (`V2`). | Lesson hanya dipelajari dari job yang punya sinyal terverifikasi (review/approval). Setiap perubahan playbook = versi baru (`playbook_versions`). |
| **Agent Workflow Memory** | Workflow sebagai *makro kaku* malah menurunkan sukses. | Lesson = **panduan**, bukan makro. Eksekusi tetap lewat EDL dan renderer. |
| **ChatDev IER** | Hit ratio pool pengalaman turun kalau terus menumpuk. Seleksi berdasarkan *information gain* + frekuensi. | Pruning berdasarkan `helpful − harmful` dan `uses`. Lesson yang sering dipakai tapi merugikan diarsipkan. |
| *Desain kami sendiri* | — | **Trial canary**: lesson baru hanya dimuat di 20% job. **Promosi bergerbang**: uses ≥ 3, net ≥ 2, harmful/uses < 0.2, maks 3 per hari. **Miner isu berulang**: QC yang sering gagal menjadi aturan *preflight* editor. **Regression guard**: kalau first-pass rate turun ≥ 10 poin atau eskalasi ×1.5, lesson yang berlaku di periode itu dikarantina otomatis (rollback ke kondisi terakhir yang bagus). |

## 3. Mencari momen

| Sumber | Yang diamati | Dipakai |
|---|---|---|
| **ClipsAI** (ClipsAI/clipsai) | TextTiling dengan embedding kalimat. Batas segmen dari *depth score*. Dedup kalau \|Δstart\|+\|Δend\| < 15 s. Tidak ada skor viral. | Analyst membaca seluruh transkrip (chunk 40k karakter dengan overlap supaya momen tidak terbelah). Dedup kalau overlap > 50%. |
| **AI-Youtube-Shorts-Generator** (SamurAIGPT) | Prompt highlight: hook dalam 3 s, "never cut mid-sentence", skor 0–100, transkrip format `[12.3s] text`. | Transkrip bertimestamp untuk prompt. `snap_moment()` memindahkan batas ke awal/akhir kalimat, lalu memberi padding. Momen yang tidak bisa memenuhi panjang minimum dibuang. |
| **OpusClip virality score** | Dimensi Hook / Flow / Value / Trend. | Skor hook, flow, value, trend + **emotion**. Bobot overall: hook 0.35, value 0.25, flow 0.2, trend 0.1, emotion 0.1. |
| **FunClip** (modelscope) | LLM memilih segmen dari SRT. Segmen kontinu digabung. | Fallback heuristik bilingual (EN/ID): kata hook, pembuka lemah ("terus", "jadi", "and", "so"), payoff berakhiran tanda baca, laju bicara. |

## 4. Edit, caption, audio, QC

| Sumber | Yang diamati | Dipakai |
|---|---|---|
| **ShortGPT** editing engine, **editly**, **Remotion** | Spec edit deklaratif (layer, `cutFrom/cutTo`, `resizeMode: contain-blur/cover`, audioTracks + mixVolume, Ken Burns `zoomAmount`). | EDL `EditPlan`: segmen di waktu sumber, overlay dan SFX di waktu output, `reframe.mode` (`fit_blur` ≈ contain-blur), zoom punch/push/pull. **Upgrade:** pemetaan waktu sumber↔output yang eksak ([`timeline.py`](../noze/agency/media/timeline.py)) untuk caption, SFX, dan timecode review. Ada juga `remove_output_range()` untuk memotong dead air hasil ukur QC. |
| **auto-editor** (WyattBlue) | Ambang audio + margin 0.2 s, minimum cut/clip. | `jump_cut()`: jeda > 0.45 s dan filler (um/uh/ehm/anu…) dibuang, padding 0.08 s, tidak ada potongan di tengah kata. |
| **PySceneDetect**, ffmpeg `scene` | ContentDetector threshold 27, min scene 15 frame. | `select='gt(scene,0.3)'` di 320 px untuk statistik shot (rata-rata, median, cut/menit) dan cek "statis". |
| **faster-whisper / WhisperX / stable-ts** | faster-whisper int8 praktis di CPU. stable-ts sudah diarsipkan (Mei 2026). | Backend faster-whisper (`word_timestamps`, VAD) + sidecar SRT/VTT. **Termasuk** timing per kata dari auto-caption YouTube; baris yang berulang dibuang. |
| **pycaps, captacity, gaya Hormozi/Submagic** | 1–3 kata per halaman, uppercase, outline 6–8 px + shadow, kata aktif kuning, pop 0.12 s dari skala 0.8. Batas baca Netflix 20 cps. | Gaya `bold_pop` (event per kata, highlight + `\t` pop), `karaoke` (`\kf`), `minimal`, `boxed`, `outline`. Grouping berhenti di tanda baca atau jeda > 0.35 s. Lint ≤ 20 cps. |
| **ClipsAI resizer, AutoFlip, SamurAIGPT** | Crop statis per segmen/pembicara (ClipsAI). Deadzone dan solver kinematik (AutoFlip). Haar + EMA (SamurAIGPT). | Crop statis per segmen (cut menyembunyikan lompatan framing), dengan posisi x dari Claude vision atau OpenCV opsional. Fallback ke center atau `fit_blur`. |
| **Resep ffmpeg yang kami uji di ffmpeg 6.1** | `scale…eval=frame` + crop untuk punch-in cepat. zoompan di upscale untuk zoom lambat. Shake dengan `crop` x/y sinus. `amix normalize=0`. sidechaincompress. loudnorm dua pass (`linear=true`, `aresample=48000`). | Semua dipakai di [`render.py`](../noze/agency/media/render.py). **Bug yang kami temukan sendiri:** `amix` memotong ekor suara ketika input SFX/musik lebih pendek, bahkan dengan `duration=first`. Solusinya: semua input di-`apad` sampai durasi penuh. Dua tahap render (segmen di-cache, lalu dirakit) mencegah OOM akibat `split`+`concat`. |
| **Safe zone platform** (template iklan TikTok, Reels, Shorts) | TikTok: atas 240, bawah 660, kolom tombol kanan ±180 px. Reels: 14% / 35%. Shorts: 288 / 672 / kanan 192. | [`standards.py`](../noze/agency/standards.py), dipakai untuk posisi caption/teks dan disebut di prompt. |

## 5. Kerja, izin, dan publikasi

| Sumber | Fakta | Dampak ke desain |
|---|---|---|
| Docs Whop Content Rewards & ToS | CPM per 1k views, budget dikunci, minimal payout, maks per video. ToS melarang scraping atau akses otomatis. Belum ada API untuk campaign CPM. | Domain Whop, contentrewards.com, dan Vyro **tidak pernah di-fetch**. Intake berupa syarat yang ditempel user. Bounties API resmi (beta) dipakai kalau ada `WHOP_API_KEY`. |
| Syarat Content Rewards (§7, §12, §17) | Disclosure di awal video. Lisensi footage terbatas. Brand memiliki hasil edit. Ada pengecekan bot dan akun terhubung. | Disclosure overlay di 3 s pertama dan di caption (dicek QC). Ringkasan syarat disimpan sebagai bukti izin campaign. |
| Reddit Responsible Builder Policy | Akses baru butuh persetujuan. Permintaan ditutup 31 Okt 2026, API publik ditutup Maret 2027. | Sumber Reddit hanya untuk kredensial yang sudah disetujui. Didokumentasikan sebagai sumber yang akan berakhir. |
| YouTube Data API (rev. Jun 2026) | `search.list` dan `videos.insert` punya bucket kuota sendiri. Upload pakai *resumable*. Refresh token kedaluwarsa 7 hari kalau consent screen masih "Testing". | Upload resumable + streaming file. Privasi default `private`. Catatan soal status verifikasi project. |
| TikTok Content Posting API | Client yang belum diaudit hanya bisa private. Audit menolak "tool internal untuk akun tim". | Hanya upload ke **inbox** (draft) akunmu sendiri. Tidak ada direct-post. |
| Instagram Graph API | Butuh akun profesional dan `video_url` publik. Akun klien butuh Advanced Access. | Belum diotomasi. Folder delivery + rclone/webhook untuk posting manual. |
