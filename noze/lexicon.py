"""Query understanding: Indonesian → English, "vibe" expansions, and intent words.

Most source APIs (and CLIP) only understand English, so "hujan malam kota
neon video gratis" becomes text="rain night city neon", kinds={video},
usage="usable". Vibes power the "related vibes" chips in the UI, the same
idea as Pinterest's guided search.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import Kind

STOPWORDS = {
    # Indonesian (incl. chat slang)
    "yang", "yg", "dan", "dgn", "dengan", "di", "ke", "dari", "untuk", "utk", "buat", "atau", "ini", "itu",
    "ada", "aja", "saja", "dong", "sih", "deh", "nih", "tuh", "kok", "pake", "pakai", "cari", "carikan",
    "mau", "pengen", "pingin", "ingin", "butuh", "perlu", "kayak", "kaya", "kyk", "seperti", "mirip", "gitu",
    "begitu", "banget", "bgt", "sangat", "agak", "lebih", "yg", "para", "sebuah", "suatu", "satu", "beberapa",
    "gw", "gue", "aku", "saya", "lu", "lo", "kamu", "bisa", "boleh", "juga", "jg", "lagi", "lg", "sama",
    "tolong", "referensi", "ref", "contoh", "semacam", "macam", "jenis", "ala", "style", "gaya", "vibe", "vibes",
    # English
    "the", "a", "an", "of", "for", "with", "and", "or", "in", "on", "at", "to", "some", "like", "similar",
    "stuff", "things", "thing", "please", "find", "search", "me", "my", "i", "want", "need", "reference",
    "references", "inspo", "inspiration", "kind",
}

# Multi-word phrases first (matched greedily, longest first).
ID_PHRASES = {
    "merah muda": "pink", "abu abu": "gray", "hitam putih": "black and white", "matahari terbenam": "sunset",
    "matahari terbit": "sunrise", "kembang api": "fireworks", "air terjun": "waterfall", "hujan deras": "heavy rain",
    "cahaya bocor": "light leak", "efek suara": "sound effect", "efek transisi": "transition effect",
    "tulisan tangan": "handwriting", "kota malam": "city night", "langit malam": "night sky",
    "jalan raya": "highway", "pantai tropis": "tropical beach", "luar angkasa": "outer space",
    "bulan purnama": "full moon", "gambar tangan": "hand drawn", "ulang tahun": "birthday", "daun gugur": "autumn leaves", "hutan hujan": "rainforest",
    "gedung tinggi": "skyscraper", "lampu jalan": "street light", "papan reklame": "billboard",
    "tekstur kertas": "paper texture", "tekstur kayu": "wood texture", "tekstur batu": "stone texture",
    "tekstur kain": "fabric texture", "gerak lambat": "slow motion", "selang waktu": "timelapse",
    "bokeh lampu": "light bokeh", "asap warna": "color smoke", "cat air": "watercolor", "cat minyak": "oil painting",
    "seni jalanan": "street art", "gaya retro": "retro", "anak muda": "youth", "rumah adat": "traditional house",
    "hari raya": "eid", "bulan ramadan": "ramadan", "kue lebaran": "eid cookies",
}

ID_EN = {
    # nature & places
    "hujan": "rain", "gerimis": "drizzle", "badai": "storm", "petir": "lightning", "kilat": "lightning",
    "salju": "snow", "es": "ice", "kabut": "fog", "awan": "clouds", "langit": "sky", "matahari": "sun",
    "bulan": "moon", "bintang": "stars", "galaksi": "galaxy", "planet": "planet", "angkasa": "space",
    "laut": "ocean", "lautan": "ocean", "samudra": "ocean", "pantai": "beach", "ombak": "waves", "gelombang": "wave",
    "sungai": "river", "danau": "lake", "gunung": "mountain", "pegunungan": "mountains", "bukit": "hill",
    "hutan": "forest", "pohon": "tree", "daun": "leaves", "bunga": "flower", "bunga2": "flowers", "rumput": "grass",
    "gurun": "desert", "pasir": "sand", "batu": "stone", "tanah": "soil", "api": "fire", "air": "water",
    "angin": "wind", "asap": "smoke", "debu": "dust", "embun": "dew", "pelangi": "rainbow", "senja": "sunset",
    "fajar": "dawn", "pagi": "morning", "siang": "daytime", "sore": "afternoon", "malam": "night",
    "gelap": "dark", "terang": "bright", "cahaya": "light", "lampu": "lamp", "sinar": "light rays",
    "bayangan": "shadow", "bayang": "shadow", "kota": "city", "desa": "village", "jalan": "street",
    "jalanan": "street", "gedung": "building", "bangunan": "building", "rumah": "house", "kamar": "bedroom",
    "ruangan": "room", "dapur": "kitchen", "kantor": "office", "sekolah": "school", "pasar": "market",
    "stasiun": "station", "jembatan": "bridge", "atap": "rooftop", "jendela": "window", "pintu": "door",
    "tembok": "wall", "dinding": "wall", "lantai": "floor", "taman": "garden", "sawah": "rice field",
    "kebun": "garden", "masjid": "mosque", "candi": "temple", "pura": "temple", "gereja": "church",
    # things
    "mobil": "car", "motor": "motorcycle", "sepeda": "bicycle", "kereta": "train", "pesawat": "airplane",
    "kapal": "ship", "perahu": "boat", "jam": "clock", "buku": "book", "kertas": "paper", "kayu": "wood",
    "besi": "metal", "logam": "metal", "kaca": "glass", "cermin": "mirror", "kain": "fabric", "kulit": "leather",
    "plastik": "plastic", "emas": "gold", "perak": "silver", "berlian": "diamond", "kristal": "crystal",
    "uang": "money", "koin": "coin", "hp": "phone", "ponsel": "phone", "laptop": "laptop", "kamera": "camera",
    "layar": "screen", "tv": "television", "mesin": "machine", "robot": "robot", "senjata": "weapon",
    "pedang": "sword", "mahkota": "crown", "topeng": "mask", "lilin": "candle", "lentera": "lantern",
    "balon": "balloon", "hadiah": "gift", "kado": "gift", "kue": "cake", "makanan": "food", "minuman": "drink",
    "kopi": "coffee", "teh": "tea", "buah": "fruit", "sayur": "vegetables", "nasi": "rice", "roti": "bread",
    # living things & people
    "orang": "people", "manusia": "human", "wajah": "face", "muka": "face", "mata": "eyes", "tangan": "hands",
    "kaki": "feet", "rambut": "hair", "bibir": "lips", "tubuh": "body", "badan": "body", "wanita": "woman",
    "perempuan": "woman", "cewek": "girl", "cewe": "girl", "pria": "man", "laki": "man", "cowok": "boy",
    "cowo": "boy", "anak": "child", "bayi": "baby", "keluarga": "family", "teman": "friends", "pasangan": "couple",
    "penari": "dancer", "tarian": "dance", "menari": "dancing", "berlari": "running", "lari": "running",
    "kerumunan": "crowd", "penonton": "audience", "kucing": "cat", "anjing": "dog",
    "burung": "bird", "ikan": "fish", "kuda": "horse", "harimau": "tiger", "singa": "lion", "kupu": "butterfly",
    "ular": "snake", "naga": "dragon", "hewan": "animal", "binatang": "animal",
    "serangga": "insect", "tengkorak": "skull", "hantu": "ghost", "malaikat": "angel", "iblis": "demon",
    # colors (also detected as color intents below)
    "merah": "red", "biru": "blue", "hijau": "green", "kuning": "yellow", "oranye": "orange", "jingga": "orange",
    "ungu": "purple", "pink": "pink", "hitam": "black", "putih": "white", "abu": "gray",
    "coklat": "brown", "cokelat": "brown", "krem": "beige", "tosca": "teal", "toska": "teal", "nila": "indigo",
    # moods / styles
    "estetik": "aesthetic", "estetika": "aesthetic", "keren": "cool", "lucu": "cute", "imut": "cute",
    "seram": "creepy", "serem": "creepy", "horor": "horror", "menyeramkan": "scary", "sedih": "sad",
    "galau": "melancholic", "sendu": "melancholic", "bahagia": "happy", "senang": "happy", "ceria": "cheerful",
    "mewah": "luxury", "elegan": "elegant", "megah": "grand", "sederhana": "simple", "simpel": "simple",
    "bersih": "clean", "kotor": "dirty", "rusak": "damaged", "tua": "old", "kuno": "ancient", "antik": "antique",
    "jadul": "retro", "klasik": "classic", "modern": "modern", "futuristik": "futuristic", "tenang": "calm",
    "kalem": "calm", "adem": "calm", "damai": "peaceful", "romantis": "romantic", "misterius": "mysterious",
    "dramatis": "dramatic", "sinematik": "cinematic", "epik": "epic", "hangat": "warm", "dingin": "cold",
    "lembut": "soft", "kasar": "rough", "tajam": "sharp", "buram": "blurry", "blur": "blur", "kabur": "blurry",
    "berkilau": "shiny", "mengkilap": "glossy", "transparan": "transparent", "berwarna": "colorful",
    "warna-warni": "colorful", "cerah": "vibrant", "pudar": "faded", "suram": "gloomy", "sepi": "lonely",
    "ramai": "busy", "liar": "wild", "alami": "natural", "abstrak": "abstract", "geometris": "geometric",
    "minimalis": "minimalist", "tradisional": "traditional", "budaya": "culture", "etnik": "ethnic",
    # motion & editing vocabulary
    "transisi": "transition", "partikel": "particles", "ledakan": "explosion", "meledak": "explosion",
    "percikan": "sparks", "kilauan": "sparkle", "kilau": "glow", "cahaya2": "lights", "efek": "effect",
    "gerak": "motion", "gerakan": "movement", "berputar": "spinning", "putar": "rotate", "zoom": "zoom",
    "goyang": "shake", "getar": "shake", "bergelombang": "wavy", "cair": "liquid", "tetes": "drops",
    "tetesan": "drops", "gelembung": "bubbles", "latar": "background", "background": "background",
    "bingkai": "frame", "garis": "lines", "titik": "dots", "pola": "pattern", "motif": "pattern",
    "tekstur": "texture", "gradasi": "gradient", "bayangan2": "shadows", "siluet": "silhouette",
    "sketsa": "sketch", "lukisan": "painting", "coretan": "doodle",
    "grafiti": "graffiti", "tulisan": "lettering", "judul": "title", "teks": "text", "kartun": "cartoon",
    "karakter": "character", "ilustrasi": "illustration", "desain": "design", "stiker": "sticker", "poster": "poster",
    "sampul": "cover", "kemasan": "packaging", "undangan": "invitation", "pernikahan": "wedding",
    "natal": "christmas", "lebaran": "eid", "ramadan": "ramadan",
    "ramadhan": "ramadan", "imlek": "chinese new year", "kemerdekaan": "independence day", "merdeka": "independence",
    "batik": "batik", "wayang": "wayang", "gamelan": "gamelan", "keris": "kris",
}

# Explicit FORMAT words that imply what kind of asset you want. Content-ish
# words ("texture", "sticker", "mesh gradient", "script font") are deliberately
# NOT here: they should widen the search, not filter it.
KIND_WORDS: dict[str, tuple[str, ...]] = {
    "video": (Kind.VIDEO,), "videos": (Kind.VIDEO,), "footage": (Kind.VIDEO,), "stock footage": (Kind.VIDEO,),
    "klip": (Kind.VIDEO,), "b-roll": (Kind.VIDEO,), "broll": (Kind.VIDEO,), "cuplikan": (Kind.VIDEO,),
    "gif": (Kind.GIF,), "gifs": (Kind.GIF,),
    "lottie": (Kind.MOTION,), "lotties": (Kind.MOTION,),
    "motion": (Kind.VIDEO, Kind.GIF, Kind.MOTION), "motion graphics": (Kind.VIDEO, Kind.GIF, Kind.MOTION),
    "animasi": (Kind.VIDEO, Kind.GIF, Kind.MOTION), "animation": (Kind.VIDEO, Kind.GIF, Kind.MOTION),
    "animated": (Kind.VIDEO, Kind.GIF, Kind.MOTION),
    "sfx": (Kind.AUDIO,), "sound effect": (Kind.AUDIO,), "sound effects": (Kind.AUDIO,),
    "efek suara": (Kind.AUDIO,), "suara": (Kind.AUDIO,), "audio": (Kind.AUDIO,), "musik": (Kind.AUDIO,),
    "music": (Kind.AUDIO,), "lagu": (Kind.AUDIO,), "song": (Kind.AUDIO,), "backsound": (Kind.AUDIO,),
    "bgm": (Kind.AUDIO,),
    "icon": (Kind.ICON,), "icons": (Kind.ICON,), "ikon": (Kind.ICON,),
    "font": (Kind.FONT,), "fonts": (Kind.FONT,), "typeface": (Kind.FONT,), "huruf": (Kind.FONT,),
    "pbr": (Kind.TEXTURE,), "pbr texture": (Kind.TEXTURE,), "pbr material": (Kind.TEXTURE,),
    "hdri": (Kind.HDRI,), "hdris": (Kind.HDRI,), "skybox": (Kind.HDRI,), "environment map": (Kind.HDRI,),
    "3d model": (Kind.MODEL3D,), "3d models": (Kind.MODEL3D,), "model 3d": (Kind.MODEL3D,),
    "glb": (Kind.MODEL3D,), "gltf": (Kind.MODEL3D,), "fbx": (Kind.MODEL3D,), "obj": (Kind.MODEL3D,),
    "foto": (Kind.IMAGE,), "photo": (Kind.IMAGE,), "photos": (Kind.IMAGE,), "gambar": (Kind.IMAGE,),
    "image": (Kind.IMAGE,), "images": (Kind.IMAGE,), "picture": (Kind.IMAGE,), "pictures": (Kind.IMAGE,),
    "wallpaper": (Kind.IMAGE,), "wallpapers": (Kind.IMAGE,),
    "github": (Kind.CODE,), "repo": (Kind.CODE,), "repository": (Kind.CODE,), "plugin": (Kind.CODE,),
    "plugins": (Kind.CODE,), "kode": (Kind.CODE,), "code": (Kind.CODE,),
    "template": (Kind.TEMPLATE, Kind.CODE), "templates": (Kind.TEMPLATE, Kind.CODE),
    "mogrt": (Kind.TEMPLATE,), "aep": (Kind.TEMPLATE,), "preset": (Kind.TEMPLATE,), "presets": (Kind.TEMPLATE,),
    "lut": (Kind.TEMPLATE,), "luts": (Kind.TEMPLATE,),
}

# Indonesian words that are also common English words; only translated when the
# query clearly is Indonesian ("air terjun" yes, "hot air balloon" no).
AMBIGUOUS = {"air", "jam", "sore", "api", "kaki", "es", "man", "pasar", "tua", "lari"}

ID_STOPWORDS = {
    "yang", "yg", "dan", "dgn", "dengan", "di", "ke", "dari", "untuk", "utk", "buat", "atau", "ini", "itu", "ada",
    "aja", "saja", "dong", "sih", "deh", "nih", "tuh", "kok", "pake", "pakai", "cari", "carikan", "mau", "pengen",
    "pingin", "butuh", "perlu", "kayak", "kaya", "kyk", "seperti", "mirip", "gitu", "banget", "bgt", "gw", "gue",
}
ID_SIGNAL = ({w for w, e in ID_EN.items() if w != e} - AMBIGUOUS) | ID_STOPWORDS

USAGE_WORDS = {
    "free": "usable", "gratis": "usable", "gratisan": "usable", "royalty free": "usable", "royalty-free": "usable",
    "bebas royalti": "usable", "no copyright": "usable", "copyright free": "usable", "bebas hak cipta": "usable",
    "tanpa hak cipta": "usable", "non copyright": "usable", "nocopyright": "usable", "komersial": "usable",
    "commercial": "usable", "commercial use": "usable", "boleh dipakai": "usable", "bisa dipakai": "usable",
    "bisa dipake": "usable", "cc0": "free", "public domain": "free", "domain publik": "free",
    "no attribution": "free", "tanpa atribusi": "free", "tanpa kredit": "free", "no credit": "free",
}

COLOR_WORDS = {
    "red": "#e53935", "merah": "#e53935", "blue": "#1e63d6", "biru": "#1e63d6", "green": "#2e9d4a",
    "hijau": "#2e9d4a", "yellow": "#f5d000", "kuning": "#f5d000", "orange": "#f57c00", "oranye": "#f57c00",
    "jingga": "#f57c00", "purple": "#7b3fbf", "ungu": "#7b3fbf", "violet": "#7b3fbf", "pink": "#f06ba8",
    "merah muda": "#f06ba8", "black": "#111111", "hitam": "#111111", "white": "#f7f7f5", "putih": "#f7f7f5",
    "gray": "#8a8a8a", "grey": "#8a8a8a", "abu": "#8a8a8a", "abu abu": "#8a8a8a", "brown": "#7a4a2a",
    "coklat": "#7a4a2a", "cokelat": "#7a4a2a", "gold": "#d4a72c", "golden": "#d4a72c", "emas": "#d4a72c",
    "silver": "#c0c4c8", "perak": "#c0c4c8", "teal": "#0f9a94", "tosca": "#0f9a94", "toska": "#0f9a94",
    "cyan": "#18c5e6", "magenta": "#d6249f", "navy": "#14234f", "beige": "#e6d5b8", "krem": "#e6d5b8",
    "cream": "#efe4cc", "maroon": "#6d1a24", "turquoise": "#22c2b0", "lime": "#9bd12a", "indigo": "#3f3fa8",
}

VIBES: dict[str, list[str]] = {
    "cyberpunk": ["neon city", "futuristic night", "hologram", "rainy street neon", "dystopian"],
    "vaporwave": ["pastel retro", "80s grid", "palm sunset", "glitch", "statue aesthetic"],
    "synthwave": ["neon grid", "retro futurism", "outrun sunset", "80s"],
    "y2k": ["chrome", "glossy bubble", "iridescent", "2000s futuristic", "blobject"],
    "aesthetic": ["soft film", "pastel", "moody", "minimal", "dreamy"],
    "retro": ["vintage", "70s", "80s", "film grain", "faded colors"],
    "vintage": ["retro", "old film", "sepia", "paper texture", "grain"],
    "minimal": ["clean", "white space", "simple shapes", "geometric"],
    "minimalist": ["clean", "white space", "simple shapes", "geometric"],
    "brutalism": ["concrete", "raw", "bold typography", "grid layout"],
    "brutalist": ["concrete", "raw", "bold typography", "grid layout"],
    "grunge": ["distressed", "dirty texture", "scratches", "dark"],
    "dark": ["moody", "low key", "noir", "dramatic light"],
    "moody": ["dark", "low key", "film", "fog"],
    "dreamy": ["soft focus", "haze", "pastel", "clouds", "glow"],
    "cinematic": ["film still", "anamorphic", "lens flare", "dramatic light", "widescreen"],
    "anime": ["manga", "cel shading", "japanese illustration", "lofi"],
    "lofi": ["chill", "cozy room", "anime", "rain window"],
    "glitch": ["datamosh", "rgb split", "noise", "distortion", "vhs"],
    "holographic": ["iridescent", "rainbow foil", "chrome", "gradient"],
    "iridescent": ["holographic", "rainbow", "pearl", "chrome"],
    "liquid": ["fluid", "liquid chrome", "wavy", "blob", "gradient"],
    "neon": ["glow", "night", "neon sign", "cyberpunk"],
    "cozy": ["warm light", "home", "autumn", "coffee", "candle"],
    "horror": ["dark", "fog", "abandoned", "eerie", "creepy"],
    "creepy": ["horror", "dark", "eerie", "abandoned"],
    "futuristic": ["sci-fi", "hologram", "technology", "space"],
    "space": ["nebula", "stars", "galaxy", "planet", "cosmos"],
    "abstract": ["shapes", "gradient", "pattern", "geometric", "fluid"],
    "gradient": ["mesh gradient", "blur", "aura", "color"],
    "film": ["35mm", "film grain", "analog", "light leak"],
    "analog": ["film grain", "vhs", "polaroid", "35mm"],
    "vhs": ["tape", "glitch", "90s", "scanlines", "retro"],
    "street": ["urban", "city", "graffiti", "night"],
    "urban": ["city", "street", "concrete", "architecture"],
    "luxury": ["gold", "marble", "elegant", "black"],
    "elegant": ["serif", "minimal", "luxury", "classy"],
    "pastel": ["soft colors", "dreamy", "cute"],
    "cute": ["kawaii", "pastel", "sticker", "cartoon"],
    "kawaii": ["cute", "pastel", "japanese", "cartoon"],
    "corporate": ["business", "office", "clean", "flat illustration"],
    "isometric": ["3d illustration", "low poly", "vector"],
    "pixel": ["pixel art", "8-bit", "retro game", "sprite"],
    "ethereal": ["light", "glow", "soft", "dreamy"],
    "gothic": ["dark", "cathedral", "black", "medieval"],
    "tropical": ["palm", "beach", "summer", "vibrant"],
    "summer": ["beach", "sun", "vibrant", "tropical"],
    "winter": ["snow", "cold", "blue", "frost"],
    "autumn": ["fall leaves", "orange", "warm", "cozy"],
    "rain": ["rainy window", "wet street", "drops", "storm"],
    "smoke": ["fog", "mist", "haze", "particles"],
    "fire": ["flames", "embers", "sparks", "heat"],
    "particles": ["dust", "sparkles", "bokeh", "embers"],
    "transition": ["whoosh", "swipe", "zoom transition", "glitch transition"],
    "overlay": ["light leak", "dust", "film grain", "bokeh"],
    "typography": ["lettering", "type poster", "kinetic type"],
    "poster": ["print", "typography", "layout", "swiss design"],
    "swiss": ["grid", "helvetica", "international style", "minimal"],
    "bauhaus": ["geometric", "primary colors", "modernism"],
    "memphis": ["80s pattern", "squiggle", "bold colors"],
    "editorial": ["fashion", "magazine", "portrait", "layout"],
    "fashion": ["editorial", "runway", "model", "style"],
    "portrait": ["face", "close up", "studio light"],
    "product": ["packshot", "studio", "clean background"],
    "chrome": ["metallic", "reflective", "y2k", "liquid metal"],
    "glass": ["glassmorphism", "transparent", "refraction"],
    "paper": ["paper texture", "collage", "cutout", "craft"],
    "collage": ["cutout", "paper", "mixed media", "zine"],
    "halftone": ["dots", "print", "pop art", "comic"],
    "surreal": ["dreamlike", "strange", "impossible", "art"],
    "noir": ["black and white", "shadow", "detective"],
    "sunset": ["golden hour", "orange sky", "silhouette"],
    "night": ["dark", "city lights", "stars", "moon"],
    "city": ["skyline", "street", "urban", "night lights"],
    "ocean": ["waves", "sea", "underwater", "blue"],
    "flower": ["floral", "bloom", "petals", "garden"],
    "wedding": ["elegant", "floral", "romantic", "white"],
    "ramadan": ["lantern", "mosque", "crescent", "arabesque pattern"],
    "eid": ["ketupat", "mosque", "crescent", "green gold"],
    "batik": ["indonesian pattern", "javanese", "textile"],
    "indonesia": ["bali", "jakarta", "batik", "tropical"],
    "concert": ["stage lights", "crowd", "festival"],
    "gaming": ["esports", "neon", "controller", "rgb"],
    "tech": ["circuit", "futuristic", "data", "digital"],
}

STARTER_TOPICS: list[str] = [
    "light leak", "film grain", "glitch", "neon", "cyberpunk city", "vaporwave", "y2k chrome",
    "liquid gradient", "abstract background", "particles", "smoke", "fire", "explosion", "lens flare",
    "bokeh", "rain", "clouds", "ocean waves", "city night", "retro 80s", "paper texture", "grunge texture",
    "halftone", "brutalist poster", "swiss poster", "typography poster", "holographic", "dust particles",
    "transition", "whoosh", "impact", "cinematic", "anime aesthetic", "nebula", "sunset", "portrait",
    "architecture", "studio hdri", "wood", "metal", "marble", "concrete", "fabric", "loading", "arrow",
    "social media", "sticker", "batik", "ramadan",
]


@dataclass
class ParsedQuery:
    raw: str
    text: str = ""
    terms: list[str] = field(default_factory=list)
    kinds: set[str] = field(default_factory=set)
    usage: str | None = None
    colors: list[str] = field(default_factory=list)
    vibes: list[str] = field(default_factory=list)
    translated: bool = False

    @property
    def key(self) -> str:
        return normalize_key(self.text or self.raw)


_TOKEN_RE = re.compile(r"[\w+#&.'-]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    out: list[str] = []
    for tok in _TOKEN_RE.findall((text or "").lower()):
        tok = tok.strip(".'-&")
        if not tok:
            continue
        # reduplication: bunga-bunga -> bunga, but keep things like sci-fi / lo-fi / b-roll
        if "-" in tok:
            a, _, b = tok.partition("-")
            if a == b:
                tok = a
        out.append(tok)
    return out


def normalize_key(text: str) -> str:
    return " ".join(sorted(set(tokenize(text))))


_PHRASE_TABLES = (USAGE_WORDS, KIND_WORDS, ID_PHRASES, COLOR_WORDS)


def _longest_phrase(tokens: list[str], i: int, max_len: int = 3) -> tuple[str, int]:
    for n in range(min(max_len, len(tokens) - i), 1, -1):
        phrase = " ".join(tokens[i:i + n])
        if any(phrase in table for table in _PHRASE_TABLES):
            return phrase, n
    return tokens[i], 1


def parse_query(raw: str) -> ParsedQuery:
    pq = ParsedQuery(raw=raw or "")
    tokens = tokenize(raw)
    indonesian = any(t in ID_SIGNAL for t in tokens) or any(
        " ".join(tokens[i:i + 2]) in ID_PHRASES for i in range(len(tokens) - 1)
    )
    english: list[str] = []
    original_terms: list[str] = []
    kind_hits: list[tuple[str, tuple[str, ...]]] = []
    i = 0
    while i < len(tokens):
        unit, step = _longest_phrase(tokens, i)
        i += step
        if unit in USAGE_WORDS:
            pq.usage = _stronger_usage(pq.usage, USAGE_WORDS[unit])
            continue
        if unit in KIND_WORDS:
            kind_hits.append((unit, KIND_WORDS[unit]))
            continue
        if unit in STOPWORDS:
            continue
        if unit in COLOR_WORDS:
            pq.colors.append(COLOR_WORDS[unit])
        translation = ID_PHRASES.get(unit)
        if translation is None and unit in ID_EN and (unit not in AMBIGUOUS or indonesian):
            translation = ID_EN[unit]
        if translation is not None:
            english.append(translation)
            original_terms.append(unit)
            pq.translated = pq.translated or translation != unit
        else:
            english.append(unit)

    if kind_hits:
        if english:
            for _, kinds in kind_hits:
                pq.kinds.update(kinds)
        else:
            # query is only kind words ("sfx", "lottie") → treat them as content too
            for word, kinds in kind_hits:
                pq.kinds.update(kinds)
                english.append(ID_EN.get(word, word))

    seen: set[str] = set()
    words: list[str] = []
    for phrase in english:
        for w in phrase.split():
            if w not in seen:
                seen.add(w)
                words.append(w)
    pq.text = " ".join(words)
    terms = list(words)
    for t in original_terms:
        for w in t.split():
            if w not in seen:
                seen.add(w)
                terms.append(w)
    pq.terms = terms
    pq.colors = list(dict.fromkeys(pq.colors))
    pq.vibes = suggest_vibes(words)
    return pq


def _stronger_usage(current: str | None, new: str) -> str:
    order = {None: 0, "usable": 1, "free": 2}
    return new if order.get(new, 0) > order.get(current, 0) else (current or new)


def suggest_vibes(words: list[str], limit: int = 8) -> list[str]:
    have = set(words)
    joined = " ".join(words)
    out: list[str] = []
    for w in words:
        for v in VIBES.get(w, []) + VIBES.get(w.rstrip("s"), []):
            if v not in out and v not in have and v not in joined:
                out.append(v)
    return out[:limit]
