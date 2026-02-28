from __future__ import annotations

from typing import Any, Dict, List

import logging
import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.config.config import USE_LLM_EXPLANATIONS, DATA_DIR, ALLOWED_ORIGINS
from phases.phase_1_data_ingestion.backend.data_ingestion.loader import load_cleaned_zomato
from phases.phase_2_recommendation_engine.backend.recommendation_engine import Mood, PriceRange, UserPreference, generate_recommendations
from phases.phase_3_api.backend.api.schemas import RecommendationResponse, UserPreferenceRequest, OptionsResponse
from phases.phase_5_llm.backend.llm.explainer import generate_batch_llm_explanations


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Restaurant Recommendation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache for locations and cuisines
_options_cache: Dict[str, List[str]] = {"locations": [], "cuisines": []}

@app.on_event("startup")
def startup_event():
    df = load_cleaned_zomato()
    _options_cache["locations"] = sorted(df["location"].dropna().unique().tolist())
    
    # Flatten and get unique cuisines
    all_cuisines = set()
    for sublist in df["cuisines_normalized"].dropna():
        for cuisine in sublist:
            all_cuisines.add(cuisine)
    _options_cache["cuisines"] = sorted(list(all_cuisines))


def _to_python_scalars(value: Any) -> Any:
    """
    Convert numpy scalar types inside nested structures into native Python
    types so that Pydantic/JSON serialization works reliably.
    """

    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {k: _to_python_scalars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_python_scalars(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_to_python_scalars(v) for v in value)
    return value


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/system-status")
def system_status() -> dict:
    dataset_exists = (DATA_DIR / "zomato_cleaned.parquet").exists()
    return {
        "api": "ok",
        "dataset_loaded": dataset_exists,
        "llm_enabled": USE_LLM_EXPLANATIONS
    }


@app.get("/options", response_model=OptionsResponse)
def get_options() -> OptionsResponse:
    return OptionsResponse(
        locations=_options_cache["locations"],
        cuisines=_options_cache["cuisines"]
    )


@app.post("/recommendations", response_model=List[RecommendationResponse])
def get_recommendations(payload: UserPreferenceRequest) -> List[RecommendationResponse]:
    price_range = PriceRange(
        min_price=payload.price_range.min_price if payload.price_range else None,
        max_price=payload.price_range.max_price if payload.price_range else None,
    )

    user_preference = UserPreference(
        location=payload.location,
        cuisines=payload.cuisines,
        price_range=price_range,
        rating_min=payload.rating_min,
        mood=Mood(payload.mood.value),
    )

    logger.info(f"Incoming recommendation request: {user_preference.location}, mood={user_preference.mood.value}")

    recommendations = generate_recommendations(user_preference=user_preference)

    # If no restaurants match hard filters, return empty list immediately
    if not recommendations:
        logger.info("No recommendations found matching hard filters. Skipping LLM explanation call.")
        return []

    # Prepare data for batch LLM explanation
    batch_data = []
    for r in recommendations:
        batch_data.append({
            "restaurant": r.restaurant,
            "matched_factors": r.matched_factors,
            "fallback_explanation": r.explanation
        })

    # Single API call for all explanations
    explanations = generate_batch_llm_explanations(
        user_preference=user_preference,
        restaurants_data=batch_data
    )

    enriched_results = []
    for i, r in enumerate(recommendations):
        enriched_results.append(
            RecommendationResponse(
                restaurant=_to_python_scalars(r.restaurant),
                score=float(_to_python_scalars(r.score)),
                matched_factors=_to_python_scalars(r.matched_factors),
                explanation=explanations[i],
            )
        )

    return enriched_results
