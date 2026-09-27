"""
Feedback API router — Phase 9.

POST /api/v1/feedback → record feedback and update personalization / wear tracking.
"""

from __future__ import annotations

import uuid
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.models.base import get_async_db
from app.models.user import User
from app.services.feedback_service import FeedbackService

router = APIRouter(prefix="/feedback", tags=["Feedback"])


class FeedbackPayload(BaseModel):
    outfit_id: uuid.UUID
    action: str = Field(
        ...,
        description="'like', 'dislike', 'save', 'wear', 'mark-as-worn', 'swap'"
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def record_feedback(
    payload: FeedbackPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Record user feedback action to drive the personalization loop.
    Triggers EMA updates on category & color affinities and tracks wear counts.
    """
    service = FeedbackService(db)
    try:
        result = await service.record_feedback(
            user_id=current_user.id,
            outfit_id=payload.outfit_id,
            action=payload.action,
        )
        return {
            "status": "success",
            "data": result,
        }
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower() or "belong" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=msg,
        )
