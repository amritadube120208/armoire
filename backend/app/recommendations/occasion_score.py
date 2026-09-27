"""
Occasion Score Module — Phase 8.

Scores how well an item's formality matches the target occasion's dress code.

Rules stored as data structures per Backend.md §4 constraint:
  - Each occasion maps to a formality band [min, max] on scale 0.0–1.0.
  - Items outside the band receive a graduated penalty.
  - "Overdressing" (item more formal than required) is penalised less
    than "underdressing" (more casual than required).
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple


# ---------------------------------------------------------------------------
# Formality scale (ordinal → numeric)
# ---------------------------------------------------------------------------

FORMALITY_SCALE: Dict[str, float] = {
    "casual":       0.1,
    "smart-casual": 0.4,
    "business":     0.6,
    "formal":       0.8,
    "black-tie":    1.0,
}


def formality_to_float(formality: Optional[str]) -> float:
    """Map a formality string to [0.0, 1.0]. Unknown → 0.3 neutral."""
    if not formality:
        return 0.3
    return FORMALITY_SCALE.get(formality.lower().replace(" ", "-"), 0.3)


# ---------------------------------------------------------------------------
# Occasion → acceptable formality band (min_inclusive, max_inclusive)
# Stored as data, not hardcoded conditions in logic.
# ---------------------------------------------------------------------------

OCCASION_BANDS: Dict[str, Dict] = {
    # label         min    max   over_dress_penalty  under_dress_penalty
    "casual":       {"min": 0.0, "max": 0.5,  "over": 0.15, "under": 0.50},
    "brunch":       {"min": 0.1, "max": 0.55, "over": 0.10, "under": 0.45},
    "work":         {"min": 0.3, "max": 0.75, "over": 0.10, "under": 0.50},
    "business":     {"min": 0.5, "max": 0.85, "over": 0.08, "under": 0.55},
    "date":         {"min": 0.3, "max": 0.80, "over": 0.05, "under": 0.40},
    "party":        {"min": 0.3, "max": 0.90, "over": 0.05, "under": 0.35},
    "wedding":      {"min": 0.6, "max": 1.00, "over": 0.00, "under": 0.60},
    "formal":       {"min": 0.7, "max": 1.00, "over": 0.00, "under": 0.65},
    "black-tie":    {"min": 0.9, "max": 1.00, "over": 0.00, "under": 0.70},
    "gym":          {"min": 0.0, "max": 0.25, "over": 0.30, "under": 0.00},
    "beach":        {"min": 0.0, "max": 0.20, "over": 0.30, "under": 0.00},
    "outdoor":      {"min": 0.0, "max": 0.45, "over": 0.15, "under": 0.30},
    "travel":       {"min": 0.0, "max": 0.50, "over": 0.10, "under": 0.35},
}

_DEFAULT_BAND = {"min": 0.0, "max": 1.0, "over": 0.10, "under": 0.10}


def _get_band(occasion: str) -> Dict:
    return OCCASION_BANDS.get(occasion.lower().strip(), _DEFAULT_BAND)


def calculate_occasion_score(
    item_formality: Optional[str],
    occasion: Optional[str],
    item_formality_confidence: float = 0.8,
) -> float:
    """
    Compute occasion fitness score in [0.0, 1.0].

    Args:
        item_formality:   Formality string from ClothingAttributes.
        occasion:         Target occasion string (from recommendation request).
        item_formality_confidence: Classifier confidence — lower confidence widens
                          the effective band so uncertain classifications don't get
                          unjustly penalised.

    Returns:
        Score in [0.0, 1.0].
    """
    formality_val = formality_to_float(item_formality)
    band = _get_band(occasion or "casual")

    band_min = band["min"]
    band_max = band["max"]

    # Widen band by (1 - confidence) * 0.2 to handle classifier uncertainty
    uncertainty_margin = (1.0 - item_formality_confidence) * 0.2
    effective_min = max(0.0, band_min - uncertainty_margin)
    effective_max = min(1.0, band_max + uncertainty_margin)

    if effective_min <= formality_val <= effective_max:
        return 1.0

    if formality_val > effective_max:
        # Over-dressed: lighter penalty
        excess = formality_val - effective_max
        penalty = band["over"] * excess * 5.0  # scale: 0.2 excess → full penalty
        return max(0.0, round(1.0 - penalty, 4))
    else:
        # Under-dressed: heavier penalty
        deficit = effective_min - formality_val
        penalty = band["under"] * deficit * 5.0
        return max(0.0, round(1.0 - penalty, 4))
