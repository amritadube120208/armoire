import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.clothing import ClothingItemResponse


class OutfitItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    clothing_item_id: uuid.UUID
    role: str
    clothing_item: Optional[ClothingItemResponse] = None


class OutfitCreateRequest(BaseModel):
    occasion: str
    clothing_item_ids: List[uuid.UUID]
    source: str = "manual"


class OutfitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    occasion: str
    source: str
    created_at: datetime
    items: List[OutfitItemResponse] = Field(default_factory=list)
