"""Vibe vectors: how NOZE knows two things "feel" alike.

* HashEmbedder (default, zero downloads): hashed words/character n-grams of
  title+tags plus a 64-bin color histogram of the thumbnail. Catches shared
  vocabulary and similar palettes.
* FastEmbedder (pip install 'noze[clip]'): real CLIP / SigLIP2 image+text
  embeddings via ONNX. Text and images share one space, so "moody rainy neon
  street" finds matching pictures even with zero matching tags — the same
  trick behind Pinterest's visual search.
"""

from __future__ import annotations

import logging
import re
import threading
import zlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .imaging import hist_for_colors

log = logging.getLogger("noze.embeddings")


@dataclass
class EmbedInput:
    text: str
    thumb_path: Path | None = None
    hist: np.ndarray | None = None


def _normalize(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32).reshape(-1)
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


class Embedder:
    name = "none"
    dim = 0
    ready = True

    def load(self) -> None:
        pass

    def embed_query(self, text: str, colors: list[str] | None = None) -> np.ndarray:
        raise NotImplementedError

    def embed_assets(self, items: list[EmbedInput]) -> list[tuple[np.ndarray, str]]:
        raise NotImplementedError


class HashEmbedder(Embedder):
    name = "hash-v1"
    TEXT_DIM = 256
    COLOR_DIM = 64
    dim = TEXT_DIM + COLOR_DIM
    _word = re.compile(r"[a-z0-9]+")

    def _text_vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.TEXT_DIM, dtype=np.float32)
        words = self._word.findall((text or "").lower())
        feats: dict[str, float] = {}
        for w in words:
            feats[w] = feats.get(w, 0.0) + 1.0
            stem = "~" + (w[:-1] if len(w) > 4 and w.endswith("s") else w)  # clouds ~ cloud
            feats[stem] = feats.get(stem, 0.0) + 1.0
            padded = f"<{w}>"
            for i in range(len(padded) - 2):
                g = "#" + padded[i:i + 3]
                feats[g] = feats.get(g, 0.0) + 0.25
        for a, b in zip(words, words[1:]):
            k = f"{a}_{b}"
            feats[k] = feats.get(k, 0.0) + 0.7
        for f, tf in feats.items():
            h = zlib.crc32(f.encode("utf-8"))
            sign = 1.0 if (h >> 31) & 1 else -1.0
            v[h % self.TEXT_DIM] += sign * float(np.log1p(tf))
        return _normalize(v)

    def _combine(self, t: np.ndarray, c: np.ndarray | None) -> np.ndarray:
        if c is None or not np.any(c):
            c = np.zeros(self.COLOR_DIM, dtype=np.float32)
            return _normalize(np.concatenate([t, c]))
        return _normalize(np.concatenate([0.85 * t, 0.53 * _normalize(c)]))

    def embed_query(self, text: str, colors: list[str] | None = None) -> np.ndarray:
        c = hist_for_colors(colors) if colors else None
        return self._combine(self._text_vec(text), c)

    def embed_assets(self, items: list[EmbedInput]) -> list[tuple[np.ndarray, str]]:
        return [(self._combine(self._text_vec(it.text), it.hist), "hash") for it in items]


PRESETS = {
    "clip": ("clip-vit-b32", "Qdrant/clip-ViT-B-32-vision", "Qdrant/clip-ViT-B-32-text"),
    # multilingual text side: Indonesian queries work without translation
    "siglip2": ("siglip2-b16", "google/siglip2-base-patch16-224", "google/siglip2-base-patch16-224"),
}


class FastEmbedder(Embedder):
    def __init__(self, preset: str, cache_dir: Path):
        if preset not in PRESETS:
            raise ValueError(f"unknown embedder preset {preset!r}")
        self.name, self.image_model_name, self.text_model_name = PRESETS[preset]
        self.cache_dir = cache_dir
        self._image = None
        self._text = None
        self._lock = threading.Lock()
        self.ready = False
        self.dim = 0

    def load(self) -> None:
        with self._lock:
            if self.ready:
                return
            from fastembed import ImageEmbedding, TextEmbedding

            self.cache_dir.mkdir(parents=True, exist_ok=True)
            log.info("loading %s (first run downloads the model)…", self.name)
            self._image = ImageEmbedding(self.image_model_name, cache_dir=str(self.cache_dir))
            self._text = TextEmbedding(self.text_model_name, cache_dir=str(self.cache_dir))
            probe = next(iter(self._text.embed(["probe"])))
            self.dim = int(np.asarray(probe).reshape(-1).shape[0])
            self.ready = True
            log.info("%s ready (dim=%d)", self.name, self.dim)

    def embed_query(self, text: str, colors: list[str] | None = None) -> np.ndarray:
        if not self.ready:
            self.load()
        return _normalize(next(iter(self._text.embed([text or "image"]))))

    def embed_assets(self, items: list[EmbedInput]) -> list[tuple[np.ndarray, str]]:
        if not self.ready:
            self.load()
        out: list[tuple[np.ndarray, str] | None] = [None] * len(items)
        img_idx = [i for i, it in enumerate(items)
                   if it.thumb_path and it.thumb_path.exists() and it.thumb_path.suffix.lower() != ".svg"]
        if img_idx:
            try:
                vecs = list(self._image.embed([str(items[i].thumb_path) for i in img_idx], batch_size=16))
                for i, v in zip(img_idx, vecs):
                    out[i] = (_normalize(v), "image")
            except Exception as exc:  # a corrupt thumbnail must not kill the batch
                log.warning("image embedding batch failed (%s); falling back to text for it", exc)
        txt_idx = [i for i, o in enumerate(out) if o is None]
        if txt_idx:
            vecs = list(self._text.embed([items[i].text or "untitled" for i in txt_idx], batch_size=32))
            for i, v in zip(txt_idx, vecs):
                out[i] = (_normalize(v), "text")
        return [o for o in out if o is not None]


def make_embedder(choice: str, models_dir: Path) -> Embedder:
    choice = (choice or "auto").lower()
    if choice == "hash":
        return HashEmbedder()
    preset = "clip" if choice == "auto" else choice
    try:
        import fastembed  # noqa: F401
    except ImportError:
        if choice != "auto":
            log.warning("NOZE_EMBEDDER=%s needs `pip install 'noze[clip]'`; using the lightweight hash embedder", choice)
        return HashEmbedder()
    return FastEmbedder(preset, models_dir)


class VectorIndex:
    """In-memory matrix of vectors for one model; brute-force cosine search.

    Fast enough for a personal bank (a few hundred thousand items ~ tens of ms).
    Scores are z-normalized per modality so CLIP text-embedded items (fonts,
    repos) and image-embedded items can be ranked together fairly.
    """

    def __init__(self, model: str = "", dim: int = 0):
        self.model = model
        self.dim = dim
        self._lock = threading.RLock()
        self._ids: list[str] = []
        self._pos: dict[str, int] = {}
        self._mods: list[str] = []
        self._mat = np.zeros((0, dim), dtype=np.float32)
        self._pending: list[np.ndarray] = []

    def __len__(self) -> int:
        return len(self._ids)

    def reset(self, model: str, dim: int) -> None:
        with self._lock:
            self.model, self.dim = model, dim
            self._ids, self._pos, self._mods, self._pending = [], {}, [], []
            self._mat = np.zeros((0, dim), dtype=np.float32)

    def load(self, rows) -> int:
        """rows: iterable of (asset_id, modality, float16 bytes)."""
        with self._lock:
            vecs = []
            for aid, mod, blob in rows:
                v = np.frombuffer(blob, dtype=np.float16).astype(np.float32)
                if self.dim == 0:
                    self.dim = v.shape[0]
                if v.shape[0] != self.dim:
                    continue
                self._pos[aid] = len(self._ids)
                self._ids.append(aid)
                self._mods.append(mod)
                vecs.append(v)
            if vecs:
                self._mat = np.vstack([self._mat.reshape(-1, self.dim)] + [np.stack(vecs)])
            return len(vecs)

    def add(self, asset_id: str, vec: np.ndarray, modality: str) -> None:
        vec = np.asarray(vec, dtype=np.float32).reshape(-1)
        with self._lock:
            if self.dim == 0:
                self.dim = vec.shape[0]
                self._mat = np.zeros((0, self.dim), dtype=np.float32)
            if vec.shape[0] != self.dim:
                return
            if asset_id in self._pos:
                self._flush()
                self._mat[self._pos[asset_id]] = vec
                self._mods[self._pos[asset_id]] = modality
                return
            self._pos[asset_id] = len(self._ids)
            self._ids.append(asset_id)
            self._mods.append(modality)
            self._pending.append(vec)

    def _flush(self) -> None:
        if self._pending:
            self._mat = np.vstack([self._mat.reshape(-1, self.dim), np.stack(self._pending)])
            self._pending = []

    def get(self, asset_id: str) -> np.ndarray | None:
        with self._lock:
            self._flush()
            pos = self._pos.get(asset_id)
            return None if pos is None else self._mat[pos].copy()

    def search(self, q: np.ndarray, k: int = 300, allowed: set[str] | None = None,
               exclude: set[str] | None = None) -> list[tuple[str, float]]:
        with self._lock:
            self._flush()
            if not self._ids or q is None:
                return []
            q = np.asarray(q, dtype=np.float32).reshape(-1)
            if q.shape[0] != self.dim:
                return []
            scores = self._mat @ q
            mods = np.array(self._mods)
            if len(set(self._mods)) > 1:
                scores = scores.copy()
                for m in set(self._mods):
                    mask = mods == m
                    s = scores[mask]
                    sd = float(s.std()) or 1.0
                    scores[mask] = (s - float(s.mean())) / sd
            if allowed is not None:
                idx = np.array([self._pos[a] for a in allowed if a in self._pos], dtype=np.int64)
                if idx.size == 0:
                    return []
                sub = scores[idx]
                order = idx[np.argsort(-sub)]
            else:
                kk = min(len(scores), k + (len(exclude) if exclude else 0) + 1)
                part = np.argpartition(-scores, kk - 1)[:kk]
                order = part[np.argsort(-scores[part])]
            out: list[tuple[str, float]] = []
            for i in order:
                aid = self._ids[int(i)]
                if exclude and aid in exclude:
                    continue
                out.append((aid, float(scores[int(i)])))
                if len(out) >= k:
                    break
            return out

    def zscores(self, q: np.ndarray, ids: list[str]) -> dict[str, float]:
        """How unusually similar each item is to q, compared with the whole index (per modality).
        Robust across models: raw CLIP cosines live in a narrow band, z-scores don't."""
        with self._lock:
            self._flush()
            if not self._ids or q is None:
                return {}
            q = np.asarray(q, dtype=np.float32).reshape(-1)
            if q.shape[0] != self.dim:
                return {}
            scores = self._mat @ q
            mods = np.array(self._mods)
            stats = {}
            for m in set(self._mods):
                sm = scores[mods == m]
                stats[m] = (float(sm.mean()), float(sm.std()) or 1.0)
            out = {}
            for aid in ids:
                pos = self._pos.get(aid)
                if pos is not None:
                    mean, sd = stats[self._mods[pos]]
                    out[aid] = (float(scores[pos]) - mean) / sd
            return out

    def similarity_matrix(self, ids: list[str]) -> tuple[np.ndarray, list[bool]]:
        """Pairwise cosine for MMR diversification; rows for ids without vectors are zero."""
        with self._lock:
            self._flush()
            n = len(ids)
            vecs = np.zeros((n, max(self.dim, 1)), dtype=np.float32)
            present = []
            for j, aid in enumerate(ids):
                pos = self._pos.get(aid)
                if pos is not None:
                    vecs[j] = self._mat[pos]
                present.append(pos is not None)
            return vecs @ vecs.T, present


def to_blob(vec: np.ndarray) -> bytes:
    return np.asarray(vec, dtype=np.float16).tobytes()
