"""
Color Harmony Score Module — Phase 8.

Scores color compatibility across items in a candidate outfit.

Algorithm: rule-based color theory using HSL distance and named palette relationships.

Harmony types (stored as data):
  - Monochromatic: same hue, different lightness/saturation → high score
  - Analogous: adjacent hues (±30°) → high score
  - Complementary: opposite hues (~180°) → medium-high
  - Triadic: 3 hues ~120° apart → medium
  - Neutral + anything: always compatible → high
  - Clash: hues within 30–60° that are NOT analogous (mid-saturation) → low

Named colors → approximate HSL stored as lookup table.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Named-color → HSL lookup (H in degrees 0–360, S and L in 0.0–1.0)
# ---------------------------------------------------------------------------

COLOR_HSL: Dict[str, Tuple[float, float, float]] = {
    # Neutrals (low saturation — compatible with everything)
    "white":        (0,   0.00, 1.00),
    "black":        (0,   0.00, 0.05),
    "gray":         (0,   0.00, 0.50),
    "grey":         (0,   0.00, 0.50),
    "beige":        (36,  0.33, 0.85),
    "ivory":        (60,  0.50, 0.94),
    "cream":        (45,  0.40, 0.93),
    "off-white":    (45,  0.20, 0.95),
    "charcoal":     (0,   0.00, 0.21),
    "nude":         (20,  0.35, 0.80),
    "tan":          (34,  0.44, 0.69),
    "taupe":        (33,  0.14, 0.59),
    # Earth tones
    "brown":        (25,  0.55, 0.35),
    "camel":        (33,  0.60, 0.60),
    "khaki":        (54,  0.44, 0.70),
    "olive":        (60,  0.50, 0.25),
    # Blues
    "navy":         (220, 0.80, 0.18),
    "blue":         (220, 0.75, 0.50),
    "light-blue":   (207, 0.70, 0.70),
    "royal-blue":   (225, 0.73, 0.43),
    "sky-blue":     (197, 0.72, 0.72),
    "teal":         (180, 0.60, 0.35),
    "turquoise":    (174, 0.72, 0.56),
    "denim":        (214, 0.45, 0.45),
    # Reds
    "red":          (0,   0.80, 0.50),
    "burgundy":     (345, 0.70, 0.25),
    "maroon":       (0,   0.70, 0.25),
    "coral":        (16,  0.78, 0.65),
    "salmon":       (6,   0.73, 0.71),
    "rose":         (347, 0.59, 0.78),
    # Greens
    "green":        (120, 0.61, 0.40),
    "forest-green": (120, 0.50, 0.25),
    "mint":         (152, 0.60, 0.80),
    "sage":         (80,  0.25, 0.55),
    "emerald":      (145, 0.63, 0.38),
    # Yellows / Oranges
    "yellow":       (60,  0.90, 0.55),
    "mustard":      (44,  0.80, 0.45),
    "orange":       (25,  0.90, 0.55),
    "peach":        (28,  0.88, 0.78),
    "gold":         (51,  0.90, 0.50),
    # Purples / Pinks
    "purple":       (270, 0.65, 0.40),
    "lavender":     (240, 0.50, 0.80),
    "lilac":        (279, 0.40, 0.78),
    "pink":         (340, 0.70, 0.75),
    "hot-pink":     (330, 0.90, 0.60),
    "magenta":      (300, 0.80, 0.50),
    # Metallics
    "silver":       (0,   0.05, 0.75),
    "gold-metallic":(51,  0.50, 0.60),
    "bronze":       (30,  0.50, 0.40),
}

# Neutrals by name — compatible with everything
NEUTRALS = {
    "white", "black", "gray", "grey", "beige", "ivory", "cream",
    "off-white", "charcoal", "nude", "tan", "taupe", "silver", "brown",
    "camel", "khaki", "olive",
}


def _hue_distance(h1: float, h2: float) -> float:
    """Circular hue distance in [0°, 180°]."""
    d = abs(h1 - h2) % 360
    return min(d, 360 - d)


def _color_to_hsl(color_name: Optional[str]) -> Optional[Tuple[float, float, float]]:
    """Look up HSL for a named color. Returns None if unknown."""
    if not color_name:
        return None
    return COLOR_HSL.get(color_name.lower().strip())


def _pair_score(name_a: Optional[str], name_b: Optional[str]) -> float:
    """
    Score a single color pair in [0.0, 1.0] using color theory rules.
    Returns 0.8 (safe default) when either color is unknown.
    """
    # Neutrals are compatible with anything
    if name_a in NEUTRALS or name_b in NEUTRALS:
        return 0.90

    hsl_a = _color_to_hsl(name_a)
    hsl_b = _color_to_hsl(name_b)

    if hsl_a is None or hsl_b is None:
        return 0.75  # unknown → mild uncertainty

    ha, sa, la = hsl_a
    hb, sb, lb = hsl_b

    # Low-saturation items → effectively neutral
    if sa < 0.15 or sb < 0.15:
        return 0.88

    hue_dist = _hue_distance(ha, hb)

    # Monochromatic (same hue ±15°)
    if hue_dist <= 15:
        return 0.92

    # Analogous (15°–45°)
    if hue_dist <= 45:
        return 0.85

    # Complementary (150°–180°)
    if hue_dist >= 150:
        return 0.78

    # Triadic (near 120°)
    if 100 <= hue_dist <= 140:
        return 0.72

    # Split-complementary (near 150°)
    if 130 <= hue_dist < 150:
        return 0.70

    # Square / tetradic mid-zone
    if 80 <= hue_dist < 100:
        return 0.65

    # Clash zone (45°–80° with high saturation on both sides)
    if sa > 0.50 and sb > 0.50:
        return 0.45

    return 0.60  # medium saturation clash — less bad


def calculate_color_score(colors: List[Optional[str]]) -> float:
    """
    Compute color harmony score for an outfit.

    Args:
        colors: List of color name strings from ClothingAttributes.color_primary
                for each item in the candidate outfit.

    Returns:
        Score in [0.0, 1.0] — average of all pairwise scores.
    """
    if not colors:
        return 0.75  # no data → neutral

    # Filter Nones
    valid = [c for c in colors if c]
    if len(valid) < 2:
        return 0.80  # single color → fine

    # Compute all pairwise scores
    pairs = []
    for i in range(len(valid)):
        for j in range(i + 1, len(valid)):
            pairs.append(_pair_score(valid[i], valid[j]))

    avg = sum(pairs) / len(pairs)
    return round(avg, 4)
