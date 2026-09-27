import uuid
from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.outfit import OutfitResponse


class ScoreBreakdown(BaseModel):
    weather_score: float = Field(..., ge=0.0, le=1.0)
    occasion_score: float = Field(..., ge=0.0, le=1.0)
    color_score: float = Field(..., ge=0.0, le=1.0)
    style_score: float = Field(..., ge=0.0, le=1.0)
    personalization_score: float = Field(..., ge=0.0, le=1.0)
    diversity_score: float = Field(..., ge=0.0, le=1.0)
    final_score: float = Field(..., ge=0.0, le=1.0)
    reasoning_summary: Optional[str] = None


class RecommendationCandidateResponse(BaseModel):
    id: uuid.UUID
    outfit: OutfitResponse
    scores: ScoreBreakdown


class RecommendationListResponse(BaseModel):
    recommendations: List[RecommendationCandidateResponse]
    occasion: str
    weather_condition: Optional[str] = None
    temperature_c: Optional[float] = None
