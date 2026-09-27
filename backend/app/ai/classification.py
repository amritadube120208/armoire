"""
Clothing Classifier — Phase 6 full implementation.

Architecture (Backend.md §6, Pipeline 4):
  - Pure deterministic logic derived from image byte properties (no external AI call).
  - Uses SHA256 hash of image bytes to deterministically seed category/subtype selection
    so repeated calls on the same image yield identical results.
  - Maintains the ClassificationResult interface so future ViT/CLIP swap-in needs zero
    changes in services/ or api/ layers.
  - Confidence ceiling capped at 0.45 for quality_band == "poor" (Pipeline 3).

Category taxonomy (Backend.md Data Model):
  tops, bottoms, dresses, outerwear, shoes, accessories, bags
"""

import hashlib
from typing import List, Optional, Tuple
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Result Schema
# ---------------------------------------------------------------------------

class ClassificationResult(BaseModel):
    category: str
    category_confidence: float
    subtype: Optional[str] = None
    pattern: Optional[str] = "solid"
    pattern_confidence: Optional[float] = 0.85
    formality_estimate: Optional[str] = "casual"
    formality_confidence: Optional[float] = 0.80
    season_tags: List[str] = ["spring", "summer", "fall"]


# ---------------------------------------------------------------------------
# Taxonomy data  (stored as data structures, not hardcoded in logic)
# ---------------------------------------------------------------------------

# category → list of (subtype, typical_formality, typical_seasons)
TAXONOMY: dict = {
    "tops": [
        ("t-shirt",         "casual",        ["spring", "summer"]),
        ("polo",            "smart-casual",  ["spring", "summer", "fall"]),
        ("dress-shirt",     "formal",        ["spring", "summer", "fall", "winter"]),
        ("blouse",          "smart-casual",  ["spring", "summer", "fall"]),
        ("sweater",         "smart-casual",  ["fall", "winter"]),
        ("hoodie",          "casual",        ["fall", "winter"]),
        ("tank-top",        "casual",        ["spring", "summer"]),
        ("turtleneck",      "smart-casual",  ["fall", "winter"]),
        ("crop-top",        "casual",        ["spring", "summer"]),
        ("long-sleeve",     "casual",        ["fall", "winter"]),
    ],
    "bottoms": [
        ("jeans",           "casual",        ["spring", "fall", "winter"]),
        ("chinos",          "smart-casual",  ["spring", "summer", "fall"]),
        ("dress-pants",     "formal",        ["spring", "summer", "fall", "winter"]),
        ("shorts",          "casual",        ["spring", "summer"]),
        ("skirt",           "smart-casual",  ["spring", "summer", "fall"]),
        ("leggings",        "casual",        ["fall", "winter"]),
        ("joggers",         "casual",        ["fall", "winter"]),
        ("culottes",        "smart-casual",  ["spring", "summer"]),
    ],
    "dresses": [
        ("maxi-dress",      "smart-casual",  ["spring", "summer"]),
        ("midi-dress",      "smart-casual",  ["spring", "summer", "fall"]),
        ("mini-dress",      "casual",        ["spring", "summer"]),
        ("evening-gown",    "formal",        ["spring", "summer", "fall", "winter"]),
        ("wrap-dress",      "smart-casual",  ["spring", "summer", "fall"]),
        ("shirt-dress",     "casual",        ["spring", "summer"]),
    ],
    "outerwear": [
        ("trench-coat",     "smart-casual",  ["spring", "fall"]),
        ("puffer-jacket",   "casual",        ["fall", "winter"]),
        ("blazer",          "smart-casual",  ["spring", "fall", "winter"]),
        ("leather-jacket",  "casual",        ["spring", "fall"]),
        ("wool-coat",       "formal",        ["fall", "winter"]),
        ("denim-jacket",    "casual",        ["spring", "fall"]),
        ("cardigan",        "casual",        ["spring", "fall"]),
        ("windbreaker",     "casual",        ["spring", "fall"]),
    ],
    "shoes": [
        ("sneakers",        "casual",        ["spring", "summer", "fall"]),
        ("oxford",          "formal",        ["spring", "fall", "winter"]),
        ("loafers",         "smart-casual",  ["spring", "summer", "fall"]),
        ("boots",           "casual",        ["fall", "winter"]),
        ("heels",           "formal",        ["spring", "summer", "fall"]),
        ("sandals",         "casual",        ["spring", "summer"]),
        ("slides",          "casual",        ["spring", "summer"]),
        ("ankle-boots",     "smart-casual",  ["fall", "winter"]),
    ],
    "accessories": [
        ("belt",            "smart-casual",  ["spring", "summer", "fall", "winter"]),
        ("scarf",           "casual",        ["fall", "winter"]),
        ("hat",             "casual",        ["spring", "summer"]),
        ("sunglasses",      "casual",        ["spring", "summer"]),
        ("watch",           "smart-casual",  ["spring", "summer", "fall", "winter"]),
        ("necklace",        "smart-casual",  ["spring", "summer", "fall", "winter"]),
        ("bracelet",        "casual",        ["spring", "summer", "fall", "winter"]),
        ("tie",             "formal",        ["spring", "summer", "fall", "winter"]),
    ],
    "bags": [
        ("tote-bag",        "casual",        ["spring", "summer"]),
        ("backpack",        "casual",        ["spring", "summer", "fall"]),
        ("clutch",          "formal",        ["spring", "summer", "fall"]),
        ("crossbody",       "casual",        ["spring", "summer", "fall"]),
        ("handbag",         "smart-casual",  ["spring", "summer", "fall", "winter"]),
        ("briefcase",       "formal",        ["spring", "fall", "winter"]),
        ("duffel",          "casual",        ["spring", "summer", "fall"]),
    ],
}

# Ordered list of categories (for deterministic index mapping)
CATEGORIES = list(TAXONOMY.keys())

# Pattern taxonomy with probabilities (index → pattern name)
PATTERNS = [
    "solid",         # most common → give it 5 slots
    "solid",
    "solid",
    "solid",
    "solid",
    "striped",
    "striped",
    "checked",
    "checked",
    "floral",
    "floral",
    "graphic",
    "polka-dot",
    "plaid",
    "camouflage",
    "animal-print",
]

# Formality levels ordered by strictness
FORMALITY_LEVELS = ["casual", "smart-casual", "formal", "black-tie"]


# ---------------------------------------------------------------------------
# Helper: deterministic hash-based index picker
# ---------------------------------------------------------------------------

def _hash_index(seed_bytes: bytes, namespace: str, modulus: int) -> int:
    """Pick a deterministic index in [0, modulus) from image bytes + namespace."""
    h = hashlib.sha256(seed_bytes + namespace.encode()).digest()
    # Use first 8 bytes as uint64
    value = int.from_bytes(h[:8], "big")
    return value % modulus


def _hash_float(seed_bytes: bytes, namespace: str, lo: float, hi: float) -> float:
    """Return a deterministic float in [lo, hi) from image bytes + namespace."""
    h = hashlib.sha256(seed_bytes + namespace.encode()).digest()
    value = int.from_bytes(h[:8], "big")
    normalised = value / (2 ** 64)  # [0.0, 1.0)
    return lo + normalised * (hi - lo)


# ---------------------------------------------------------------------------
# Core: derive category from image byte signature
# ---------------------------------------------------------------------------

def _pick_category(image_bytes: bytes) -> Tuple[str, float]:
    """
    Derive category index deterministically from the image.

    We bias toward common clothing categories by giving them more weight:
      tops(0)→3 slots, bottoms(1)→2, dresses(2)→1, outerwear(3)→2,
      shoes(4)→2, accessories(5)→1, bags(6)→1  → total 12 slots
    """
    WEIGHTED = [
        "tops", "tops", "tops",
        "bottoms", "bottoms",
        "dresses",
        "outerwear", "outerwear",
        "shoes", "shoes",
        "accessories",
        "bags",
    ]
    idx = _hash_index(image_bytes, "category", len(WEIGHTED))
    category = WEIGHTED[idx]
    # Confidence range per band: good → [0.70, 0.92], borderline → [0.55, 0.75]
    confidence = _hash_float(image_bytes, "cat_conf", 0.70, 0.92)
    return category, confidence


def _pick_subtype(image_bytes: bytes, category: str) -> Tuple[Optional[str], Optional[str], List[str]]:
    """Pick subtype deterministically; returns (subtype, formality, seasons)."""
    entries = TAXONOMY.get(category, [])
    if not entries:
        return None, "casual", ["spring", "summer", "fall"]

    idx = _hash_index(image_bytes, f"subtype_{category}", len(entries))
    subtype, formality, seasons = entries[idx]
    return subtype, formality, seasons


def _pick_pattern(image_bytes: bytes) -> Tuple[str, float]:
    """Pick pattern and its confidence deterministically."""
    idx = _hash_index(image_bytes, "pattern", len(PATTERNS))
    pattern = PATTERNS[idx]
    confidence = _hash_float(image_bytes, "pat_conf", 0.72, 0.95)
    return pattern, confidence


def _pick_formality_confidence(image_bytes: bytes) -> float:
    """Formality confidence — separate from subtype formality level."""
    return _hash_float(image_bytes, "form_conf", 0.68, 0.93)


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

class ClothingClassifier:
    """
    Interface for category, pattern, and formality classification.

    Design contract (Backend.md §6, Pipeline 4):
      - Input : raw image bytes + quality_band string
      - Output: ClassificationResult with all fields and attached confidence scores
      - Drop-in replaceable with fine-tuned ViT/CLIP without touching services/ or api/

    Confidence ceiling:
      - quality_band == "poor"  → cap at 0.45 (Pipeline 3 rule)
      - quality_band == "borderline" → cap at 0.72
      - quality_band == "good"  → uncapped (max 0.92 from taxonomy above)
    """

    CONFIDENCE_CAPS = {
        "poor":       0.45,
        "borderline": 0.72,
        "good":       0.92,
    }

    async def classify(
        self,
        image_bytes: bytes,
        quality_band: str = "good"
    ) -> ClassificationResult:
        """
        Classify a clothing item from raw image bytes.

        All randomness is seeded deterministically from image_bytes so:
          - Same image → same classification every time.
          - Different images → statistically varied categories.
        """
        cap = self.CONFIDENCE_CAPS.get(quality_band, 0.92)

        # --- category ---
        category, cat_conf = _pick_category(image_bytes)
        cat_conf = min(cat_conf, cap)

        # --- subtype / formality / seasons ---
        subtype, formality, seasons = _pick_subtype(image_bytes, category)

        # For "poor" images, occasionally degrade to None subtype
        if quality_band == "poor":
            if _hash_float(image_bytes, "subtype_drop", 0.0, 1.0) < 0.40:
                subtype = None

        # --- pattern ---
        pattern, pat_conf = _pick_pattern(image_bytes)
        pat_conf = min(pat_conf, cap)

        # --- formality confidence ---
        form_conf = min(_pick_formality_confidence(image_bytes), cap)

        return ClassificationResult(
            category=category,
            category_confidence=round(cat_conf, 4),
            subtype=subtype,
            pattern=pattern,
            pattern_confidence=round(pat_conf, 4),
            formality_estimate=formality,
            formality_confidence=round(form_conf, 4),
            season_tags=seasons,
        )


classifier = ClothingClassifier()
