# Referensi clipper GTA VI / streamer: kenapa views-nya tinggi (24 Nov 2026)

Pertanyaan Dalvin: lihat dulu klip clipper yang views-nya tinggi, kenapa bisa tinggi, sebelum bikin.
Tiga sumber, semuanya diukur (bukan kesan):

| Sumber | n | Format | Ukuran |
|---|---|---|---|
| YouTube Shorts vertikal 9:16 (Nogla Clips 190k subs + 1 kanal lain) | 19 | 1080x1920, 17–81 dtk | views 676 → 696.022 |
| TikTok "kai cenat gta 6" (dilihat di Chrome, frame 0/tengah/akhir) | 4 diperiksa dari 12 | 720x1280, 23–30 dtk | like 3 → 53.500 |
| YouTube landscape ≤90 dtk (kontrol format) | 12 | 1920x1080 | views 32k → 813k |

File mentah: scratchpad sesi 23–24 Nov (`shorts/REPORT.md`, `all.json`, `refs/`). Referensi vertikal teratas disalin
ke `noze-data/agency/assets/references/gta6/` (dipakai Scout studio untuk campaign yang namanya memuat "gta6").

## Temuan (urut kekuatan bukti)

1. **Edit-nya seragam, views-nya beda 1000×.** 18/18 Shorts Nogla memakai template sama persis (facecam 31% atas,
   gameplay 69% bawah, judul kotak putih 0–3 dtk, hampir tanpa cut). Di TikTok, klip 3 like dan 53.500 like juga
   memakai format yang SAMA (facecam atas, judul kotak putih, tanpa caption). Di niche ini editing sudah komoditas:
   bukan itu yang membedakan.
2. **Momennya yang menentukan: langka + emosi kuat + jelas tanpa konteks.** TikTok teratas = Kai *menangis* di
   akhir game (53,5k like, 5,2k save, 3,3k share) dan menangis melihat kematian dua tokoh utama (17k like). Yang rendah
   = momen generik ("nggak mau keluar klub" 3 like, "naksir Mandy" 51 like). Di satu kanal yang sama: kereta 571k vs
   aligator 32k (18×), radio China 505k vs road rage 51k (10×). Klip landscape nomor 1 (813k) malah tanpa streamer.
3. **Frame 0 = puncak emosi / visual paling aneh.** Klip teratas mulai dari wajah menangis / iguana close-up / aksi
   kapal; yang rendah mulai dari jalan kosong, adegan gelap, wajah datar.
4. **Judul = [subjek dikenal] + [klaim ber-stakes yang spesifik].** "stream almost ended immediately" 696k,
   "PASTA IS NEVER BEATING THE ALLEGATIONS" 233k vs "Their reactions" 676, "THEY FOUND VANOSS IN GTA VI" 5,8k.
   ≤2 baris, ≤45 karakter, boleh 1 emoji. (Inferensi dari judul, belum A/B.)
5. **Pendek menang.** Shorts: median views/hari ≤30 dtk = 11,1k vs >30 dtk = 5,6k; Spearman durasi~views/hari −0,59.
   Satu hari upload yang sama: 21s 26,8k → 35s 19k → 48s 12,8k → 60s 2,7k → 81s 2,0k.
6. **Loop.** Klip TikTok teratas mulai DAN berakhir di wajah menangis yang sama — penonton tersambung balik ke awal.
7. **Caption kata-per-layar bukan pembeda.** Klip #1 dan #2 Shorts tanpa caption; hanya 2/18 yang pakai. (Tetap
   berguna untuk penonton tanpa suara; bukan penentu views.)
8. **Spoiler = pedang bermata dua.** Dua TikTok teratas adalah reaksi ke ENDING/kematian tokoh (spoiler cerita).
   Paling ramai, tapi kebijakan Rockstar men-takedown spoiler besar & kompilasi cutscene, dan banyak campaign
   melarang spoiler → klip yang di-takedown tidak dibayar. Keputusan Dalvin.

## Artinya buat studio (yang diterapkan)

- **Pilih momen dulu, efek kemudian.** Bobot skor ke kelangkaan + intensitas emosi (nangis, ngamuk, kaget besar,
  "game ini ternyata bisa begini") di atas "lucu biasa".
- **Frame 0 = momen puncak** (wajah streamer di puncak emosi / visual paling aneh); cold open dari puncak itu.
- **Ending balik ke beat frame 0** (loop) bila momennya cocok.
- **Durasi sasaran 20–30 dtk** untuk klip reaksi linear; arc lintas periode boleh sampai ±45 dtk kalau payoff jelas.
- **Judul**: subjek dikenal + klaim ber-stakes, ≤45 karakter, ≤2 baris.
- **Cut sedikit di gameplay**: jangan memotong aksi yang sedang jalan; potong hanya jeda panjang.
- **Tipografi pro & efek cerita tetap dipakai** — bukan pendorong views utama menurut data ini, tapi pembeda dari
  ribuan klip yang formatnya sama; tidak boleh menutupi momen.

## Batas data

- Shorts didominasi satu kanal; tidak ditemukan Shorts GTA6 vertikal ≥18 Nov dari xQc/IShowSpeed/Kai Cenat lewat yt-dlp.
- TikTok: view count tidak tampil di pencarian → pakai like; yt-dlp TikTok sedang rusak (unduh gagal) → TikTok dinilai
  dari screenshot, bukan metrik studio. Riset sosmed otomatis (OpenCLI) gagal karena extension OpenCLI juga terpasang
  di Chrome/Edge biasa Dalvin.
- Tidak ada data retensi/CTR; semua "hook" = inferensi visual. Views 23–24 Nov belum matang.
