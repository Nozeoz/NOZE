# Storage: di mana bank-nya disimpan

## Strategi: bertingkat, bukan simpan semua

| Lapisan | Isi | Ukuran (terukur) | Kenapa |
|---|---|---|---|
| **Indeks** (`noze.db`) | metadata, tag, lisensi, palet, vektor CLIP, board, riwayat | ±4 KB per aset | inilah "otak" bank — cari & related tetap jalan walau offline |
| **Thumbnail** (`thumbs/`) | WebP 360 px | ±14 KB per aset | grid tampil instan, dipakai buat vektor visual |
| **File asli** (`blobs/` atau bucket) | hanya yang kamu **Save/Download** | tergantung (HDRI 2K ±6 MB, foto 1–5 MB, video 1080p 10–60 MB, Lottie ±50 KB, SFX ±100 KB, font ±0,1–1 MB) | yang penting buat kamu aman walau sumber hilang |

Dari tes nyata: 1.737 aset dari 15 sumber = 23,6 MB thumbnail + 7,3 MB database. Jadi:

| Isi bank | Indeks + thumbnail |
|---|---|
| 10 ribu aset | ±180 MB |
| 100 ribu aset | ±1,8 GB |
| 1 juta aset | ±18 GB |

Yang makan tempat hanya file asli yang kamu simpan — dan itu juga yang paling layak dibayar. File identik cuma disimpan sekali (nama file = hash SHA-256 isinya).

## Opsi tempat simpan

Harga perkiraan — cek halaman harga resmi sebelum memutuskan.

| Opsi | Biaya kira-kira | Plus | Minus | Cocok buat |
|---|---|---|---|---|
| **Disk laptop/PC** (default) | gratis | paling cepat, offline | hilang kalau disk rusak; nggak bisa diakses dari HP | mulai |
| **HDD/SSD eksternal atau NAS** | sekali beli | murah per TB, privat | perlu backup sendiri | bank besar di rumah/studio |
| **Cloudflare R2** | 10 GB gratis, lalu ±US$0,015/GB/bulan, **tanpa biaya egress** | murah, cepat, S3-compatible | perlu kartu untuk aktivasi | rekomendasi utama untuk cloud |
| **Backblaze B2** | ±US$6–7/TB/bulan, 10 GB pertama gratis | sangat murah per TB | egress gratis hanya sampai batas tertentu | arsip besar |
| **Wasabi** | ±US$7/TB/bulan (minimum 1 TB) | tanpa egress | ada minimum tagihan & masa simpan | bank multi-TB |
| **Hetzner Storage Box** | ±€3–4/bulan untuk 1 TB | murah, bisa SFTP/WebDAV/Samba/rclone | bukan S3 (pakai via rclone/mount) | backup harian |
| **Google Drive / OneDrive / Dropbox** | gratis 15 GB (Drive), lalu paket bulanan | mungkin sudah punya | lambat untuk ribuan file kecil; via rclone | backup `blobs/` saja |
| **MinIO di NAS/PC rumah** | gratis (hardware sendiri) | S3-compatible, data di tanganmu | harus dirawat sendiri | yang suka self-host |

Hindari layanan "unlimited gratis" yang nggak jelas (penyimpanan via bot chat, cloud gratis berukuran TB tanpa model bisnis jelas): rawan hilang, privasi buruk, dan sering melanggar ToS.

## Setup

### 1. Lokal / drive eksternal

```bash
NOZE_DATA_DIR=/Volumes/AssetDrive/noze-bank noze serve
```

Seluruh bank (database, thumbnail, file, model CLIP) pindah ke drive itu. Bisa dicolok ke komputer lain dan langsung dipakai.

### 2. Cloudflare R2 (atau S3-compatible lain)

```bash
pip install -e ".[s3]"
```

`.env`:

```ini
NOZE_STORAGE=s3
NOZE_S3_ENDPOINT=https://<ACCOUNT_ID>.r2.cloudflarestorage.com
NOZE_S3_BUCKET=noze-bank
NOZE_S3_ACCESS_KEY=...
NOZE_S3_SECRET_KEY=...
NOZE_S3_REGION=auto
```

Backblaze B2: endpoint `https://s3.<region>.backblazeb2.com`. MinIO: `http://nas.local:9000`. File asli masuk bucket; indeks & thumbnail tetap lokal (cepat). Download dari UI diarahkan ke link sementara (presigned) dari bucket.

### 3. Backup / sinkron ke mana pun dengan rclone

```bash
rclone config                                   # tambahkan remote, mis. "gdrive" atau "r2"
rclone sync ./noze-data/blobs  gdrive:noze/blobs  --transfers 8
rclone copy ./noze-data/noze.db gdrive:noze/      # indeks: salin saat NOZE tidak sedang menulis
```

Jadwalkan pakai cron/Task Scheduler. Folder `thumbs/` bisa dibangun ulang (`noze enrich`), jadi opsional dibackup.

## Mau diakses dari mana-mana?

- **Laptop + Tailscale**: jalankan `noze serve --host 0.0.0.0` dengan `NOZE_PASSWORD`, buka dari HP lewat alamat Tailscale. Paling gampang & aman.
- **Server kecil di rumah** (PC lama, NAS, mini PC): `docker compose up -d`, bank di disk besar.
- **VPS/cloud**: Docker image yang sama, volume ke disk server, file asli ke R2. Jangan lupa `NOZE_PASSWORD` dan HTTPS (mis. di belakang Caddy/Cloudflare Tunnel). Beberapa penyedia punya tier gratis (VM ARM + block storage) selama masih ditawarkan — cek syaratnya.

## Hemat ruang

- `NOZE_VIDEO_MAX_WIDTH=1920` (default) supaya stock video yang disimpan maksimal 1080p.
- `NOZE_AUTO_DOWNLOAD_ON_SAVE=0` kalau mau board cuma berisi link + thumbnail (download manual per item).
- `noze stats` buat lihat yang makan tempat; *Not my vibe* menyembunyikan item dari hasil.
