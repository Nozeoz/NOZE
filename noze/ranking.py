"""Small ranking toolkit: reciprocal-rank fusion and MMR diversification."""

from __future__ import annotations

from typing import Callable, Iterable

import numpy as np

from .embeddings import VectorIndex


def rrf(lists: Iterable[tuple[list[str], float]], k: float = 60.0) -> dict[str, float]:
    """Reciprocal Rank Fusion: robustly merges rankings from different signals
    (source relevance, keyword BM25, vectors, board co-occurrence…)."""
    scores: dict[str, float] = {}
    for ids, weight in lists:
        if weight <= 0:
            continue
        for rank, aid in enumerate(ids):
            scores[aid] = scores.get(aid, 0.0) + weight / (k + rank + 1)
    return scores


def normalize(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return scores
    top = max(scores.values()) or 1.0
    return {k: v / top for k, v in scores.items()}


def mmr(
    ordered: list[str],
    scores: dict[str, float],
    index: VectorIndex,
    top_n: int = 300,
    penalty: float = 0.35,
    group_of: Callable[[str], str] | None = None,
    group_penalty: float = 0.04,
    duplicate_of: Callable[[str], str | None] | None = None,
) -> list[str]:
    """Maximal Marginal Relevance over the head of the list so one look/source
    doesn't take over the grid (Pinterest diversifies its feeds the same way)."""
    head, tail = ordered[:top_n], ordered[top_n:]
    if len(head) < 3:
        return ordered
    sims, present = index.similarity_matrix(head)
    base = np.array([scores.get(a, 0.0) for a in head], dtype=np.float32)
    has_vec = np.array(present, dtype=bool)
    chosen: list[int] = []
    max_sim = np.zeros(len(head), dtype=np.float32)
    remaining = np.ones(len(head), dtype=bool)
    group_counts: dict[str, int] = {}
    seen_dupes: set[str] = set()
    groups = [group_of(a) if group_of else "" for a in head]
    dupes = [duplicate_of(a) if duplicate_of else None for a in head]
    while remaining.any():
        adj = base - penalty * np.where(has_vec, max_sim, 0.0)
        if group_of:
            adj = adj - group_penalty * np.array([group_counts.get(g, 0) for g in groups], dtype=np.float32)
        adj = np.where(remaining, adj, -np.inf)
        j = int(np.argmax(adj))
        remaining[j] = False
        d = dupes[j]
        if d:
            if d in seen_dupes:
                continue  # exact visual duplicate of something already shown
            seen_dupes.add(d)
        chosen.append(j)
        if has_vec[j]:
            max_sim = np.maximum(max_sim, sims[j])
        if group_of:
            group_counts[groups[j]] = group_counts.get(groups[j], 0) + 1
    return [head[j] for j in chosen] + tail
