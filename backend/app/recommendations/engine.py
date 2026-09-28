"""
Recommendation Engine — Phase 8 full implementation.

Architecture (Backend.md Pipeline 7):
  Final Score = 0.25*Weather + 0.25*Occasion + 0.15*Color + 0.15*Style
              + 0.15*Personalization + 0.05*Diversity

Candidate Generation Strategy:
  1. Bucket wardrobe items by category.
  2. Apply hard filters (weather-excluded subtypes, status != "ready").
  3. Generate outfit skeletons:
       - Normal:  top + bottom + [outerwear optional] + [shoes optional]
       - Dress:   dress + [outerwear optional] + [shoes optional]
  4. Score each skeleton with all 6 modules.
  5. Persist top-N to Recommendation table and return ranked list.

Multi-tenant isolation: all DB queries pass user_id (Backend.md §10).
"""

from __future__ import annotations

import itertools
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clothing import ClothingItem
from app.models.weather_snapshot import Recommendation
from app.repositories.clothing_repo import ClothingRepository
from app.repositories.outfit_repo import OutfitRepository
from app.recommendations.weather_score import calculate_weather_score, infer_warmth
from app.recommendations.occasion_score import calculate_occasion_score
from app.recommendations.color_score import calculate_color_score
from app.recommendations.style_score import calculate_style_score
from app.recommendations.personalization_score import calculate_personalization_score
from app.recommendations.diversity_score import calculate_diversity_score

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS = {
    "weather":        0.25,
    "occasion":       0.25,
    "color":          0.15,
    "style":          0.15,
    "personalization": 0.15,
    "diversity":      0.05,
}

TOP_N_CANDIDATES = 8   # max recommendations returned per call
MAX_COMBOS_PER_TYPE = 50  # limit combinatorial explosion

# Categories treated as optional layers (outerwear, shoes)
OPTIONAL_CATEGORIES = {"outerwear", "shoes", "accessories", "bags"}
TOP_CATEGORIES = {"tops"}
BOTTOM_CATEGORIES = {"bottoms"}
DRESS_CATEGORIES = {"dresses"}
OUTERWEAR_CATEGORIES = {"outerwear"}
SHOE_CATEGORIES = {"shoes"}


# ---------------------------------------------------------------------------
# Data classes (no ORM dependency here)
# ---------------------------------------------------------------------------

class OutfitCandidate:
    """In-memory representation of a candidate outfit before DB persistence."""

    def __init__(
        self,
        items: List[ClothingItem],
        scores: Dict[str, float],
        final_score: float,
        occasion: str,
        weather_snapshot_id: Optional[str] = None,
    ):
        self.id = str(uuid.uuid4())
        self.items = items
        self.scores = scores
        self.final_score = final_score
        self.occasion = occasion
        self.weather_snapshot_id = weather_snapshot_id

    def to_dict(self) -> Dict[str, Any]:
        outfit_id = getattr(self, "db_outfit_id", self.id)
        rec_id = getattr(self, "db_rec_id", None)
        return {
            "id": outfit_id,
            "outfit_id": outfit_id,
            "recommendation_id": rec_id,
            "items": [
                {
                    "id": str(item.id),
                    "category": item.category,
                    "subtype": item.subtype,
                    "color": item.attributes.color_primary if item.attributes else None,
                    "thumbnail_url": item.image.thumbnail_url if item.image else None,
                }
                for item in self.items
            ],
            "score_breakdown": {k: round(v, 4) for k, v in self.scores.items()},
            "final_score": round(self.final_score, 4),
            "occasion": self.occasion,
        }


def compute_outfit_score(
    scores: Dict[str, float],
    weights: Optional[Dict[str, float]] = None,
) -> float:
    """Weighted sum of all dimension scores → final score in [0.0, 1.0]."""
    w = weights or DEFAULT_WEIGHTS
    total = (
        w["weather"]         * scores.get("weather", scores.get("weather_score", 0.0)) +
        w["occasion"]        * scores.get("occasion", scores.get("occasion_score", 0.0)) +
        w["color"]           * scores.get("color", scores.get("color_score", 0.0)) +
        w["style"]           * scores.get("style", scores.get("style_score", 0.0)) +
        w["personalization"] * scores.get("personalization", scores.get("personalization_score", 0.0)) +
        w["diversity"]       * scores.get("diversity", scores.get("diversity_score", 0.0))
    )
    return round(total, 4)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class RecommendationEngine:
    """
    Stateless scoring engine — all async DB access is done in generate().
    """

    DEFAULT_WEIGHTS = DEFAULT_WEIGHTS

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or DEFAULT_WEIGHTS

    def compute_outfit_score(
        self,
        scores: Dict[str, float],
        weights: Optional[Dict[str, float]] = None,
    ) -> float:
        return compute_outfit_score(scores, weights or self.weights)

    def _score_candidate(
        self,
        items: List[ClothingItem],
        requirement_band: Dict[str, Any],
        occasion: str,
        color_affinity: Dict[str, float],
        category_affinity: Dict[str, float],
        recent_outfit_items: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        """Compute all 6 dimension scores for a candidate outfit."""
        target_warmth = requirement_band.get("warmth_level", 0.35)
        excluded = requirement_band.get("excluded_subtypes", [])

        # --- Weather ---
        weather_scores = []
        has_outerwear = any(item.category == "outerwear" for item in items)
        required_layers = requirement_band.get("required_layers", [])

        for item in items:
            subtype = item.subtype
            stored_warmth = None  # no warmth_rating column yet → infer
            warmth = infer_warmth(item.category, subtype)
            weather_scores.append(
                calculate_weather_score(
                    item_warmth=warmth,
                    target_warmth=target_warmth,
                    item_subtype=subtype,
                    excluded_subtypes=excluded,
                )
            )

        # Layer appropriateness modifier
        if target_warmth <= 0.20 and has_outerwear:
            # Penalize unnecessary heavy jackets in hot weather
            weather_scores.append(0.10)
        elif target_warmth >= 0.65 and "outerwear" in required_layers:
            # Reward coat/outerwear presence in freezing/cold weather
            if has_outerwear:
                weather_scores.append(0.95)
            else:
                weather_scores.append(0.30)

        weather_s = sum(weather_scores) / len(weather_scores) if weather_scores else 0.75

        # --- Occasion ---
        occ_scores = []
        for item in items:
            formality = item.attributes.formality_estimate if item.attributes else None
            conf = item.attributes.formality_confidence if item.attributes else 0.70
            occ_scores.append(
                calculate_occasion_score(
                    item_formality=formality,
                    occasion=occasion,
                    item_formality_confidence=conf or 0.70,
                )
            )
        occasion_s = sum(occ_scores) / len(occ_scores) if occ_scores else 0.75

        # --- Color ---
        colors = [
            (item.attributes.color_primary if item.attributes else None)
            for item in items
        ]
        color_s = calculate_color_score(colors)

        # --- Style ---
        embeddings = [
            (item.attributes.embedding if item.attributes else None)
            for item in items
        ]
        patterns = [
            (item.attributes.pattern if item.attributes else None)
            for item in items
        ]
        style_s = calculate_style_score(embeddings=embeddings, patterns=patterns)

        # --- Personalization ---
        item_cats = [item.category for item in items]
        wear_counts = [item.wear_count for item in items]
        personalization_s = calculate_personalization_score(
            item_colors=colors,
            item_categories=item_cats,
            wear_counts=wear_counts,
            color_affinity=color_affinity,
            category_affinity=category_affinity,
        )

        # --- Diversity ---
        candidate_ids = [str(item.id) for item in items]
        diversity_s = calculate_diversity_score(
            candidate_item_ids=candidate_ids,
            recent_outfit_items=recent_outfit_items,
        )

        return {
            "weather":          round(weather_s, 4),
            "occasion":         round(occasion_s, 4),
            "color":            round(color_s, 4),
            "style":            round(style_s, 4),
            "personalization":  round(personalization_s, 4),
            "diversity":        round(diversity_s, 4),
        }

    def _generate_skeletons(
        self,
        by_category: Dict[str, List[ClothingItem]],
        requirement_band: Optional[Dict[str, Any]] = None,
    ) -> List[List[ClothingItem]]:
        """
        Generate candidate outfit combinations.

        Outfit types:
          A: top + bottom (+ optional outerwear) (+ optional shoes)
          B: dress (+ optional outerwear) (+ optional shoes)
        """
        skeletons: List[List[ClothingItem]] = []
        tops = by_category.get("tops", [])
        bottoms = by_category.get("bottoms", [])
        dresses = by_category.get("dresses", [])
        raw_outerwear = by_category.get("outerwear", [])
        shoes = by_category.get("shoes", [None])

        target_warmth = (requirement_band or {}).get("warmth_level", 0.35)

        # Adjust outerwear consideration according to weather temperature band
        if target_warmth <= 0.20:
            # Hot weather: skip heavy outerwear entirely
            outerwear = [None]
        elif target_warmth >= 0.60:
            # Cold weather: prioritize outerwear combinations
            outerwear = raw_outerwear + [None] if raw_outerwear else [None]
        else:
            outerwear = [None] + raw_outerwear if raw_outerwear else [None]

        if not shoes:
            shoes = [None]
        else:
            shoes = [None] + shoes

        count = 0
        # Type A: top + bottom
        for top, bottom, outer, shoe in itertools.product(tops, bottoms, outerwear, shoes):
            combo = [top, bottom]
            if outer:
                combo.append(outer)
            if shoe:
                combo.append(shoe)
            skeletons.append(combo)
            count += 1
            if count >= MAX_COMBOS_PER_TYPE:
                break

        count = 0
        # Type B: dress
        for dress, outer, shoe in itertools.product(dresses, outerwear, shoes):
            combo = [dress]
            if outer:
                combo.append(outer)
            if shoe:
                combo.append(shoe)
            skeletons.append(combo)
            count += 1
            if count >= MAX_COMBOS_PER_TYPE:
                break

        return skeletons

    async def generate(
        self,
        db: AsyncSession,
        user_id: str,
        occasion: str = "casual",
        requirement_band: Optional[Dict[str, Any]] = None,
        color_affinity: Optional[Dict[str, float]] = None,
        category_affinity: Optional[Dict[str, float]] = None,
        recent_outfit_items: Optional[List[Dict[str, Any]]] = None,
        weather_snapshot_id: Optional[str] = None,
    ) -> List[OutfitCandidate]:
        """
        Full candidate generation + scoring pipeline.

        Args:
            db:                  Async DB session.
            user_id:             Authenticated user's UUID string.
            occasion:            Target occasion label.
            requirement_band:    From WeatherService — warmth level + exclusions.
            color_affinity:      From UserPreference.color_affinity.
            category_affinity:   From UserPreference.category_affinity.
            recent_outfit_items: Recent worn outfits for diversity scoring.
            weather_snapshot_id: Optional FK to WeatherSnapshot row.

        Returns:
            Top-N ranked OutfitCandidate objects.
        """
        uid = uuid.UUID(user_id)
        repo = ClothingRepository(db)

        # 1. Fetch all ready wardrobe items for this user
        all_items, _ = await repo.list_items(
            user_id=uid,
            status="ready",
            limit=200,
        )

        if not all_items:
            return []

        # 2. Hard filter — weather-excluded subtypes
        excluded_subtypes = (requirement_band or {}).get("excluded_subtypes", [])
        filtered = [
            item for item in all_items
            if not (item.subtype and item.subtype in excluded_subtypes)
        ]

        if not filtered:
            filtered = all_items  # fallback: ignore hard filter if it empties the wardrobe

        # 3. Bucket by category
        by_category: Dict[str, List[ClothingItem]] = {}
        for item in filtered:
            cat = item.category or "tops"
            by_category.setdefault(cat, []).append(item)

        # 4. Generate outfit skeletons
        skeletons = self._generate_skeletons(by_category, requirement_band=requirement_band)
        if not skeletons:
            return []

        # 5. Score all skeletons
        band = requirement_band or {"warmth_level": 0.35, "excluded_subtypes": []}
        scored: List[Tuple[float, OutfitCandidate]] = []

        for combo in skeletons:
            scores = self._score_candidate(
                items=combo,
                requirement_band=band,
                occasion=occasion,
                color_affinity=color_affinity or {},
                category_affinity=category_affinity or {},
                recent_outfit_items=recent_outfit_items or [],
            )
            final = self.compute_outfit_score(scores)
            candidate = OutfitCandidate(
                items=combo,
                scores=scores,
                final_score=final,
                occasion=occasion,
                weather_snapshot_id=weather_snapshot_id,
            )
            scored.append((final, candidate))

        # 6. Sort descending; take top N
        scored.sort(key=lambda x: x[0], reverse=True)
        top_candidates = [c for _, c in scored[:TOP_N_CANDIDATES]]

        # 7. Persist to Recommendation table (best effort; don't fail if DB write fails)
        await self._persist_recommendations(db, top_candidates, weather_snapshot_id)

        return top_candidates

    async def _persist_recommendations(
        self,
        db: AsyncSession,
        candidates: List[OutfitCandidate],
        weather_snapshot_id: Optional[str],
    ) -> None:
        """
        Write Recommendation rows linking outfits to their score breakdown.
        Creates a new Outfit row per candidate (unnamed, system-generated).
        """
        outfit_repo = OutfitRepository(db)

        for candidate in candidates:
            try:
                # Create a system-generated outfit
                item_ids = [item.id for item in candidate.items]
                user_id = candidate.items[0].user_id  # all items belong to same user

                outfit = await outfit_repo.create_outfit(
                    user_id=user_id,
                    occasion=candidate.occasion,
                    clothing_item_ids=item_ids,
                    source="ai",
                )

                ws_id = (
                    uuid.UUID(weather_snapshot_id)
                    if weather_snapshot_id else None
                )

                rec = Recommendation(
                    outfit_id=outfit.id,
                    weather_snapshot_id=ws_id,
                    weather_score=candidate.scores.get("weather", 0.0),
                    occasion_score=candidate.scores.get("occasion", 0.0),
                    color_score=candidate.scores.get("color", 0.0),
                    style_score=candidate.scores.get("style", 0.0),
                    personalization_score=candidate.scores.get("personalization", 0.0),
                    diversity_score=candidate.scores.get("diversity", 0.0),
                    final_score=candidate.final_score,
                )
                db.add(rec)
                await db.flush()

                # Store the DB outfit id and recommendation id back on candidate
                candidate.db_outfit_id = str(outfit.id)
                candidate.db_rec_id = str(rec.id)

            except Exception as exc:
                logger.warning("Failed to persist recommendation: %s", exc)
                continue

        try:
            await db.commit()
        except Exception as exc:
            logger.warning("Recommendation DB commit failed: %s", exc)
            await db.rollback()


engine = RecommendationEngine()
