"""
Unit tests for Recommendation Engine & Scoring Modules (Phase 8).
"""

from datetime import date, timedelta
import pytest

from app.recommendations.weather_score import (
    calculate_weather_score,
    infer_warmth,
)
from app.recommendations.occasion_score import (
    calculate_occasion_score,
    formality_to_float,
)
from app.recommendations.color_score import (
    calculate_color_score,
    _pair_score,
)
from app.recommendations.style_score import (
    calculate_style_score,
    _pattern_coherence_score,
)
from app.recommendations.personalization_score import (
    calculate_personalization_score,
    _wear_count_score,
)
from app.recommendations.diversity_score import (
    calculate_diversity_score,
    _jaccard,
    _recency_weight,
)
from app.recommendations.engine import RecommendationEngine, compute_outfit_score


# ---------------------------------------------------------------------------
# Weather Score Tests
# ---------------------------------------------------------------------------

def test_weather_score_exact_match():
    """Exact warmth match should yield 1.0."""
    score = calculate_weather_score(
        item_warmth=0.5,
        target_warmth=0.5,
        item_subtype="jeans",
        excluded_subtypes=["shorts"],
    )
    assert score == 1.0


def test_weather_score_excluded_subtype():
    """Excluded subtype should trigger a hard low score penalty (0.05)."""
    score = calculate_weather_score(
        item_warmth=0.1,
        target_warmth=0.9,
        item_subtype="shorts",
        excluded_subtypes=["shorts", "sandals"],
    )
    assert score == 0.0


def test_weather_score_delta_penalty():
    """Greater difference in warmth should yield lower scores."""
    score_close = calculate_weather_score(item_warmth=0.6, target_warmth=0.7)
    score_far = calculate_weather_score(item_warmth=0.1, target_warmth=0.9)
    assert score_close > score_far
    assert 0.0 <= score_far <= 1.0


def test_infer_warmth_defaults():
    """Taxonomy warmth lookup fallback."""
    warmth_puffer = infer_warmth("outerwear", "puffer-jacket")
    warmth_tank = infer_warmth("tops", "tank-top")
    assert warmth_puffer > warmth_tank


# ---------------------------------------------------------------------------
# Occasion Score Tests
# ---------------------------------------------------------------------------

def test_occasion_score_matching():
    """Items within the expected formality range score 1.0."""
    score_casual = calculate_occasion_score(item_formality="casual", occasion="casual")
    assert score_casual == 1.0

    score_formal = calculate_occasion_score(item_formality="formal", occasion="formal")
    assert score_formal == 1.0


def test_occasion_score_underdressing_penalty():
    """Underdressing should be penalized heavily."""
    # Wearing casual (0.1) to black-tie (min 0.9)
    score = calculate_occasion_score(item_formality="casual", occasion="black-tie")
    assert score < 0.5


def test_occasion_score_overdressing_penalty():
    """Overdressing is penalized more gently than underdressing."""
    # Wearing formal (0.8) to casual (max 0.5)
    score_over = calculate_occasion_score(item_formality="formal", occasion="casual")
    # Wearing casual (0.1) to formal (min 0.7)
    score_under = calculate_occasion_score(item_formality="casual", occasion="formal")
    assert score_over > score_under


# ---------------------------------------------------------------------------
# Color Score Tests
# ---------------------------------------------------------------------------

def test_color_score_neutrals():
    """Neutrals pair harmoniously with anything."""
    score_white_navy = _pair_score("white", "navy")
    score_black_red = _pair_score("black", "red")
    assert score_white_navy >= 0.85
    assert score_black_red >= 0.85


def test_color_score_complementary():
    """Complementary colors yield high harmony scores."""
    score_comp = _pair_score("blue", "orange")
    assert score_comp >= 0.75


def test_color_score_clash():
    """Saturated clashing hues should yield lower scores."""
    score_clash = _pair_score("coral", "pink")
    score_neutral = _pair_score("white", "blue")
    assert score_clash < score_neutral


def test_calculate_color_score_multi_item():
    """Multi-item palette average calculation."""
    palette = ["navy", "white", "beige"]
    score = calculate_color_score(palette)
    assert score >= 0.85


# ---------------------------------------------------------------------------
# Style Score Tests
# ---------------------------------------------------------------------------

def test_style_score_pattern_coherence():
    """Fewer busy patterns yield higher style coherence."""
    score_calm = _pattern_coherence_score(["solid", "striped"])
    score_busy = _pattern_coherence_score(["floral", "animal-print", "camouflage"])
    assert score_calm > score_busy


# ---------------------------------------------------------------------------
# Personalization Score Tests
# ---------------------------------------------------------------------------

def test_personalization_score_affinity_boost():
    """Higher affinity for specific colors & categories should boost personalization."""
    affinities = {
        "color_affinity": {"blue": 9.0, "white": 8.0},
        "category_affinity": {"tops": 9.0, "bottoms": 8.0},
    }
    score_fav = calculate_personalization_score(
        item_colors=["blue", "white"],
        item_categories=["tops", "bottoms"],
        wear_counts=[3, 4],
        **affinities,
    )
    score_unfav = calculate_personalization_score(
        item_colors=["purple", "neon-green"],
        item_categories=["outerwear", "shoes"],
        wear_counts=[0, 0],
        **affinities,
    )
    assert score_fav > score_unfav


def test_wear_count_score_scaling():
    """Items worn frequently achieve higher implicit preference score."""
    score_zero = _wear_count_score([0, 0])
    score_high = _wear_count_score([5, 10])
    assert score_high > score_zero


# ---------------------------------------------------------------------------
# Diversity Score Tests
# ---------------------------------------------------------------------------

def test_diversity_score_novelty():
    """Brand new outfit combinations score 1.0 for diversity."""
    candidate = ["item-1", "item-2"]
    history = [
        {"item_ids": ["item-3", "item-4"], "worn_date": date.today()}
    ]
    assert calculate_diversity_score(candidate, history) == 1.0


def test_diversity_score_recent_repeat_penalty():
    """Exact duplicate worn today has maximum repetition penalty."""
    candidate = ["item-1", "item-2"]
    history = [
        {"item_ids": ["item-1", "item-2"], "worn_date": date.today()}
    ]
    score_today = calculate_diversity_score(candidate, history)
    assert score_today <= 0.1  # Jaccard 1.0 * weight 1.0 -> 0.0


def test_diversity_score_old_repeat_decay():
    """Outfits worn long ago receive decayed penalty."""
    candidate = ["item-1", "item-2"]
    history_old = [
        {"item_ids": ["item-1", "item-2"], "worn_date": date.today() - timedelta(days=60)}
    ]
    score_old = calculate_diversity_score(candidate, history_old)
    assert score_old >= 0.90


# ---------------------------------------------------------------------------
# Engine Overall Scoring Tests
# ---------------------------------------------------------------------------

def test_compute_outfit_score_weighted_sum():
    """Weighted sum matches default weights."""
    scores = {
        "weather_score": 1.0,
        "occasion_score": 1.0,
        "color_score": 1.0,
        "style_score": 1.0,
        "personalization_score": 1.0,
        "diversity_score": 1.0,
    }
    weights = RecommendationEngine.DEFAULT_WEIGHTS
    final = compute_outfit_score(scores, weights)
    assert round(final, 4) == 1.0

    scores_half = {k: 0.5 for k in scores}
    final_half = compute_outfit_score(scores_half, weights)
    assert round(final_half, 4) == 0.5
