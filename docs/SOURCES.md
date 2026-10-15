# Sumber aset

Semua sumber pakai **API resmi** masing-masing. Cek status & key yang kurang: `noze sources` atau halaman **Bank** di web — key bisa langsung ditempel di sana (disimpan ke `NOZE_DATA_DIR/.env`, langsung aktif tanpa restart).

Label pemakaian: **Free** = komersial OK tanpa kredit · **Credit** = komersial OK, wajib kredit · **Non-comm.** · **Ref only** = cuma referensi · **Check** = cek dulu di halaman sumber · **Mine** = punyamu.

## Tanpa API key (langsung jalan)

| Sumber | Bagus buat | Jenis | Lisensi umumnya | Catatan |
|---|---|---|---|---|
| [Wallhaven](https://wallhaven.cc) | wallpaper & art aesthetic (anime, cyberpunk, minimal, nature…) — paling mirip feed Pinterest di antara yang tanpa key | image | **Ref only** | pencarian berbasis tag; hanya SFW |
| [Openverse](https://openverse.org) | foto/ilustrasi/audio apa aja (Flickr, Wikimedia, museum, Jamendo…) | image, audio | CC0 · CC BY/SA · sebagian NC → dilabel per item | tanpa key dibatasi ketat; daftar OAuth gratis biar longgar (`OPENVERSE_CLIENT_ID/SECRET`) |
| [Wikimedia Commons](https://commons.wikimedia.org) | foto, SVG, video, suara, file 3D | image, gif, video, audio, 3d | CC BY-SA/BY/CC0/PD | pakai HTTP/2 + User-Agent sopan; `WIKIMEDIA_TOKEN` opsional |
| [Poly Haven](https://polyhaven.com) | HDRI studio/outdoor, tekstur PBR, model 3D | hdri, texture, 3d | **CC0** | NOZE menampilkan "Powered by Poly Haven" sesuai ToS API mereka; download HDRI 2K / set tekstur 2K (zip) / glTF |
| [ambientCG](https://ambientcg.com) | material PBR (kayu, logam, beton, kain…) | texture, hdri, 3d | **CC0** | download zip 2K-JPG |
| [NASA Images](https://images.nasa.gov) | luar angkasa, bumi, roket — foto **dan footage** | image, video, audio | umumnya public domain (jangan pakai logo NASA/kesan endorsement) | |
| [The Met](https://www.metmuseum.org/art/collection) | lukisan, poster, tekstil, ornamen | image | **CC0** (hanya karya public domain yang diambil) | pakai endpoint `v1.1/search` (yang lama dipensiunkan 1 Okt 2026) |
| [Art Institute of Chicago](https://www.artic.edu/collection) | seni & desain, dengan warna dominan | image | **CC0** | gambar IIIF butuh header `AIC-User-Agent` (sudah otomatis) |
| [Cleveland Museum of Art](https://www.clevelandart.org) | karya CC0 resolusi tinggi | image | **CC0** | |
| [Smithsonian](https://www.si.edu/openaccess) | 4,5 jt+ gambar CC0 dari 21 museum | image | **CC0** | `DEMO_KEY` cepat habis → ambil key gratis di api.data.gov |
| [Europeana](https://www.europeana.eu) | arsip & museum Eropa: poster, foto lawas, film, suara | image, video, audio, 3d | hanya yang lisensinya terbuka | `api2demo` dipakai default; key sendiri gratis |
| [Internet Archive](https://archive.org) | **footage public domain** (Prelinger!), kartun lawas, rekaman suara | video, image, audio | PD/CC kalau ada `licenseurl`, selain itu **Check** | link video yang bisa diputar diambil saat kamu buka detail |
| [Iconify](https://icon-sets.iconify.design) | 200 rb+ ikon SVG dari 150+ set | icon | MIT/Apache/CC BY… per set | |
| [Fontsource](https://fontsource.org) | semua Google Fonts + lainnya; dicari pakai nama **atau vibe** (retro→display, code→mono…) | font | OFL/Apache (Google Fonts) | download = semua weight dalam satu zip |
| [GitHub](https://github.com) | script AE/Blender, shader, pack Lottie, design system, awesome-list | code | sesuai lisensi repo; repo tanpa lisensi = **Ref only** | `GITHUB_TOKEN` (tanpa scope) menaikkan limit |
| [Are.na](https://www.are.na) | moodboard kurasi desainer — paling mirip Pinterest | image, gif, video, link | **Ref only** | dicari lewat *channel* (board) yang cocok lalu isinya; channel = graf "related" |
| [LottieFiles](https://lottiefiles.com/free-animations) | animasi Lottie gratis (loader, ikon, karakter) | motion | Lottie Simple License (**Free**) | hover kartu = preview animasi |
| [Civitai](https://civitai.com/images) | gambar & klip hasil AI yang dipublikasi + prompt-nya | image, video | **Check** (AI, ikut aturan platform) | API-nya tidak punya pencarian teks: NOZE menyaring feed SFW berdasarkan prompt |

## Dengan API key gratis

| Sumber | Bagus buat | Daftar key | Variabel | Catatan |
|---|---|---|---|---|
| [Pexels](https://www.pexels.com) | foto & **stock footage 4K** (B-roll) | [pexels.com/api](https://www.pexels.com/api/new/) | `PEXELS_API_KEY` | Free; video yang disimpan dibatasi `NOZE_VIDEO_MAX_WIDTH` |
| [Pixabay](https://pixabay.com) | foto, vektor, **motion background** | [pixabay.com/api/docs](https://pixabay.com/api/docs/) | `PIXABAY_API_KEY` | Free; Pixabay minta gambar disimpan (bukan hotlink permanen) — NOZE meng-cache |
| [Unsplash](https://unsplash.com) | foto berkualitas | [unsplash.com/oauth/applications](https://unsplash.com/oauth/applications) | `UNSPLASH_ACCESS_KEY` | Free; thumbnail ditampilkan langsung dari Unsplash & download dilaporkan ke mereka (aturan API) |
| [Tumblr](https://www.tumblr.com) | budaya aesthetic/moodboard — banyak konten Pinterest asalnya dari sini | [tumblr.com/oauth/apps](https://www.tumblr.com/oauth/apps) | `TUMBLR_API_KEY` | **Ref only**; dicari per tag (mis. *vaporwave*, *y2k aesthetic*) |
| [Flickr](https://www.flickr.com) | miliaran foto orang biasa | [flickr.com/services/apps](https://www.flickr.com/services/apps/create/apply/) | `FLICKR_API_KEY` | lisensi per foto: CC/PD bisa dipakai, sisanya **Ref only** |
| [DeviantArt](https://www.deviantart.com) | ilustrasi, concept art, photomanip | [deviantart.com/developers](https://www.deviantart.com/developers/apps) | `DEVIANTART_CLIENT_ID` + `_SECRET` | **Ref only**; punya "more like this" sendiri (dipakai buat related) |
| [Vimeo](https://vimeo.com) | **reel motion design**, title sequence | [developer.vimeo.com/apps](https://developer.vimeo.com/apps) | `VIMEO_ACCESS_TOKEN` | diputar lewat player Vimeo (embed), file tidak diunduh |
| [YouTube](https://www.youtube.com) | referensi & breakdown motion | [Google Cloud Console](https://console.cloud.google.com/apis/library/youtube.googleapis.com) | `YOUTUBE_API_KEY` | embed saja; kuota ±100 pencarian/hari |
| [Freesound](https://freesound.org) | **SFX**: whoosh, impact, ambience | [freesound.org/apiv2/apply](https://freesound.org/apiv2/apply/) | `FREESOUND_API_KEY` | CC0/BY/NC per suara; yang disimpan = preview MP3 HQ (file asli butuh login OAuth) |
| [GIPHY](https://giphy.com) | GIF & stiker transparan | [developers.giphy.com](https://developers.giphy.com/dashboard/) | `GIPHY_API_KEY` | **Ref only** |
| [Reddit](https://www.reddit.com) | r/motiondesign, r/AfterEffects, r/Cinema4D, r/generative… | [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) (tipe *script*) | `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` | **Ref only**; subreddit bisa diganti via `NOZE_REDDIT_SUBS` |

## Pinterest

Pinterest **tidak punya API pencarian publik** (API resminya cuma bisa baca pin & board milik akun kamu sendiri), dan ToS-nya melarang scraping — jadi NOZE nggak nge-crawl hasil pencarian Pinterest. Yang bisa, dan jalan sendiri:

1. **Connect Pinterest (otomatis)** — halaman **Bank** → panel *Pinterest → your bank*:
   1. buka [developers.pinterest.com/apps](https://developers.pinterest.com/apps/) → **Connect app** (gratis);
   2. di setting app-nya tambahkan *Redirect URI* yang ditampilkan NOZE (mis. `http://localhost:8787/api/pinterest/callback` — harus persis sama, termasuk `localhost` vs `127.0.0.1`);
   3. tempel **App ID** + **App secret** di NOZE → **Save** → **Connect Pinterest** → login & *Allow*.

   Setelah itu semuanya otomatis: worker nge-sync tiap 6 jam (`NOZE_PINTEREST_SYNC_HOURS`), cuma ngambil pin baru, token diperpanjang sendiri (akses 30 hari, refresh token 60 hari yang terus diperbarui). Tiap board jadi board NOZE `Pinterest · <nama>`, dan **nama board jadi interest** — jadi NOZE juga nyari vibe yang sama di 29 sumber lain. Izin yang diminta cuma baca: `boards:read`, `pins:read`, `user_accounts:read`.
   Jalan pintas: tempel *access token* langsung (`PINTEREST_ACCESS_TOKEN`) — tapi itu mati setelah 30 hari.
2. **Bookmarklet "Save to NOZE" mode Pinterest** (halaman Bank → seret tombolnya ke bookmarks bar) — buat pin orang lain yang belum kamu save di Pinterest.
   Buka Pinterest seperti biasa — cari, atau buka satu pin dan scroll ke *More like this* (itu mesin related-nya Pinterest sendiri). Klik bookmarklet → **Select all** → semua pin yang sedang kamu lihat masuk bank sekaligus:
   - gambar diambil versi **736px** (bukan thumbnail 236px), judul dari caption pin, link ke pin aslinya untuk kredit;
   - urutan feed Pinterest dipertahankan;
   - pin yang disimpan dari halaman yang sama otomatis **saling terhubung**, jadi "More like this" di NOZE ikut mewarisi kurasi Pinterest;
   - label sumber **Pinterest**, pemakaian **Ref only** (hak tetap di kreator aslinya).
3. **Sumber yang rasanya mirip Pinterest** (kurasi visual dari orang-orang): Are.na & Wallhaven (tanpa key), Tumblr, Flickr, DeviantArt (key gratis).

Bookmarklet yang sama berlaku untuk Behance, Dribbble, X, Cosmos, Savee, galeri AI (Dreamina/Higgsfield/Kling), dll.

## Seedance & AI

- **Lihat hasil orang**: Civitai (otomatis), atau simpan dari galeri Dreamina/Higgsfield/Kling pakai bookmarklet.
- **Bikin sendiri**: isi `REPLICATE_API_TOKEN` → panel *Generate* di halaman Bank. Default video `bytedance/seedance-1-lite`, gambar `black-forest-labs/flux-schnell` (ganti via `NOZE_GEN_VIDEO_MODEL` / `NOZE_GEN_IMAGE_MODEL`). Berbayar per generasi di Replicate; hasilnya masuk bank sebagai **Mine** — cek ketentuan model untuk pemakaian komersial.

## Nambah sumber baru

Satu file di `noze/sources/`, satu class:

```python
from ..licenses import normalize_license
from ..models import Kind
from .base import SearchResult, Source


class MySource(Source):
    name = "mysource"                 # id unik (jadi prefix id aset)
    label = "My Source"
    homepage = "https://example.com"
    description = "Apa yang dikasih sumber ini."
    kinds = (Kind.IMAGE, Kind.VIDEO)  # jenis yang bisa dikembalikan
    key_names = ()                    # mis. ("MYSOURCE_API_KEY",) kalau wajib key (daftarkan juga di config.KEY_NAMES)
    min_interval = 0.5                # jeda antar request (detik)

    async def search(self, query, kinds, page, limit, cursor=None) -> SearchResult:
        data = await self.get("https://api.example.com/search", params={"q": query, "page": page})
        assets = [
            self.make(
                source_id=item["id"], kind=Kind.IMAGE, title=item["title"], tags=item.get("tags", []),
                author=item.get("author", ""), page_url=item["url"], thumb_url=item["thumb"],
                preview_url=item["large"], download_url=item["original"],
                width=item.get("w"), height=item.get("h"),
                license=normalize_license(item.get("license"), item.get("license_url")),
            )
            for item in data["results"]
        ]
        return SearchResult(assets, exhausted=not data.get("next"))
```

Lalu tambahkan class-nya ke `SOURCE_CLASSES` di `noze/sources/__init__.py`, dan bikin tes dengan contoh respons asli di `tests/fixtures/responses.py` + `tests/test_sources.py`. Hook opsional: `related()` (graf "mirip ini" dari sumber), `hydrate()` (lengkapi URL saat detail dibuka), `resolve_download()` (file yang diunduh; banyak file → otomatis di-zip), `fetch_headers()`, `on_download()`.
