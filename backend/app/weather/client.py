"""
OpenWeatherMap client — Phase 7 full implementation.

Architecture (Backend.md Pipeline 5):
  - Live call when OPENWEATHER_API_KEY is set; structured mock otherwise.
  - Normalises raw OWM response into a flat WeatherConditions dict.
  - Maps temperature + conditions to a RequirementBand (what clothing layers needed).
  - All constants stored as data structures per Backend.md §4 constraint.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import logging
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Temperature Bands (Backend.md Pipeline 5 — stored as data, not hardcoded)
# ---------------------------------------------------------------------------

# Each band: (label, min_c_inclusive, max_c_exclusive, warmth_level, required_layers)
# warmth_level is used by weather_score.py to compare against item warmth_rating.
TEMP_BANDS: List[Dict[str, Any]] = [
    {
        "label": "freezing",
        "min_c": -50.0,
        "max_c": 0.0,
        "warmth_level": 1.0,
        "required_layers": ["base_layer", "mid_layer", "outerwear"],
        "excluded_categories": ["shorts", "sandals", "tank-top"],
    },
    {
        "label": "very_cold",
        "min_c": 0.0,
        "max_c": 7.0,
        "warmth_level": 0.85,
        "required_layers": ["mid_layer", "outerwear"],
        "excluded_categories": ["shorts", "sandals"],
    },
    {
        "label": "cold",
        "min_c": 7.0,
        "max_c": 13.0,
        "warmth_level": 0.70,
        "required_layers": ["outerwear"],
        "excluded_categories": ["shorts", "sandals", "tank-top"],
    },
    {
        "label": "cool",
        "min_c": 13.0,
        "max_c": 18.0,
        "warmth_level": 0.55,
        "required_layers": ["light_jacket_optional"],
        "excluded_categories": ["sandals"],
    },
    {
        "label": "mild",
        "min_c": 18.0,
        "max_c": 23.0,
        "warmth_level": 0.35,
        "required_layers": [],
        "excluded_categories": [],
    },
    {
        "label": "warm",
        "min_c": 23.0,
        "max_c": 29.0,
        "warmth_level": 0.15,
        "required_layers": [],
        "excluded_categories": ["heavy_outerwear", "puffer-jacket", "wool-coat"],
    },
    {
        "label": "hot",
        "min_c": 29.0,
        "max_c": 100.0,
        "warmth_level": 0.0,
        "required_layers": [],
        "excluded_categories": ["heavy_outerwear", "puffer-jacket", "wool-coat", "sweater", "hoodie"],
    },
]

# Precipitation modifier — adds outerwear pressure if rain/snow
PRECIPITATION_BANDS = [
    {"label": "none",     "min_prob": 0.0,  "max_prob": 0.20, "suggests_rain_gear": False},
    {"label": "light",    "min_prob": 0.20, "max_prob": 0.50, "suggests_rain_gear": True},
    {"label": "moderate", "min_prob": 0.50, "max_prob": 0.75, "suggests_rain_gear": True},
    {"label": "heavy",    "min_prob": 0.75, "max_prob": 1.01, "suggests_rain_gear": True},
]

# Condition string → weather family (OWM "main" field)
CONDITION_FAMILIES = {
    "clear": "clear",
    "clouds": "cloudy",
    "rain": "rain",
    "drizzle": "rain",
    "thunderstorm": "rain",
    "snow": "snow",
    "mist": "fog",
    "fog": "fog",
    "haze": "fog",
    "smoke": "fog",
    "dust": "fog",
    "sand": "fog",
    "tornado": "extreme",
    "squall": "extreme",
    "ash": "extreme",
}


# ---------------------------------------------------------------------------
# Helper: derive requirement band from normalised conditions
# ---------------------------------------------------------------------------

def get_temp_band(temperature_c: float) -> Dict[str, Any]:
    """Return the TEMP_BANDS entry that matches the given temperature."""
    for band in TEMP_BANDS:
        if band["min_c"] <= temperature_c < band["max_c"]:
            return band
    # Fallback: last band (hot)
    return TEMP_BANDS[-1]


def get_precipitation_band(precipitation_prob: float) -> Dict[str, Any]:
    """Return the PRECIPITATION_BANDS entry for the given probability [0.0–1.0]."""
    for band in PRECIPITATION_BANDS:
        if band["min_prob"] <= precipitation_prob < band["max_prob"]:
            return band
    return PRECIPITATION_BANDS[-1]


def build_requirement_band(conditions: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a combined requirement band dict from normalised weather conditions.
    This is what the recommendation engine consumes.
    """
    temp_band = get_temp_band(conditions["temperature"])
    precip_band = get_precipitation_band(conditions.get("precipitation_prob", 0.0))
    condition_family = CONDITION_FAMILIES.get(
        conditions.get("condition", "").lower(), "clear"
    )

    return {
        "temp_label": temp_band["label"],
        "warmth_level": temp_band["warmth_level"],
        "required_layers": temp_band["required_layers"],
        "excluded_subtypes": temp_band["excluded_categories"],
        "precipitation_label": precip_band["label"],
        "suggests_rain_gear": precip_band["suggests_rain_gear"],
        "condition_family": condition_family,
    }


# ---------------------------------------------------------------------------
# Weather Client
# ---------------------------------------------------------------------------

class WeatherClient:
    """
    Fetches and normalises weather data from OpenWeatherMap.

    When OPENWEATHER_API_KEY is unset → returns structured deterministic mock.
    Interface contract: always returns the same dict shape regardless of source.
    """

    OWM_URL = "https://api.openweathermap.org/data/2.5/weather"
    OWM_ONECALL_URL = "https://api.openweathermap.org/data/3.0/onecall"
    TIMEOUT = 10.0

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.OPENWEATHER_API_KEY

    def _mock_conditions(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Structured mock for local dev without an API key.
        Deterministically varies by rough lat/lon bucket so tests
        don't always get the same exact temperature.
        """
        # Simple seasonal proxy: Northern hemisphere vs Southern, rough bucket
        import math
        temp_proxy = 18.0 + 8.0 * math.sin(math.radians(lat)) - 2.0 * math.cos(math.radians(lon))
        temp_c = round(temp_proxy, 1)

        return {
            "temperature": temp_c,
            "feels_like": round(temp_c - 1.5, 1),
            "humidity": 55.0,
            "precipitation_prob": 0.10,
            "wind_speed": 10.0,
            "condition": "Clouds",
            "condition_family": "cloudy",
            "source": "mock",
            "notice": "Mock data — set OPENWEATHER_API_KEY in .env for live weather.",
        }

    @staticmethod
    def _wmo_code_to_condition(code: int) -> Tuple[str, str]:
        """Maps WMO weather codes to (condition, condition_family)."""
        if code == 0:
            return "Clear", "clear"
        elif code in (1, 2, 3):
            return "Clouds", "cloudy"
        elif code in (45, 48):
            return "Fog", "fog"
        elif code in (51, 53, 55, 56, 57):
            return "Drizzle", "rain"
        elif code in (61, 63, 65, 66, 67, 80, 81, 82):
            return "Rain", "rain"
        elif code in (71, 73, 75, 77, 85, 86):
            return "Snow", "snow"
        elif code in (95, 96, 99):
            return "Thunderstorm", "rain"
        return "Clouds", "cloudy"

    async def _fetch_open_meteo(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Fetch real-time weather from Open-Meteo API (free worldwide provider, no API key required).
        """
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
            "wind_speed_unit": "ms",
        }
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        current = data.get("current", {})
        temp = float(current.get("temperature_2m", 20.0))
        feels_like = float(current.get("apparent_temperature", temp))
        humidity = float(current.get("relative_humidity_2m", 50.0))
        precip = float(current.get("precipitation", 0.0))
        wind_speed = float(current.get("wind_speed_10m", 0.0))
        weather_code = int(current.get("weather_code", 0))

        condition, condition_family = self._wmo_code_to_condition(weather_code)
        precip_prob = min(1.0, precip / 5.0) if precip > 0 else (0.4 if condition in ("Rain", "Drizzle") else 0.0)

        return {
            "temperature": round(temp, 1),
            "feels_like": round(feels_like, 1),
            "humidity": round(humidity, 1),
            "precipitation_prob": round(precip_prob, 2),
            "wind_speed": round(wind_speed, 1),
            "condition": condition,
            "condition_family": condition_family,
            "source": "live",
        }

    async def _fetch_owm(self, lat: float, lon: float) -> Dict[str, Any]:
        """Fetch current weather from OpenWeatherMap."""
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self.api_key,
            "units": "metric",
        }
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            resp = await client.get(self.OWM_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        main = data.get("main", {})
        wind = data.get("wind", {})
        weather = data.get("weather", [{}])[0]
        rain = data.get("rain", {})

        rain_1h = rain.get("1h", 0.0)
        precip_prob = min(1.0, rain_1h / 5.0)

        condition_raw = weather.get("main", "Clear")
        condition_family = CONDITION_FAMILIES.get(condition_raw.lower(), "clear")

        return {
            "temperature": main.get("temp", 20.0),
            "feels_like": main.get("feels_like", 20.0),
            "humidity": float(main.get("humidity", 50)),
            "precipitation_prob": precip_prob,
            "wind_speed": wind.get("speed", 0.0),
            "condition": condition_raw,
            "condition_family": condition_family,
            "source": "live",
        }

    async def get_current_conditions(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Fetch and normalise real-time current weather.
        Prioritizes OpenWeatherMap (if key set), then live Open-Meteo, falling back to mock on failure.
        """
        if self.api_key:
            try:
                return await self._fetch_owm(lat, lon)
            except Exception as e:
                logger.warning("OpenWeatherMap fetch failed, trying Open-Meteo: %s", e)

        try:
            return await self._fetch_open_meteo(lat, lon)
        except Exception as e:
            logger.warning("Open-Meteo live weather fetch failed, falling back to mock: %s", e)
            return self._mock_conditions(lat, lon)

    def get_requirement_band(self, conditions: Dict[str, Any]) -> Dict[str, Any]:
        """Convenience method: conditions dict → requirement band."""
        return build_requirement_band(conditions)


weather_client = WeatherClient()
