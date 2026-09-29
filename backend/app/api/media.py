"""Serve private Vercel Blob images only to the wardrobe owner."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.image_processing.storage import storage
from app.models.base import get_async_db
from app.models.clothing import ClothingImage, ClothingItem
from app.repositories.session_repo import SessionRepository

router = APIRouter(tags=["Private Media"])


@router.get("/storage/{pathname:path}", include_in_schema=False)
async def serve_private_wardrobe_image(
    pathname: str,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    """Use the existing HttpOnly refresh session to authorize same-origin images."""
    token = request.cookies.get("refresh_token")
    payload = decode_token(token or "")
    if not payload or payload.get("type") != "refresh" or not payload.get("jti"):
        raise HTTPException(status_code=401, detail="A valid session is required to view this image.")
    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="A valid session is required to view this image.")

    user_session = await SessionRepository(db).get_by_jti(payload["jti"])
    if not user_session or user_session.user_id != user_id or user_session.is_revoked:
        raise HTTPException(status_code=401, detail="This image session has expired.")
    expiry = user_session.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry <= datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="This image session has expired.")

    storage_path = f"/storage/{pathname}"
    owned_image = await db.execute(
        select(ClothingImage.id)
        .join(ClothingItem, ClothingItem.id == ClothingImage.clothing_item_id)
        .where(
            ClothingItem.user_id == user_id,
            or_(
                ClothingImage.original_url == storage_path,
                ClothingImage.enhanced_url == storage_path,
                ClothingImage.thumbnail_url == storage_path,
            ),
        )
        .limit(1)
    )
    if not owned_image.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Image not found.")

    content = await storage.get_file(storage_path)
    if content is None:
        raise HTTPException(status_code=404, detail="Image not found.")
    media_type = (
        "image/svg+xml" if pathname.lower().endswith(".svg") else
        "image/webp" if pathname.lower().endswith(".webp") else
        "image/png" if pathname.lower().endswith(".png") else
        "image/jpeg"
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )
