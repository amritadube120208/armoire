"""
Recommendations API — Phase 8 full implementation.

GET  /api/v1/recommendations          → generate + return ranked outfit list
GET  /api/v1/recommendations/{id}/explain → score breakdown for a specific recommendation
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.models.base import get_async_db
from app.models.user import User
from app.models.weather_snapshot import Recommendation
from app.recommendations.engine import RecommendationEngine
from app.services.weather_service import WeatherService

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("")
async def get_outfit_recommendations(
    occasion: Optional[str] = Query("casual", description="Target occasion"),
    lat: Optional[float] = Query(None, description="Latitude for weather lookup"),
    lon: Optional[float] = Query(None, description="Longitude for weather lookup"),
    override_weather: Optional[str] = Query(
        None,
        description="Force a weather condition label (e.g. 'hot', 'cold') for testing"
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Generate ranked outfit recommendations for the authenticated user.

    Process:
      1. Resolve weather (user location → WeatherService → requirement_band).
      2. Build user preference context from UserPreference row.
      3. Fetch recent outfit history for diversity scoring.
      4. Run RecommendationEngine.generate() → top-N candidates.
      5. Return ranked list with per-item metadata and score breakdowns.
    """
    # --- 1. Weather ---
    resolved_lat = lat
    resolved_lon = lon
    if resolved_lat is None or resolved_lon is None:
        loc = current_user.location or {}
        resolved_lat = float(loc.get("lat", 28.6))
        resolved_lon = float(loc.get("lon", 77.2))

    weather_svc = WeatherService(db)
    weather_data = await weather_svc.get_current_weather(
        lat=resolved_lat, lon=resolved_lon
    )
    requirement_band = weather_data.get("requirement_band", {})
    weather_snapshot_id = weather_data.get("snapshot_id")

    # Override warmth_level for testing (e.g. override_weather="freezing")
    if override_weather:
        from app.weather.client import TEMP_BANDS
        for band in TEMP_BANDS:
            if band["label"] == override_weather.lower():
                requirement_band = {
                    "temp_label": band["label"],
                    "warmth_level": band["warmth_level"],
                    "required_layers": band["required_layers"],
                    "excluded_subtypes": band["excluded_categories"],
                    "precipitation_label": "none",
                    "suggests_rain_gear": False,
                    "condition_family": "clear",
                }
                break

    # --- 2. User preference context ---
    pref = current_user.preference
    color_affinity = (pref.color_affinity or {}) if pref else {}
    category_affinity = (pref.category_affinity or {}) if pref else {}

    # --- 3. Recent outfit history (last 30 worn outfits) ---
    from app.models.outfit import Outfit, OutfitItem
    from sqlalchemy.orm import selectinload
    recent_stmt = (
        select(Outfit)
        .options(selectinload(Outfit.items))
        .where(Outfit.user_id == current_user.id)
        .order_by(Outfit.created_at.desc())
        .limit(30)
    )
    recent_result = await db.execute(recent_stmt)
    recent_outfits = recent_result.scalars().all()

    recent_outfit_items = [
        {
            "item_ids": [str(oi.clothing_item_id) for oi in outfit.items],
            "worn_date": None,  # Phase 9 will add last_worn_date to Outfit
        }
        for outfit in recent_outfits
    ]

    # --- 4. Run engine ---
    eng = RecommendationEngine()
    candidates = await eng.generate(
        db=db,
        user_id=str(current_user.id),
        occasion=occasion or "casual",
        requirement_band=requirement_band,
        color_affinity=color_affinity,
        category_affinity=category_affinity,
        recent_outfit_items=recent_outfit_items,
        weather_snapshot_id=weather_snapshot_id,
    )

    if not candidates:
        return {
            "occasion": occasion,
            "recommendations": [],
            "weather": {
                "source": weather_data.get("source", "unknown"),
                "temperature": weather_data.get("temperature"),
                "condition": weather_data.get("condition"),
                "requirement_band": requirement_band,
            },
            "notice": "No suitable outfits found. Add more items to your wardrobe.",
        }

    return {
        "occasion": occasion,
        "recommendations": [c.to_dict() for c in candidates],
        "weather": {
            "source": weather_data.get("source", "unknown"),
            "temperature": weather_data.get("temperature"),
            "condition": weather_data.get("condition"),
            "requirement_band": requirement_band,
        },
        "total": len(candidates),
    }


@router.get("/{recommendation_id}/explain")
async def explain_recommendation(
    recommendation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Return full explainable score breakdown for a persisted Recommendation row.
    Supports the 'Why this outfit?' feature per Backend.md §4.
    """
    stmt = (
        select(Recommendation)
        .where(
            (Recommendation.id == recommendation_id)
            | (Recommendation.outfit_id == recommendation_id)
        )
    )
    result = await db.execute(stmt)
    rec = result.scalars().first()

    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation not found.",
        )

    # Verify the outfit belongs to the current user
    from app.models.outfit import Outfit
    outfit_stmt = select(Outfit).where(
        Outfit.id == rec.outfit_id,
        Outfit.user_id == current_user.id,
    )
    outfit_result = await db.execute(outfit_stmt)
    outfit = outfit_result.scalars().first()

    if not outfit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this recommendation.",
        )

    # Build human-readable reasoning strings
    reasoning = _build_reasoning(rec)

    return {
        "recommendation_id": str(rec.id),
        "outfit_id": str(rec.outfit_id),
        "score_breakdown": {
            "weather_score":         round(rec.weather_score, 4),
            "occasion_score":        round(rec.occasion_score, 4),
            "color_score":           round(rec.color_score, 4),
            "style_score":           round(rec.style_score, 4),
            "personalization_score": round(rec.personalization_score, 4),
            "diversity_score":       round(rec.diversity_score, 4),
            "final_score":           round(rec.final_score, 4),
        },
        "weights": RecommendationEngine().weights,
        "reasoning": reasoning,
        "generated_at": rec.created_at.isoformat(),
    }


def _build_reasoning(rec: Recommendation) -> dict:
    """Convert numeric scores to human-readable explanations."""
    def _label(score: float) -> str:
        if score >= 0.85:
            return "excellent"
        if score >= 0.70:
            return "good"
        if score >= 0.55:
            return "fair"
        return "poor"

    return {
        "weather":         f"Weather compatibility is {_label(rec.weather_score)} ({rec.weather_score:.0%}). "
                           "Items are appropriate for the current temperature and conditions.",
        "occasion":        f"Occasion fit is {_label(rec.occasion_score)} ({rec.occasion_score:.0%}). "
                           "The formality level of items matches your chosen occasion.",
        "color":           f"Color harmony is {_label(rec.color_score)} ({rec.color_score:.0%}). "
                           "The palette of this outfit follows color theory principles.",
        "style":           f"Style cohesion is {_label(rec.style_score)} ({rec.style_score:.0%}). "
                           "Items share a consistent aesthetic and pattern language.",
        "personalization": f"Personalization match is {_label(rec.personalization_score)} ({rec.personalization_score:.0%}). "
                           "This outfit aligns with your past preferences and wear history.",
        "diversity":       f"Novelty score is {_label(rec.diversity_score)} ({rec.diversity_score:.0%}). "
                           "This outfit is fresh relative to what you have worn recently.",
    }
