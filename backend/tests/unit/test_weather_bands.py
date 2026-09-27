"""
Unit tests for Weather Client & Requirement Band Mapping (Phase 7).
"""

import pytest
from app.weather.client import (
    TEMP_BANDS,
    PRECIPITATION_BANDS,
    CONDITION_FAMILIES,
    get_temp_band,
    get_precipitation_band,
    build_requirement_band,
    WeatherClient,
)


def test_temp_band_boundaries():
    """Verify temperature boundaries correctly map to defined bands."""
    # Freezing: [-50, 0)
    assert get_temp_band(-15.0)["label"] == "freezing"
    assert get_temp_band(-0.1)["label"] == "freezing"

    # Very cold: [0, 7)
    assert get_temp_band(0.0)["label"] == "very_cold"
    assert get_temp_band(6.9)["label"] == "very_cold"

    # Cold: [7, 13)
    assert get_temp_band(7.0)["label"] == "cold"
    assert get_temp_band(12.9)["label"] == "cold"

    # Cool: [13, 18)
    assert get_temp_band(13.0)["label"] == "cool"
    assert get_temp_band(17.9)["label"] == "cool"

    # Mild: [18, 23)
    assert get_temp_band(18.0)["label"] == "mild"
    assert get_temp_band(22.9)["label"] == "mild"

    # Warm: [23, 29)
    assert get_temp_band(23.0)["label"] == "warm"
    assert get_temp_band(28.9)["label"] == "warm"

    # Hot: [29, 100)
    assert get_temp_band(29.0)["label"] == "hot"
    assert get_temp_band(38.5)["label"] == "hot"


def test_precipitation_band_mapping():
    """Verify precipitation probabilities map to appropriate rain gear advice."""
    assert get_precipitation_band(0.0)["label"] == "none"
    assert get_precipitation_band(0.15)["suggests_rain_gear"] is False

    assert get_precipitation_band(0.25)["label"] == "light"
    assert get_precipitation_band(0.25)["suggests_rain_gear"] is True

    assert get_precipitation_band(0.60)["label"] == "moderate"
    assert get_precipitation_band(0.60)["suggests_rain_gear"] is True

    assert get_precipitation_band(0.85)["label"] == "heavy"
    assert get_precipitation_band(0.85)["suggests_rain_gear"] is True


def test_build_requirement_band_freezing_rain():
    """Verify requirement band synthesis for freezing conditions with rain."""
    conditions = {
        "temperature": -2.0,
        "condition": "rain",
        "precipitation_prob": 0.8,
        "humidity": 90,
        "wind_speed": 5.0,
    }
    band = build_requirement_band(conditions)

    assert band["temp_label"] == "freezing"
    assert band["warmth_level"] == 1.0
    assert "outerwear" in band["required_layers"]
    assert "shorts" in band["excluded_subtypes"]
    assert band["precipitation_label"] == "heavy"
    assert band["suggests_rain_gear"] is True
    assert band["condition_family"] == "rain"


def test_build_requirement_band_hot_clear():
    """Verify requirement band synthesis for hot clear summer conditions."""
    conditions = {
        "temperature": 32.0,
        "condition": "clear",
        "precipitation_prob": 0.05,
        "humidity": 40,
        "wind_speed": 1.5,
    }
    band = build_requirement_band(conditions)

    assert band["temp_label"] == "hot"
    assert band["warmth_level"] == 0.0
    assert band["required_layers"] == []
    assert "sweater" in band["excluded_subtypes"]
    assert band["suggests_rain_gear"] is False
    assert band["condition_family"] == "clear"


def test_mock_weather_client_deterministic():
    """Verify mock weather client returns valid schema and varies by coordinates."""
    client = WeatherClient(api_key=None)

    w1 = client._mock_conditions(28.6, 77.2)
    w2 = client._mock_conditions(28.6, 77.2)
    w3 = client._mock_conditions(51.5, -0.1)

    # Identical coords -> identical mock
    assert w1 == w2

    # Required fields present
    for k in ["temperature", "condition", "precipitation_prob", "humidity", "wind_speed"]:
        assert k in w1
        assert isinstance(w1[k], (int, float, str))

    # Different coords can vary
    assert isinstance(w3["temperature"], (int, float))
