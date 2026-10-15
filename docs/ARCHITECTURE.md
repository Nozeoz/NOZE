# Cara kerja NOZE (dan cara kerja "related"-nya Pinterest)

## 1. Pinterest itu nyambung-nyambunginnya gimana?

Yang kamu lihat sebagai "Pinterest kok ngerti banget vibe gue" sebenarnya gabungan beberapa sinyal. Dari paper & tulisan engineering Pinterest sendiri:

| Sinyal | Isinya | Contoh sistem di Pinterest |
|---|---|---|
| **Graf pin–board** | Miliaran pin yang di-save orang ke board. Dua pin yang sering muncul di board yang sama dianggap "nyambung" — ini kurasi manusia, sinyal paling kuat. | *Pixie* (random walk di graf pin–board, real-time, 2018) |
| **Embedding visual** | Model vision mengubah gambar jadi vektor; gambar yang mirip tampilannya → vektornya dekat. Dipakai buat visual search ("Lens") dan "more like this". | *Visual Discovery at Pinterest* (2017), *unified visual embeddings* |
| **Gabungan graf + konten** | Neural network yang belajar dari graf **dan** fitur gambar/teks sekaligus → satu embedding per pin. | *PinSage* (Graph Convolutional Networks, KDD 2018) |
| **Teks/anotasi** | Judul, deskripsi, nama board, teks di gambar → anotasi/keyword per pin; juga "guided search" (chip saran kata). | sistem annotation & query understanding |
| **Sinyal personal** | Apa yang kamu save, klik, close-up, sembunyikan → embedding selera kamu (bisa beberapa, satu per minat). Ini bagian "cookie"/akun. | *PinnerSage* (KDD 2020), model ranking homefeed |
| **Caching & ANN** | Kandidat & embedding dihitung duluan lalu di-cache; pencarian tetangga terdekat pakai indeks ANN (mis. HNSW) supaya cepat. | serving infra |

Satu hal penting: Pinterest **tidak** "nge-crawl seluruh internet" buat isinya — kontennya datang dari orang-orang yang menekan **Save** (tombol/ekstensi browser) dan dari publisher. Itulah kenapa NOZE punya bookmarklet "Save to NOZE".

## 2. Padanannya di NOZE

| Pinterest | NOZE |
|---|---|
| graf pin–board | **board milikmu** (co-occurrence: item yang kamu taruh di board yang sama) + **channel Are.na** (board kurasi desainer, publik) + endpoint *related* dari Openverse → tabel `edges` |
| embedding visual | **CLIP / SigLIP2** (ONNX via `fastembed`, tanpa PyTorch): teks dan gambar satu ruang vektor, jadi kalimat bisa nyari gambar. Tanpa CLIP: vektor ringan dari hash kata + histogram warna |
| anotasi teks | SQLite **FTS5/BM25** atas judul, tag, deskripsi, kreator + **terjemahan Indonesia→Inggris** + kamus vibe (`noze/lexicon.py`) |
| guided search | chip ✦ vibe (mis. *cyberpunk* → neon city, hologram, rainy street neon…) |
| feed Pinterest itu sendiri | bookmarklet: pin yang kamu simpan dari satu halaman Pinterest (mis. *More like this* sebuah pin) disambung jadi edge `context` — kurasi Pinterest ikut masuk ke grafmu |
| sinyal personal | tabel `interactions` (open, save, download, copy credit, hide) → **vektor selera** dengan peluruhan 30 hari + tag favorit |
| caching | cache query per (query, sumber, halaman) 7 hari, cache thumbnail lokal, dan **semua yang pernah ditemukan tetap tersimpan** |
| diversifikasi feed | **MMR** + penalti per sumber/jenis supaya satu gaya/sumber nggak menguasai grid |

## 3. Alur data

```
                ┌─────────────── query understanding (lexicon.py) ───────────────┐
"hujan malam    │ id→en: "rain night"  · intent: kinds/lisensi/warna · vibes       │
 neon video"  ─►└──────────────────────────────┬───────────────────────────────────┘
                                               ▼
                   harvest.py: fan-out paralel ke sumber yang cocok jenisnya
                   (rate-limit per sumber, budget per jam, cooldown kalau 429,
                    cache 7 hari; sumber lambat lanjut di background)
                                               ▼
                   sources/*.py → Asset (1 skema) → licenses.py → kelas pemakaian
                   free / credit / noncommercial / reference / check / own
                                               ▼
                   db.py: SQLite (WAL) + FTS5 · query_hits (urutan versi sumber) · edges
                                               ▼
       worker.py ─► enrich.py: thumbnail WebP 360px (±14 KB), palet 5 warna,
                   dHash (deteksi duplikat), vektor CLIP → indeks vektor di memori
                                               ▼
                   search.py (Ranker)
                   kandidat:  hits sumber  +  BM25  +  vektor vibe
                   gabung:    Reciprocal Rank Fusion
                   boost:     selera kamu · cocok warna · popularitas · jenis visual (feed)
                   rapikan:   MMR (beragam) + buang duplikat visual
```

### Ranking pencarian

Untuk query *q*, tiap daftar kandidat diberi bobot lalu digabung dengan RRF:

```
skor(a) = Σ  w_daftar / (60 + peringkat_a_di_daftar)
          daftar ∈ { urutan hasil sumber (1.0), BM25 (1.0), vektor (1.3 CLIP / 0.5 ringan) }
```

lalu **disaring relevansinya**: tiap kandidat diberi skor 0–1 dari (a) berapa banyak kata query yang ada di judul/tag (deskripsi dihitung lebih lemah; cocok separuh kata dihukum), (b) seberapa jauh di atas rata-rata kemiripan CLIP-nya terhadap query (z-score), (c) sedikit bonus kalau mesin pencari sumbernya sendiri memilihnya (sumber berbasis tag/vibe seperti Wallhaven, Fontsource, Poly Haven dipercaya penuh). Yang di bawah 0,5 dibuang — ini yang memotong "ekor" hasil nyasar. Skor akhir = 0,45 × RRF + 0,55 × relevansi, ditambah: `+0.6 × kecocokan warna` (kalau pilih warna / ada kata warna), `+0.12 × kemiripan dengan vektor selera`, `+0.04 × log(popularitas)`. Terakhir **MMR**: item yang terlalu mirip dengan yang sudah ditampilkan, atau dari sumber/jenis yang sudah banyak, turun sedikit.

### "More like this"

Kandidat dari: tetangga vektor (visual), item yang satu board dengannya, tetangga di graf (`edges`: channel Are.na yang sama, *related* Openverse), kecocokan tag/judul, kreator yang sama. Plus boost kemiripan palet warna. Jenis yang "nyambung" dibatasi (foto bisa dapat video/GIF/tekstur, tapi bukan SFX).

### Feed "For you"

Tetangga dari vektor selera + tetangga dari 8 simpanan terakhir + tag favorit + yang baru masuk + sedikit acak untuk eksplorasi. Yang sudah kamu simpan diturunkan, jenis visual didahulukan, lalu MMR.

## 4. Kenapa "bank" dan nggak perlu crawl ulang

- Setiap hasil dari sumber disimpan (metadata + thumbnail kecil) begitu muncul. Pencarian yang sama/mirip berikutnya dijawab dari bank — sumber hanya ditanya lagi setelah cache kedaluwarsa atau kalau kamu scroll lebih dalam.
- File asli hanya diunduh untuk yang kamu **Save/Download**, disimpan berdasarkan hash konten (file sama = sekali simpan).
- **Interests** di-crawl di background (default tiap 24 jam, 1 halaman lebih dalam tiap putaran) — bank tumbuh sendiri sesuai minatmu.
- Setelah kamu menyimpan sesuatu, worker menjalankan job `expand`: ambil *related* dari sumbernya + cari lagi pakai tag-tagnya.

## 5. Komponen kode

| File | Isi |
|---|---|
| `noze/sources/` | satu konektor per sumber; semua mengembalikan `Asset` (lihat [SOURCES.md](SOURCES.md)) |
| `noze/harvest.py` | fan-out, cache, budget/cooldown, related dari sumber, download ke bank (multi-file → zip) |
| `noze/enrich.py` | thumbnail, palet, dHash, vektor (termasuk dari file lokal: gambar, frame video via ffmpeg, spesimen font) |
| `noze/embeddings.py` | `HashEmbedder`, `FastEmbedder` (CLIP/SigLIP2), `VectorIndex` (numpy, z-score per modalitas) |
| `noze/search.py`, `noze/ranking.py` | ranking hybrid, related, feed, RRF, MMR |
| `noze/db.py` | skema SQLite + FTS5, board, interaksi, cache, graf, job |
| `noze/storage.py` | penyimpanan content-addressed: lokal atau S3-compatible |
| `noze/importers/` | folder lokal, Pinterest (API resmi), web/bookmarklet/upload |
| `noze/api.py`, `noze/web/` | API FastAPI + UI vanilla JS (tanpa build step) |
| `noze/worker.py` | job (download, harvest, interest, expand, generate) + enrichment |

## 6. Keamanan

- Default hanya listen di `127.0.0.1`. Kalau dibuka ke jaringan, set `NOZE_PASSWORD` (HTTP Basic).
- Request tulis lintas-situs ditolak (cek `Origin`), jadi situs lain nggak bisa diam-diam nambah ke bank-mu.
- URL yang kamu simpan dari web dicek dulu (bukan alamat privat/lokal) di setiap redirect — mencegah SSRF.
- Semua URL yang tersimpan hanya boleh `http(s)` (nggak ada `javascript:`), dan UI tidak pernah memasukkan teks dari sumber sebagai HTML.
