"""
Style Score Module — Phase 8.

Scores stylistic cohesion between items in a candidate outfit using
embedding cosine similarity.

When embeddings are available (stored as 512-dim JSON arrays):
  → Cosine similarity averaged over all pairs.

When embeddings are absent:
  → Pattern coherence fallback: penalise outfit if more than one item
    has a busy pattern (floral, graphic, animal-print, etc.).
"""

from __future__ import annotations

import math
from typing import List, Optional


# Patterns considered "busy" — two busy items in one outfit → style clash
BUSY_PATTERNS = {"floral", "graphic", "animal-print", "camouflage", "polka-dot"}


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """L2-normalised dot product. Returns value in [-1, 1]."""
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _pattern_coherence_score(patterns: List[Optional[str]]) -> float:
    """
    Fallback score based on pattern variety.
    - 0 or 1 busy items: neutral-good (0.78)
    - 2+ busy items: clash penalty proportional to count
    """
    busy_count = sum(
        1 for p in patterns
        if p and p.lower().strip() in BUSY_PATTERNS
    )
    if busy_count == 0:
        return 0.85  # all solid/minimal → naturally cohesive
    if busy_count == 1:
        return 0.78  # one statement piece is fine
    # 2 → 0.50, 3 → 0.30, 4+ → 0.20
    penalty = min(0.10 * (busy_count - 1), 0.65)
    return max(0.20, round(0.85 - penalty, 4))


def calculate_style_score(
    embeddings: Optional[List[Optional[List[float]]]] = None,
    patterns: Optional[List[Optional[str]]] = None,
) -> float:
    """
    Compute style cohesion score in [0.0, 1.0].

    Args:
        embeddings: List of 512-dim embedding vectors (one per item).
                    Items with no embedding should be None in the list.
        patterns:   List of pattern strings (one per item), used as fallback.

    Returns:
        Score in [0.0, 1.0].
    """
    # Try embedding cosine similarity first
    valid_embeddings = [e for e in (embeddings or []) if e]
    if len(valid_embeddings) >= 2:
        sims = []
        for i in range(len(valid_embeddings)):
            for j in range(i + 1, len(valid_embeddings)):
                sim = _cosine_similarity(valid_embeddings[i], valid_embeddings[j])
                # Shift from [-1,1] to [0,1]
                sims.append((sim + 1.0) / 2.0)
        if sims:
            return round(sum(sims) / len(sims), 4)

    # Fallback: pattern coherence
    return _pattern_coherence_score(patterns or [])
