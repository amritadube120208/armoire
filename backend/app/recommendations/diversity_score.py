"""
Diversity Score Module — Phase 8.

Penalises candidates that are near-identical to outfits the user wore recently,
ensuring the recommendation list surfaces variety.

Algorithm:
  1. Each candidate outfit is represented by its sorted set of item IDs.
  2. Jaccard similarity is computed against each recently worn outfit's item set.
  3. The maximum Jaccard similarity to ANY recent outfit becomes the repetition signal.
  4. diversity_score = 1.0 − (max_jaccard * repetition_weight)
     where repetition_weight decays exponentially with age (recent duplicates penalised more).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Set


def _jaccard(set_a: Set[str], set_b: Set[str]) -> float:
    """Jaccard index between two sets."""
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _recency_weight(worn_date: Optional[date]) -> float:
    """
    Exponential decay of repetition penalty based on outfit age.
    
    - Worn today  → 1.00 (full penalty if duplicate)
    - 7 days ago  → 0.70
    - 14 days ago → 0.49
    - 30 days ago → 0.25
    - 60+ days    → ≤ 0.06 (very low penalty for old outfits)
    """
    if worn_date is None:
        return 0.30  # unknown — apply moderate recency weight
    today = datetime.now(timezone.utc).date()
    days_ago = (today - worn_date).days
    # decay rate: half-life ≈ 10 days  (0.5^(1/10))
    weight = 0.5 ** (days_ago / 10.0)
    return round(min(1.0, weight), 4)


def calculate_diversity_score(
    candidate_item_ids: List[str],
    recent_outfit_items: Optional[List[Dict[str, Any]]] = None,
) -> float:
    """
    Compute diversity score in [0.0, 1.0] for a candidate outfit.

    Args:
        candidate_item_ids: List of clothing item UUID strings in the candidate outfit.
        recent_outfit_items: List of dicts describing recently worn outfits.
            Each dict should have:
              - "item_ids": List[str]  — item IDs in that past outfit
              - "worn_date": Optional[date]  — when it was last worn (None if unknown)

    Returns:
        Score in [0.0, 1.0].
        1.0 = completely fresh (no overlap with recent outfits)
        0.0 = exact repeat of a very recently worn outfit
    """
    if not recent_outfit_items:
        return 1.0  # no history → full novelty

    candidate_set: Set[str] = set(candidate_item_ids)

    weighted_penalties = []
    for past in recent_outfit_items:
        past_ids = set(past.get("item_ids", []))
        jac = _jaccard(candidate_set, past_ids)
        if jac == 0.0:
            continue
        worn_date = past.get("worn_date")
        if isinstance(worn_date, str):
            try:
                worn_date = date.fromisoformat(worn_date)
            except ValueError:
                worn_date = None
        weight = _recency_weight(worn_date)
        weighted_penalties.append(jac * weight)

    if not weighted_penalties:
        return 1.0

    # Penalty = max weighted Jaccard (worst-case repetition)
    max_penalty = max(weighted_penalties)
    score = 1.0 - max_penalty
    return round(max(0.0, score), 4)
