"""
Weather API Router — Phase 7 full implementation.

GET /api/v1/weather/current
  - Optional query params: lat, lon (falls back to user's stored location)
  - Returns normalised conditions + requirement_band
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.models.base import get_async_db
from app.models.user import User
from app.services.weather_service import WeatherService

router = APIRouter(prefix="/weather", tags=["Weather"])


@router.get("/current")
async def get_current_weather(
    lat: Optional[float] = Query(None, description="Latitude (falls back to user profile location)"),
    lon: Optional[float] = Query(None, description="Longitude (falls back to user profile location)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Returns normalised weather for the user's location, including a requirement_band
    that the recommendation engine uses to filter clothing appropriateness.

    Priority for coordinates:
      1. lat/lon query params (explicit override)
      2. User's stored location in profile (user.location = {"lat": ..., "lon": ...})
      3. Default: New Delhi (28.6, 77.2) — clearly documented in response
    """
    # Resolve coordinates
    resolved_lat: float
    resolved_lon: float
    location_source: str

    if lat is not None and lon is not None:
        resolved_lat, resolved_lon = lat, lon
        location_source = "query_param"
    elif current_user.location and "lat" in current_user.location and "lon" in current_user.location:
        resolved_lat = float(current_user.location["lat"])
        resolved_lon = float(current_user.location["lon"])
        location_source = "user_profile"
    else:
        resolved_lat, resolved_lon = 28.6, 77.2
        location_source = "default_new_delhi"

    svc = WeatherService(db)
    conditions = await svc.get_current_weather(lat=resolved_lat, lon=resolved_lon)

    return {
        **conditions,
        "location": {"lat": resolved_lat, "lon": resolved_lon, "source": location_source},
    }
