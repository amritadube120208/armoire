"""
OpenWeatherMap client — Phase 7 full implementation.

Architecture (Backend.md Pipeline 5):
  - Live call when OPENWEATHER_API_KEY is set; structured mock otherwise.
  - Normalises raw OWM response into a flat WeatherConditions dict.
  - Maps temperature + conditions to a RequirementBand (what clothing layers needed).
  - All constants stored as data structures per Backend.md §4 constraint.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings


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

    async def get_current_conditions(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Fetch and normalise current weather.

        Returns a flat dict:
          temperature (°C), feels_like (°C), humidity (%), precipitation_prob [0–1],
          wind_speed (m/s), condition (OWM main string), condition_family,
          source ("live" | "mock"), [notice only in mock]
        """
        if not self.api_key:
            return self._mock_conditions(lat, lon)

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

        # OWM Current doesn't return precipitation_prob — use rain.1h as proxy
        rain_1h = rain.get("1h", 0.0)
        precip_prob = min(1.0, rain_1h / 5.0)  # 5mm/h = 100% proxy

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

    def get_requirement_band(self, conditions: Dict[str, Any]) -> Dict[str, Any]:
        """Convenience method: conditions dict → requirement band."""
        return build_requirement_band(conditions)


weather_client = WeatherClient()
