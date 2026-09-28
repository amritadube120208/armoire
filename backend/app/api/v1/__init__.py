from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.wardrobe import router as wardrobe_router
from app.api.v1.clothing import router as clothing_router
from app.api.v1.images import router as images_router
from app.api.v1.weather import router as weather_router
from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.outfits import router as outfits_router
from app.api.v1.favorites import router as favorites_router
from app.api.v1.feedback import router as feedback_router
from app.api.v1.stylist import router as stylist_router

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(wardrobe_router)
api_v1_router.include_router(clothing_router)
api_v1_router.include_router(images_router)
api_v1_router.include_router(weather_router)
api_v1_router.include_router(recommendations_router)
api_v1_router.include_router(outfits_router)
api_v1_router.include_router(favorites_router)
api_v1_router.include_router(feedback_router)
api_v1_router.include_router(stylist_router)

__all__ = ["api_v1_router"]
