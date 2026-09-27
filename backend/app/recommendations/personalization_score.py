"""
Personalization Score Module — Phase 8.

Scores how well a candidate outfit aligns with the user's inferred preferences,
derived from their feedback history and stored UserPreference affinity maps.

Signals used:
  1. color_affinity:    dict {color: weight} from UserPreference (EMA-updated)
  2. category_affinity: dict {category: weight} from UserPreference
  3. style_tags:        list of preferred style labels
  4. wear_count:        items the user wears often → implicit preference
  5. last_worn_date:    recency bias — recently worn = still relevant taste
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Dict, List, Optional


def _days_since(last_worn: Optional[date]) -> Optional[int]:
    if last_worn is None:
        return None
    today = datetime.now(timezone.utc).date()
    return (today - last_worn).days


def _color_affinity_score(
    item_colors: List[Optional[str]],
    color_affinity: Dict[str, float],
) -> float:
    """
    Score based on user's colour affinity map.
    Each colour in the outfit that appears in affinity → adds weighted contribution.
    Missing colours → neutral 0.5.
    """
    if not color_affinity:
        return 0.65  # no preference data yet

    scores = []
    for color in item_colors:
        if not color:
            scores.append(0.60)
            continue
        c = color.lower().strip()
        if c in color_affinity:
            # Affinity stored as raw vote count or EMA weight — normalise to [0,1]
            raw = color_affinity[c]
            # Clamp and scale: assume max meaningful value is 10.0
            scores.append(min(1.0, raw / 10.0))
        else:
            scores.append(0.55)  # unknown colour — mild neutral

    if not scores:
        return 0.65
    return round(sum(scores) / len(scores), 4)


def _category_affinity_score(
    item_categories: List[Optional[str]],
    category_affinity: Dict[str, float],
) -> float:
    """Score based on user's category affinity map."""
    if not category_affinity:
        return 0.65

    scores = []
    for cat in item_categories:
        if not cat:
            scores.append(0.60)
            continue
        c = cat.lower().strip()
        raw = category_affinity.get(c, 0)
        scores.append(min(1.0, raw / 10.0) if raw > 0 else 0.55)

    if not scores:
        return 0.65
    return round(sum(scores) / len(scores), 4)


def _wear_count_score(wear_counts: List[int]) -> float:
    """
    Items the user actually wears often score higher.
    Scale: 0 wears → 0.50 (new/unknown), 5+ wears → 0.90 (proven favourite).
    """
    if not wear_counts:
        return 0.60
    avg = sum(wear_counts) / len(wear_counts)
    # Logarithmic: log(1 + avg) / log(6) maps [0,5+] → [0,1]
    import math
    score = math.log(1 + avg) / math.log(6)
    # Rescale to [0.50, 0.92]
    return round(0.50 + 0.42 * min(1.0, score), 4)


def calculate_personalization_score(
    item_colors: Optional[List[Optional[str]]] = None,
    item_categories: Optional[List[Optional[str]]] = None,
    wear_counts: Optional[List[int]] = None,
    color_affinity: Optional[Dict[str, float]] = None,
    category_affinity: Optional[Dict[str, float]] = None,
) -> float:
    """
    Compute personalization score in [0.0, 1.0].

    Args:
        item_colors:       Primary colors of outfit items.
        item_categories:   Categories of outfit items.
        wear_counts:       wear_count values for each item.
        color_affinity:    User's colour affinity map from UserPreference.
        category_affinity: User's category affinity map from UserPreference.

    Returns:
        Weighted average of color, category, and wear-frequency signals.
    """
    color_s = _color_affinity_score(
        item_colors or [], color_affinity or {}
    )
    category_s = _category_affinity_score(
        item_categories or [], category_affinity or {}
    )
    wear_s = _wear_count_score(wear_counts or [])

    # Weights: color 40%, category 35%, wear frequency 25%
    score = 0.40 * color_s + 0.35 * category_s + 0.25 * wear_s
    return round(score, 4)
