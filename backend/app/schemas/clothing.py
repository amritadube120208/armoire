import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class QualityMetrics(BaseModel):
    blur_score: float = 0.0
    width: int = 0
    height: int = 0
    brightness: float = 0.0
    quality_band: str = "good"  # "good", "borderline", "poor"
    details: Optional[Dict[str, Any]] = None


class ClothingImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_url: str
    enhanced_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    quality_band: str
    enhancement_applied: bool
    quality_metrics: Dict[str, Any] = Field(default_factory=dict)


class ClothingAttributesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    color_primary: Optional[str] = None
    color_secondary: Optional[str] = None
    pattern: Optional[str] = None
    pattern_confidence: Optional[float] = None
    formality_estimate: Optional[str] = None
    formality_confidence: Optional[float] = None
    season_tags: List[str] = Field(default_factory=list)


class ClothingItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: Optional[str] = None
    subtype: Optional[str] = None
    status: str
    wear_count: int
    last_worn_date: Optional[date] = None
    created_at: datetime
    image: Optional[ClothingImageResponse] = None
    attributes: Optional[ClothingAttributesResponse] = None


class ClothingItemUpdate(BaseModel):
    category: Optional[str] = None
    subtype: Optional[str] = None
    color_primary: Optional[str] = None
    color_secondary: Optional[str] = None
    pattern: Optional[str] = None
    pattern_confidence: Optional[float] = None
    formality_estimate: Optional[str] = None
    formality_confidence: Optional[float] = None
    season_tags: Optional[List[str]] = None
    wear_count: Optional[int] = None
    last_worn_date: Optional[date] = None


class ClothingListResponse(BaseModel):
    items: List[ClothingItemResponse]
    total: int
    limit: int
    offset: int


class ImageEnhanceRequest(BaseModel):
    action: str = Field(..., description="'use_enhanced' or 'use_original' or 'retake'")


class ItemStatusResponse(BaseModel):
    id: uuid.UUID
    status: str
    quality_band: str
    needs_review: bool
    message: Optional[str] = None
