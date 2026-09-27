"""
Clothing router module matching Backend.md §2 folder structure.
Shares routes with wardrobe.py to provide flexible API routing for clothing items.
"""
from fastapi import APIRouter
from app.api.v1.wardrobe import router as wardrobe_router

router = APIRouter(prefix="/clothing", tags=["Clothing"])

# Mount wardrobe router items under clothing prefix as well for developer convenience
# while strictly preserving /wardrobe/items per Backend.md §4
router.include_router(wardrobe_router, prefix="")
