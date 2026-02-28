from phases.phase_2_recommendation_engine.backend.recommendation_engine import (
    Mood,
    PriceRange,
    UserPreference,
    generate_recommendations,
)
from phases.phase_1_data_ingestion.backend.data_ingestion.loader import load_cleaned_zomato


def test_generate_recommendations_returns_results():
    df = load_cleaned_zomato()

    user_pref = UserPreference(
        location="Banashankari",
        cuisines=["North Indian"],
        price_range=PriceRange(min_price=200, max_price=800),
        rating_min=3.0,
        mood=Mood.CASUAL_HANGOUT,
    )

    recommendations = generate_recommendations(user_preference=user_pref, dataframe=df)

    assert isinstance(recommendations, list)
    assert len(recommendations) > 0

    first = recommendations[0]
    assert first.score is not None
    assert isinstance(first.score, float)
    assert first.explanation

