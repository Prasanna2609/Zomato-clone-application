from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

import logging
import numpy as np
import pandas as pd
import pyarrow.compute as pc

from phases.phase_1_data_ingestion.backend.data_ingestion.loader import load_cleaned_zomato

logger = logging.getLogger(__name__)


class Mood(str, Enum):
    DATE_NIGHT = "date_night"
    WORK_CAFE = "work_cafe"
    FAMILY_DINING = "family_dining"
    CASUAL_HANGOUT = "casual_hangout"
    COMFORT_FOOD = "comfort_food"


@dataclass
class PriceRange:
    """
    Normalized numeric price range for filtering and scoring.
    """

    min_price: Optional[float] = None
    max_price: Optional[float] = None


@dataclass
class UserPreference:
    """
    Backend view of the user preference schema used for deterministic
    recommendation logic in Phase 2.
    """

    location: str
    cuisines: List[str]
    price_range: PriceRange
    rating_min: float
    mood: Mood


@dataclass
class Recommendation:
    """
    Deterministic recommendation result for a single restaurant.
    """

    restaurant: Dict[str, Any]
    score: float
    matched_factors: Dict[str, Any]
    explanation: str


@dataclass
class MoodWeights:
    """
    Weight profile produced by the Mood Interpretation Layer.
    """

    rating_weight: float
    price_weight: float
    distance_weight: float
    popularity_weight: float
    ambience_weight: float


def interpret_mood(mood: Mood) -> MoodWeights:
    """
    Deterministic Mood Interpretation Layer.

    Maps a mood enum to a fixed weight profile which is later used by the
    scoring function. The semantics follow the architecture document:
    - date_night: high rating & ambience, medium distance, lower price.
    - work_cafe: high distance & ambience, medium rating, lower price.
    - family_dining: high rating & price, medium distance.
    - casual_hangout: balanced with extra popularity.
    - comfort_food: higher cuisine/price, moderate rating.
    """

    if mood is Mood.DATE_NIGHT:
        return MoodWeights(
            rating_weight=0.35,
            price_weight=0.1,
            distance_weight=0.15,
            popularity_weight=0.15,
            ambience_weight=0.25,
        )
    if mood is Mood.WORK_CAFE:
        return MoodWeights(
            rating_weight=0.2,
            price_weight=0.1,
            distance_weight=0.3,
            popularity_weight=0.15,
            ambience_weight=0.25,
        )
    if mood is Mood.FAMILY_DINING:
        return MoodWeights(
            rating_weight=0.3,
            price_weight=0.3,
            distance_weight=0.2,
            popularity_weight=0.15,
            ambience_weight=0.05,
        )
    if mood is Mood.CASUAL_HANGOUT:
        return MoodWeights(
            rating_weight=0.25,
            price_weight=0.15,
            distance_weight=0.2,
            popularity_weight=0.25,
            ambience_weight=0.15,
        )
    if mood is Mood.COMFORT_FOOD:
        return MoodWeights(
            rating_weight=0.2,
            price_weight=0.3,
            distance_weight=0.1,
            popularity_weight=0.1,
            ambience_weight=0.3,
        )

    # Fallback (should not be hit with a proper enum)
    return MoodWeights(
        rating_weight=0.25,
        price_weight=0.25,
        distance_weight=0.2,
        popularity_weight=0.15,
        ambience_weight=0.15,
    )


def _normalize_series(series: pd.Series) -> pd.Series:
    """
    Min-max normalize a numeric pandas Series to [0, 1].
    """

    if series.empty:
        return series
    min_val = series.min()
    max_val = series.max()
    if pd.isna(min_val) or pd.isna(max_val) or max_val == min_val:
        return pd.Series(np.zeros(len(series)), index=series.index)
    return (series - min_val) / (max_val - min_val)


def _compute_price_suitability(
    prices: pd.Series, price_range: PriceRange
) -> pd.Series:
    """
    Compute how well each restaurant's price fits within the desired range.

    A value of 1.0 indicates perfect fit, with values decaying linearly as the
    price moves away from the preferred range.
    """

    if price_range.min_price is None and price_range.max_price is None:
        # No strong price preference: everyone gets neutral 0.5
        return pd.Series(np.full(len(prices), 0.5), index=prices.index)

    center: Optional[float]
    tolerance: float

    if price_range.min_price is not None and price_range.max_price is not None:
        center = (price_range.min_price + price_range.max_price) / 2.0
        tolerance = (price_range.max_price - price_range.min_price) / 2.0 or 1.0
    elif price_range.min_price is not None:
        center = price_range.min_price
        tolerance = price_range.min_price or 1.0
    else:
        center = price_range.max_price
        tolerance = price_range.max_price or 1.0

    diff = (prices - center).abs()

    # Linearly decay score; clamp to [0, 1].
    raw = np.maximum(0.0, 1.0 - diff / (tolerance * 2.0))
    return pd.Series(raw, index=prices.index)

def _split_cuisines(row_val: Any) -> set:
    """Helper to consistently split cuisine strings or lists into a flat lowercase set."""
    if not row_val:
        return set()
    if isinstance(row_val, list):
        res = set()
        for c in row_val:
            if isinstance(c, str):
                res.update({x.strip().lower() for x in c.split(",")})
            else:
                res.add(str(c).lower().strip())
        return res
    if isinstance(row_val, str):
        return {x.strip().lower() for x in row_val.split(",")}
    return {str(row_val).lower().strip()}



def _compute_cuisine_match(
    df: pd.DataFrame, preferred_cuisines: Sequence[str]
) -> pd.Series:
    """
    Compute cuisine match score in [0, 1] based on overlap with preferred cuisines.

    Assumes the cleaned dataset has a `cuisines` column containing an iterable
    (e.g., list) of cuisine strings per row.
    """

    if not preferred_cuisines:
        # No strong preference → neutral score
        return pd.Series(np.full(len(df), 0.5), index=df.index)

    preferred_lower = {c.lower().strip() for c in preferred_cuisines}

    def row_score(row_cuisines: Any) -> float:
        row_set = _split_cuisines(row_cuisines)
        if not row_set:
            return 0.0

        intersection = preferred_lower.intersection(row_set)
        if not intersection:
            return 0.0
        
        # Reward partial matches: higher overlap = higher score.
        # len(intersection) / len(preferred_lower) gives 1.0 if all preferred are found,
        # but here we also care about how many of the restaurant's cuisines matched.
        # We'll use a simple ratio of matches to user preferences.
        return len(intersection) / len(preferred_lower)

    scores = df["cuisines"].apply(row_score)
    return scores.astype(float)


def _build_explanation(row: pd.Series, matched: Dict[str, Any]) -> str:
    """
    Build a simple, template-based human-readable explanation for why a
    restaurant was recommended. This is deliberately deterministic and
    non-LLM for Phase 2.
    """

    parts: List[str] = []
    name = str(row.get("name", "This place"))
    location = str(row.get("location", "the selected area"))

    parts.append(f"{name} in {location} matched your preferences")

    if matched.get("cuisine_match", False):
        parts.append("for the cuisines you like")
    if matched.get("within_budget", False):
        parts.append("and fits your budget")
    if matched.get("high_rating", False):
        parts.append("with a strong rating")
    if matched.get("popular", False):
        parts.append("and good popularity")
    if matched.get("family_friendly", False):
        parts.append("and is suitable for families")

    explanation = ", ".join(parts)
    if not explanation.endswith("."):
        explanation += "."
    return explanation


def generate_recommendations(
    user_preference: UserPreference,
    top_n: int = 10,
    dataset: Any = None,
) -> List[Recommendation]:
    """
    Deterministic recommendation pipeline for Phase 2.

    Steps:
    - Load cleaned dataset (or use the provided PyArrow Dataset).
    - Filter by location and rating lazily using PyArrow.
    - Convert matches to pandas and filter by cuisines.
    - Compute a weighted score per restaurant using mood-adjusted weights.
    - Return top-N `Recommendation` objects.
    """

    ds_obj = dataset if dataset is not None else load_cleaned_zomato()
    
    # Handle Pandas DataFrame directly (Streamlit Cloud fallback)
    if isinstance(ds_obj, pd.DataFrame):
        initial_count = len(ds_obj)
        if "location" not in ds_obj.columns:
            raise KeyError("Expected 'location' column in cleaned Zomato dataset.")
        
        user_loc = user_preference.location.lower()
        location_series = ds_obj["location"].fillna("").astype(str).str.lower()
        location_mask = location_series.str.contains(user_loc, na=False)
        
        if user_preference.rating_min is not None and "rating" in ds_obj.columns:
            rating_mask = ds_obj["rating"] >= user_preference.rating_min
        else:
            rating_mask = pd.Series(np.ones(len(ds_obj), dtype=bool), index=ds_obj.index)
            
        df = ds_obj[location_mask & rating_mask].copy()
        
    else:
        # Standard PyArrow lazy loading (Local / Main backend)
        initial_count = ds_obj.count_rows()

        if "location" not in ds_obj.schema.names:
            raise KeyError("Expected 'location' column in cleaned Zomato dataset.")

        user_loc = user_preference.location.lower()
        
        # Use PyArrow for basic filters (location, rating)
        loc_expr = pc.match_substring(pc.utf8_lower(pc.field("location")), user_loc)
        
        if user_preference.rating_min is not None and "rating" in ds_obj.schema.names:
            filter_expr = loc_expr & (pc.field("rating") >= user_preference.rating_min)
        else:
            filter_expr = loc_expr

        # Apply PyArrow filter & convert just matches to Pandas
        table = ds_obj.to_table(filter=filter_expr)
        df = table.to_pandas()
    
    scanned_count = len(df)
    logger.info(f"PyArrow filtering: Scanned {initial_count} rows -> {scanned_count} rows returned for Pandas logic.")

    if df.empty:
        logger.info(f"Filtering resulted in 0 matches for location: {user_loc}, rating >= {user_preference.rating_min}")
        return []

    # Build location and rating masks (already filtered by PyArrow, so all True)
    location_mask = pd.Series(np.ones(len(df), dtype=bool), index=df.index)
    rating_mask = pd.Series(np.ones(len(df), dtype=bool), index=df.index)

    # Cuisine hard filter: at least one matching cuisine (case-insensitive)
    if user_preference.cuisines:
        preferred_lower = {c.lower().strip() for c in user_preference.cuisines}
        
        def cuisine_matches(row_cuisines: Any) -> bool:
            row_set = _split_cuisines(row_cuisines)
            if not row_set:
                return False
            # ANY-match: if any user-preferred cuisine is in the restaurant's list
            return any(c in row_set for c in preferred_lower)

        cuisine_mask = df["cuisines"].apply(cuisine_matches)
        pass_count = cuisine_mask.sum()
        logger.info(f"Cuisine filter: {pass_count} restaurants pass ANY-match for {user_preference.cuisines}")
    else:
        cuisine_mask = pd.Series(np.ones(len(df), dtype=bool), index=df.index)

    # Apply strict hard filters: ALL must match.
    filtered = df[location_mask & rating_mask & cuisine_mask]

    if filtered.empty:
        logger.info(f"Filtering resulted in 0 matches for location: {user_loc}, rating >= {user_preference.rating_min}, cuisines: {user_preference.cuisines}")
        return []

    final_count = len(filtered)
    logger.info(f"Recommendation filtering: {initial_count} restaurants -> {final_count} after user filters.")

    # Compute feature scores
    weights = interpret_mood(user_preference.mood)

    rating_series = filtered["rating"] if "rating" in filtered.columns else pd.Series(
        np.zeros(len(filtered)), index=filtered.index
    )
    normalized_rating = _normalize_series(rating_series)

    price_series = (
        filtered["approx_cost"]
        if "approx_cost" in filtered.columns
        else pd.Series(np.zeros(len(filtered)), index=filtered.index)
    )
    price_suitability = _compute_price_suitability(price_series, user_preference.price_range)

    popularity_series = (
        filtered["votes"]
        if "votes" in filtered.columns
        else pd.Series(np.zeros(len(filtered)), index=filtered.index)
    )
    popularity_score = _normalize_series(popularity_series)

    # Distance & ambience are not explicitly present in the base dataset, so we
    # approximate them deterministically for now.
    distance_score = pd.Series(np.full(len(filtered), 0.5), index=filtered.index)
    ambience_score = pd.Series(np.full(len(filtered), 0.5), index=filtered.index)

    cuisine_match_score = _compute_cuisine_match(filtered, user_preference.cuisines)

    # Incorporate cuisine match into both popularity and ambience notionally,
    # emphasizing mood impact without overfitting to any single feature.
    combined_ambience = (ambience_score + cuisine_match_score) / 2.0
    combined_popularity = (popularity_score + cuisine_match_score) / 2.0

    final_score = (
        weights.rating_weight * normalized_rating
        + weights.price_weight * price_suitability
        + weights.distance_weight * distance_score
        + weights.popularity_weight * combined_popularity
        + weights.ambience_weight * combined_ambience
    )

    filtered = filtered.copy()
    filtered["__score"] = final_score

    # Derive matched_factors flags
    matched_factors_list: List[Tuple[int, Dict[str, Any]]] = []
    for idx, row in filtered.iterrows():
        matched: Dict[str, Any] = {}

        matched["cuisine_match"] = cuisine_match_score.loc[idx] > 0.0
        matched["within_budget"] = price_suitability.loc[idx] >= 0.5
        matched["high_rating"] = normalized_rating.loc[idx] >= 0.6
        matched["popular"] = combined_popularity.loc[idx] >= 0.6

        if user_preference.mood is Mood.FAMILY_DINING:
            matched["family_friendly"] = True

        matched_factors_list.append((idx, matched))

    # Sort by score and deduplicate by name + location
    filtered_sorted = filtered.sort_values("__score", ascending=False)
    initial_filtered_count = len(filtered_sorted)
    
    # Keep only the highest-scoring instance of each restaurant
    deduplicated = filtered_sorted.drop_duplicates(subset=["name", "location"], keep="first")
    removed_count = initial_filtered_count - len(deduplicated)
    
    if removed_count > 0:
        logger.info(f"Deduplication removed {removed_count} duplicate restaurant entries.")

    # Select top-N unique results
    top = deduplicated.head(top_n)

    idx_to_matched = dict(matched_factors_list)
    recommendations: List[Recommendation] = []

    for _, row in top.iterrows():
        idx = row.name
        matched = idx_to_matched.get(idx, {})

        restaurant_payload: Dict[str, Any] = {
            "restaurant_id": row.get("restaurant_id"),
            "name": row.get("name"),
            "location": row.get("location"),
            "cuisines": row.get("cuisines"),
            "rating": row.get("rating"),
            "approx_cost": row.get("approx_cost"),
        }

        explanation = _build_explanation(row, matched)

        recommendations.append(
            Recommendation(
                restaurant=restaurant_payload,
                score=float(row["__score"]),
                matched_factors=matched,
                explanation=explanation,
            )
        )

    return recommendations

