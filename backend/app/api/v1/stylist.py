"""
AI Fashion Stylist Router.
Provides conversational outfit advice and style consulting powered by Groq.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_current_user
from app.models.base import get_async_db
from app.models.user import User
from app.repositories.clothing_repo import ClothingRepository
from app.services.stylist_service import stylist_service
from app.services.weather_service import WeatherService

router = APIRouter(prefix="/stylist", tags=["AI Stylist"])


class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message text")


class StylistChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="User's style question")
    history: Optional[List[ChatMessage]] = Field(None, description="Previous conversation messages")
    occasion: Optional[str] = Field(None, description="Current selected occasion")
    lat: Optional[float] = Field(None, description="Latitude for weather-aware styling")
    lon: Optional[float] = Field(None, description="Longitude for weather-aware styling")


class StylistChatResponse(BaseModel):
    reply: str
    suggestions: List[str]
    model: Optional[str] = None


@router.post("/chat", response_model=StylistChatResponse)
async def chat_with_stylist(
    req: StylistChatRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Interact with the Armoire AI Fashion Stylist.
    Provides tailored outfit ideas, color pairing, and wardrobe guidance.
    Strictly excludes study/academic content.
    """
    # 1. Fetch user wardrobe pieces summary if authenticated
    wardrobe_pieces: List[str] = []
    if current_user:
        try:
            repo = ClothingRepository(db)
            items, _ = await repo.list_items(user_id=current_user.id, limit=20)
            for it in items:
                name = it.subtype or it.category or "piece"
                color = it.color_primary or ""
                wardrobe_pieces.append(f"{color} {name}".strip())
        except Exception:
            pass

    # 2. Fetch current weather if coordinates available
    weather_info: Optional[Dict[str, Any]] = None
    if req.lat is not None and req.lon is not None:
        try:
            weather_svc = WeatherService(db)
            weather_info = await weather_svc.get_current_weather(lat=req.lat, lon=req.lon)
        except Exception:
            pass

    history_dicts = [m.model_dump() for m in req.history] if req.history else []

    res = await stylist_service.get_stylist_advice(
        prompt=req.message,
        history=history_dicts,
        occasion=req.occasion,
        weather=weather_info,
        wardrobe_pieces=wardrobe_pieces if wardrobe_pieces else None,
    )

    return StylistChatResponse(
        reply=res.get("reply", ""),
        suggestions=res.get("suggestions", []),
        model=res.get("model")
    )
