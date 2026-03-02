import streamlit as st
import logging
import time

from phases.phase_1_data_ingestion.backend.data_ingestion.loader import load_cleaned_zomato
from phases.phase_2_recommendation_engine.backend.recommendation_engine import (
    Mood, 
    PriceRange, 
    UserPreference, 
    generate_recommendations
)
from phases.phase_5_llm.backend.llm.explainer import generate_batch_llm_explanations
from shared.config.config import USE_LLM_EXPLANATIONS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Zomato AI Recommendations",
    page_icon="🍔",
    layout="centered"
)

# Application CSS
st.markdown("""
<style>
    .restaurant-card {
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        margin-bottom: 1rem;
        background-color: #ffffff;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    .restaurant-title {
        color: #cb202d;
        font-size: 1.5rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
    }
    .restaurant-cuisines {
        color: #666;
        font-style: italic;
        margin-bottom: 0.5rem;
    }
    .restaurant-meta {
        display: flex;
        gap: 1rem;
        margin-bottom: 1rem;
        font-size: 0.9rem;
    }
    .rating-badge {
        background-color: #24963f;
        color: white;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .cost-badge {
        color: #444;
        font-weight: 500;
    }
    .explanation-box {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 6px;
        border-left: 4px solid #cb202d;
        font-size: 0.95rem;
        line-height: 1.4;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_dataset():
    """Load the dataset lazily using PyArrow."""
    return load_cleaned_zomato()

@st.cache_data
def get_options():
    """Extract location and cuisine options memory-efficiently."""
    dataset = get_dataset()
    df = dataset.to_table(columns=["location", "cuisines_normalized"]).to_pandas()
    
    locations = sorted(df["location"].dropna().unique().tolist())
    
    all_cuisines = set()
    for sublist in df["cuisines_normalized"].dropna():
        for cuisine in sublist:
            all_cuisines.add(cuisine)
    
    cuisines = sorted(list(all_cuisines))
    
    del df
    return {"locations": locations, "cuisines": cuisines}


def main():
    st.title("🍽️ Zomato AI Matchmaker")
    st.write("Find the perfect restaurant for your mood and preferences!")
    
    st.markdown("---")
    
    # Load options safely
    try:
        with st.spinner("Loading dataset options..."):
            options = get_options()
            locations = options["locations"]
            all_cuisines = options["cuisines"]
    except Exception as e:
        st.error(f"Error loading dataset: {str(e)}")
        st.info("Make sure you have run the data ingestion to produce the cleaned parquet file!")
        st.stop()
        
    # Build UI
    with st.container():
        st.subheader("Your Preferences")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Set default index safely based on available locations
            loc_idx = locations.index("indiranagar") if "indiranagar" in locations else 0
            location = st.selectbox("Location", options=locations, index=loc_idx)
            
            price_min = st.number_input("Min Price (₹ for two)", min_value=0, value=0, step=100)
            price_max = st.number_input("Max Price (₹ for two)", min_value=0, value=2000, step=100)
            
        with col2:
            cuisines = st.multiselect("Cuisines", options=all_cuisines, placeholder="Select cuisines...")
            rating_min = st.slider("Minimum Rating", min_value=1.0, max_value=5.0, value=4.0, step=0.1)
            
        mood = st.selectbox(
            "What's your mood?",
            options=[m.value for m in set(Mood)],
            format_func=lambda x: x.replace("_", " ").title()
        )
        
    submit_button = st.button("Find Restaurants 🚀", type="primary", use_container_width=True)
    
    if submit_button:
        with st.spinner("Generating AI recommendations..."):
            start_time = time.time()
            
            # 1. Build request
            price_range = PriceRange(
                min_price=float(price_min) if price_min > 0 else None,
                max_price=float(price_max) if price_max > 0 else None
            )
            
            user_preference = UserPreference(
                location=location,
                cuisines=cuisines,
                price_range=price_range,
                rating_min=rating_min,
                mood=Mood(mood),
            )
            
            # 2. Get deterministic recommendations
            try:
                ds = get_dataset()
                recommendations = generate_recommendations(user_preference=user_preference, dataset=ds)
                
                if not recommendations:
                    st.warning("No restaurants found matching your criteria. Try loosening your filters!")
                    return
                
                # 3. Generate LLM Explanations exactly as API does
                if USE_LLM_EXPLANATIONS:
                    batch_data = []
                    for r in recommendations:
                        batch_data.append({
                            "restaurant": r.restaurant,
                            "matched_factors": r.matched_factors,
                            "fallback_explanation": r.explanation
                        })
                    
                    try:
                        explanations = generate_batch_llm_explanations(
                            user_preference=user_preference,
                            restaurants_data=batch_data
                        )
                        # Patch recommendations with LLM explanations
                        for i, r in enumerate(recommendations):
                            r.explanation = explanations[i]
                    except Exception as e:
                        logger.error(f"LLM batch failed: {e}")
                        st.toast("LLM explanation failed, falling back to standard descriptions.")
                
                # 4. Display Results
                elapsed = time.time() - start_time
                st.success(f"Found {len(recommendations)} matches in {elapsed:.2f} seconds!")
                
                for r in recommendations:
                    rest = r.restaurant
                    
                    # Convert fields safely
                    name = str(rest.get("name", "Unknown"))
                    loc = str(rest.get("location", ""))
                    cuisine_str = str(rest.get("cuisines", ""))
                    rating = rest.get("rating", "N/A")
                    cost = rest.get("approx_cost", "N/A")
                    
                    st.markdown(f"""
                    <div class="restaurant-card">
                        <div class="restaurant-title">{name}</div>
                        <div class="restaurant-cuisines">🍽️ {cuisine_str}</div>
                        <div class="restaurant-meta">
                            <span class="rating-badge">⭐ {rating}/5</span>
                            <span class="cost-badge">💰 ₹{cost} for two</span>
                            <span>📍 {loc}</span>
                        </div>
                        <div class="explanation-box">
                            <strong>Why this place?</strong><br/>
                            {r.explanation}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
            except Exception as e:
                logger.error(f"Recommendation failed: {e}", exc_info=True)
                st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
