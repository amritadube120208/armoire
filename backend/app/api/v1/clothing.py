"""
Clothing router module matching Backend.md §2 folder structure.
Shares routes with wardrobe.py to provide flexible API routing for clothing items:
Exposes /clothing/items, /clothing/items/{id}, etc. in addition to /wardrobe/items.
"""
from fastapi import APIRouter
from app.api.v1.wardrobe import (
    upload_clothing_item,
    list_wardrobe_items,
    get_clothing_item,
    update_clothing_item,
    delete_clothing_item,
    get_clothing_item_status,
)

router = APIRouter(prefix="/clothing", tags=["Clothing"])

router.add_api_route("/items", upload_clothing_item, methods=["POST"], status_code=201)
router.add_api_route("/items", list_wardrobe_items, methods=["GET"])
router.add_api_route("/items/{id}", get_clothing_item, methods=["GET"])
router.add_api_route("/items/{id}", update_clothing_item, methods=["PATCH"])
router.add_api_route("/items/{id}", delete_clothing_item, methods=["DELETE"])
router.add_api_route("/items/{id}/status", get_clothing_item_status, methods=["GET"])
