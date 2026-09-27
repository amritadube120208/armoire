"""
Weather Score Module — Phase 8.

Scores how well a clothing item (or outfit combination) matches the current
weather requirement band.

Algorithm:
  - Each item has a warmth_rating [0.0–1.0] stored in ClothingAttributes
    (or inferred from category/subtype if not explicitly set).
  - The requirement_band from WeatherService exposes warmth_level [0.0–1.0].
  - Score = 1.0 − |item_warmth − target_warmth| ^ 0.7  (curved penalty)
    so small mismatches are penalised less than large ones.
  - Hard exclusions (e.g. sandals in freezing weather) → score 0.0.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Warmth inference table — category/subtype → implied warmth_rating
# When ClothingAttributes.warmth_rating is NULL, we use this lookup.
# ---------------------------------------------------------------------------

SUBTYPE_WARMTH: Dict[str, float] = {
    # Tops
    "tank-top":      0.05,
    "crop-top":      0.05,
    "t-shirt":       0.15,
    "polo":          0.25,
    "dress-shirt":   0.25,
    "blouse":        0.20,
    "long-sleeve":   0.35,
    "turtleneck":    0.55,
    "sweater":       0.65,
    "hoodie":        0.60,
    # Bottoms
    "shorts":        0.05,
    "culottes":      0.15,
    "skirt":         0.15,
    "leggings":      0.35,
    "jeans":         0.40,
    "chinos":        0.40,
    "joggers":       0.45,
    "dress-pants":   0.40,
    # Dresses
    "mini-dress":    0.10,
    "shirt-dress":   0.15,
    "wrap-dress":    0.20,
    "midi-dress":    0.25,
    "maxi-dress":    0.30,
    "evening-gown":  0.25,
    # Outerwear
    "cardigan":      0.50,
    "denim-jacket":  0.55,
    "windbreaker":   0.60,
    "leather-jacket": 0.65,
    "trench-coat":   0.70,
    "blazer":        0.60,
    "puffer-jacket": 0.85,
    "wool-coat":     0.90,
    # Shoes
    "sandals":       0.00,
    "slides":        0.00,
    "sneakers":      0.30,
    "loafers":       0.35,
    "oxford":        0.35,
    "heels":         0.25,
    "ankle-boots":   0.55,
    "boots":         0.70,
    # Accessories/bags — neutral
    "belt":          0.30,
    "hat":           0.20,
    "scarf":         0.75,
    "sunglasses":    0.00,
    "watch":         0.30,
    "necklace":      0.25,
    "bracelet":      0.25,
    "tie":           0.30,
    "tote-bag":      0.20,
    "backpack":      0.20,
    "clutch":        0.20,
    "crossbody":     0.20,
    "handbag":       0.20,
    "briefcase":     0.20,
    "duffel":        0.20,
}

CATEGORY_WARMTH_DEFAULT: Dict[str, float] = {
    "tops":        0.25,
    "bottoms":     0.30,
    "dresses":     0.20,
    "outerwear":   0.70,
    "shoes":       0.30,
    "accessories": 0.25,
    "bags":        0.20,
}


def infer_warmth(
    category: Optional[str],
    subtype: Optional[str],
) -> float:
    """Return implied warmth_rating from taxonomy when stored value is absent."""
    if subtype and subtype in SUBTYPE_WARMTH:
        return SUBTYPE_WARMTH[subtype]
    if category and category in CATEGORY_WARMTH_DEFAULT:
        return CATEGORY_WARMTH_DEFAULT[category]
    return 0.30  # safe neutral


def calculate_weather_score(
    item_warmth: float,
    target_warmth: float,
    item_subtype: Optional[str] = None,
    excluded_subtypes: Optional[List[str]] = None,
) -> float:
    """
    Compute weather compatibility score in [0.0, 1.0].

    Args:
        item_warmth:      Warmth rating of the clothing item [0.0–1.0].
        target_warmth:    Required warmth level from the temperature band.
        item_subtype:     Subtype string (e.g. "sandals") for hard exclusion check.
        excluded_subtypes: List of subtypes banned in current weather.

    Returns:
        Score in [0.0, 1.0]. Hard-excluded items return 0.0.
    """
    # Hard exclusion check
    if item_subtype and excluded_subtypes:
        if item_subtype in excluded_subtypes:
            return 0.0

    delta = abs(item_warmth - target_warmth)
    # Curved penalty: 1 − delta^0.7
    # delta=0.0 → 1.0; delta=0.3 → ~0.54; delta=1.0 → 0.0
    score = 1.0 - (delta ** 0.7)
    return max(0.0, round(score, 4))
