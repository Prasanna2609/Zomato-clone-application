import json
import logging
from typing import Any, Dict, List, Optional

import requests

from shared.config.config import GROQ_API_KEY, GROQ_API_URL, GROQ_MODEL, USE_LLM_EXPLANATIONS

logger = logging.getLogger(__name__)

def generate_batch_llm_explanations(
    user_preference: Any,
    restaurants_data: List[Dict[str, Any]]
) -> List[str]:
    """
    Generate natural-language explanations for multiple restaurants in a single LLM call.
    
    Args:
        user_preference: The UserPreference object.
        restaurants_data: List of dicts, each with 'restaurant', 'matched_factors', and 'fallback_explanation'.
        
    Returns:
        List of concise 1-2 sentence explanations, mapped by index.
    """
    fallbacks = [r['fallback_explanation'] for r in restaurants_data]
    
    if not USE_LLM_EXPLANATIONS or not GROQ_API_KEY:
        return fallbacks

    try:
        # Mood behavioral interpretations
        MOOD_INTERPRETATIONS = {
            "date_night": "romantic, high ambience, quality dining",
            "work_cafe": "calm, comfortable seating, longer stay friendly",
            "family_dining": "budget-friendly, spacious, group suitable",
            "casual_hangout": "popular, lively, social atmosphere",
            "comfort_food": "familiar cuisines, cozy experience"
        }
        
        selected_mood = user_preference.mood.value
        mood_context = MOOD_INTERPRETATIONS.get(selected_mood, "general dining")

        # Prepare restaurant list for prompt
        restaurants_brief = []
        for i, r in enumerate(restaurants_data):
            res = r['restaurant']
            mf = r['matched_factors']
            restaurants_brief.append({
                "id": i,
                "name": res.get('name'),
                "cuisines": res.get('cuisines'),
                "rating": res.get('rating'),
                "cost": res.get('approx_cost'),
                "factors": {
                    "cuisine_match": bool(mf.get('cuisine_match')),
                    "within_budget": bool(mf.get('within_budget')),
                    "high_rating": bool(mf.get('high_rating')),
                    "popular": bool(mf.get('popular'))
                }
            })

        # Construct a structured prompt for the LLM
        prompt = f"""
        Generate concise 1-2 sentence recommendations for the following {len(restaurants_brief)} restaurants based on user preferences and their current MOOD.
        
        USER CONTEXT:
        - Mood: {selected_mood.replace('_', ' ')} (User is looking for: {mood_context})
        - Target Cuisines: {', '.join(user_preference.cuisines)}
        - Min Rating Requested: {user_preference.rating_min}
        
        RESTAURANTS TO EXPLAIN:
        {json.dumps(restaurants_brief, indent=2)}
        
        INSTRUCTIONS:
        1. For each restaurant, explain WHY it matches the user's mood ({selected_mood.replace('_', ' ')}).
        2. Reference the mood context naturally.
        3. Return ONLY a JSON object with a key "explanations" which is a list of strings in the exact same order as provided.
        4. Do NOT invent any details. Stick to the provided facts.

        Example Output:
        {{
          "explanations": [
            "Explanation for restaurant 0...",
            "Explanation for restaurant 1..."
          ]
        }}
        """

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": "You are a helpful Zomato dining assistant that responds only in JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 1000,
            "response_format": {"type": "json_object"}
        }

        response = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content'].strip()
            data = json.loads(content)
            explanations = data.get("explanations", [])
            
            # Map back or fallback if count mismatch
            final_explanations = []
            for i in range(len(restaurants_data)):
                if i < len(explanations) and explanations[i]:
                    exp = explanations[i].replace('"', '').replace('\n', ' ')
                    final_explanations.append(exp)
                else:
                    final_explanations.append(fallbacks[i])
            
            logger.info("LLM batch explanation used — 1 API call")
            return final_explanations
        else:
            logger.warning(f"Batch LLM API returned status {response.status_code}. Using fallbacks.")
            return fallbacks

    except Exception as e:
        logger.error(f"Error generating batch LLM explanations: {e}")
        return fallbacks

def generate_llm_explanation(
    user_preference: Any,
    restaurant: Dict[str, Any],
    matched_factors: Dict[str, Any],
    fallback_explanation: str
) -> str:
    """
    DEPRECATED: Use generate_batch_llm_explanations for efficiency.
    Generate a single natural-language explanation using an LLM.
    """
    # Simply wrap the batch function for a single item to maintain API compatibility if needed
    results = generate_batch_llm_explanations(
        user_preference, 
        [{"restaurant": restaurant, "matched_factors": matched_factors, "fallback_explanation": fallback_explanation}]
    )
    return results[0]
