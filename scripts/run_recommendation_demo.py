"""
Simple Phase 2 test script to exercise the deterministic recommendation engine.

Usage (from project root):
    python -m scripts.run_recommendation_demo

This assumes the cleaned Zomato dataset already exists:
    python -m backend.data_ingestion.zomato_ingestion
"""

from __future__ import annotations

from phases.phase_2_recommendation_engine.backend.recommendation_engine import (
    Mood,
    PriceRange,
    UserPreference,
    generate_recommendations,
)


def main() -> None:
    # Example preferences: relaxed but realistic defaults.
    preference = UserPreference(
        location="Banashankari",
        cuisines=["North Indian"],
        price_range=PriceRange(min_price=200, max_price=1200),
        rating_min=3.0,
        mood=Mood.DATE_NIGHT,
    )

    recommendations = generate_recommendations(preference, top_n=10)

    if not recommendations:
        print("No recommendations found for the given preferences.")
        return

    print("=== Deterministic Recommendations (Phase 2 Demo) ===")
    for idx, rec in enumerate(recommendations, start=1):
        restaurant = rec.restaurant
        print(f"\n#{idx}: {restaurant.get('name')} ({restaurant.get('location')})")
        print(f"  Rating: {restaurant.get('rating')}  |  Cost: {restaurant.get('approx_cost')}")
        print(f"  Cuisines: {', '.join(restaurant.get('cuisines') or [])}")
        print(f"  Score: {rec.score:.3f}")
        print(f"  Matched factors: {rec.matched_factors}")
        print(f"  Explanation: {rec.explanation}")


if __name__ == "__main__":
    main()

