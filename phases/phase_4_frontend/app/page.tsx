"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

const API_BASE_URL = "http://localhost:8000";

type Mood =
  | "date_night"
  | "work_cafe"
  | "family_dining"
  | "casual_hangout"
  | "comfort_food";

interface PriceRangeRequest {
  min_price?: number | null;
  max_price?: number | null;
}

interface UserPreferenceRequest {
  location: string;
  cuisines: string[];
  price_range?: PriceRangeRequest | null;
  rating_min: number;
  mood: Mood;
}

interface RestaurantInfo {
  restaurant_id: unknown;
  name?: string | null;
  location?: string | null;
  cuisines?: unknown;
  rating?: number | null;
  approx_cost?: number | null;
}

interface RecommendationResponse {
  restaurant: RestaurantInfo;
  score: number;
  matched_factors: Record<string, unknown>;
  explanation: string;
}

const MOOD_OPTIONS: { value: Mood; label: string }[] = [
  { value: "date_night", label: "Date night" },
  { value: "work_cafe", label: "Work café" },
  { value: "family_dining", label: "Family dining" },
  { value: "casual_hangout", label: "Casual hangout" },
  { value: "comfort_food", label: "Comfort food" }
];

const DEFAULT_CUISINE_SUGGESTIONS = [
  "North Indian",
  "South Indian",
  "Chinese",
  "Italian",
  "Fast Food",
  "Cafe",
  "Desserts"
];

const DEFAULT_LOCATION_SUGGESTIONS = [
  "Banashankari",
  "Indiranagar",
  "BTM",
  "Koramangala",
  "Whitefield",
  "HSR Layout"
];

export default function HomePage() {
  const [location, setLocation] = useState<string>("");
  const [locationError, setLocationError] = useState<string | null>(null);
  const [cuisineInput, setCuisineInput] = useState<string>("");
  const [cuisines, setCuisines] = useState<string[]>([]);
  const [minPrice, setMinPrice] = useState<string>("");
  const [maxPrice, setMaxPrice] = useState<string>("");
  const [ratingMin, setRatingMin] = useState<string>("3.5");
  const [mood, setMood] = useState<Mood>("date_night");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<RecommendationResponse[]>([]);
  const [hasSearched, setHasSearched] = useState(false);

  const [availableLocations, setAvailableLocations] = useState<string[]>([]);
  const [availableCuisines, setAvailableCuisines] = useState<string[]>([]);

  // State for detailed restaurant view
  const [selectedResult, setSelectedResult] = useState<RecommendationResponse | null>(null);

  // Helper for placeholder images based on cuisine keywords
  const getPlaceholderImage = (cuisineLabels: unknown) => {
    const list = Array.isArray(cuisineLabels) ? cuisineLabels : [String(cuisineLabels)];
    const text = list.join(" ").toLowerCase();

    if (text.includes("pizza") || text.includes("italian")) return "/assets/cuisines/pizza.png";
    if (text.includes("chinese") || text.includes("noodle") || text.includes("momos")) return "/assets/cuisines/chinese.png";
    if (text.includes("north indian") || text.includes("south indian") || text.includes("mughlai") || text.includes("biryani")) return "/assets/cuisines/indian.png";
    if (text.includes("burger") || text.includes("fast food") || text.includes("sandwich")) return "/assets/cuisines/burger.png";
    if (text.includes("cafe") || text.includes("beverages") || text.includes("coffee")) return "/assets/cuisines/cafe.png";

    // Default to indian if no match
    return "/assets/cuisines/dineout.png";
  };

  const renderBadges = (matchedFactors: Record<string, any>) => {
    const factorMap: Record<string, string> = {
      cuisine_match: "🍽 Cuisine Match",
      high_rating: "⭐ Highly Rated",
      within_budget: "💰 Budget Friendly",
      popular: "🔥 Popular Choice",
      mood_match: "💬 Matches Your Mood",
      family_friendly: "👨‍👩‍👧‍👦 Family Friendly",
    };

    return (
      <div className="badge-container">
        {Object.entries(matchedFactors).map(([key, value]) => {
          if (value && factorMap[key]) {
            return (
              <span key={key} className="badge">
                {factorMap[key]}
              </span>
            );
          }
          return null;
        })}
      </div>
    );
  };

  // Fetch dynamic options from backend
  useEffect(() => {
    void (async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/options`);
        if (response.ok) {
          const data = await response.json();
          setAvailableLocations(data.locations);
          setAvailableCuisines(data.cuisines);
        }
      } catch (err) {
        console.error("Failed to fetch options:", err);
      }
    })();
  }, []);

  const parsedPriceRange: PriceRangeRequest | null = useMemo(() => {
    const min = minPrice.trim() === "" ? null : Number(minPrice);
    const max = maxPrice.trim() === "" ? null : Number(maxPrice);
    if (min == null && max == null) return null;
    return { min_price: Number.isNaN(min) ? null : min, max_price: Number.isNaN(max) ? null : max };
  }, [minPrice, maxPrice]);

  const handleAddCuisine = () => {
    const candidate = cuisineInput.trim();
    if (!candidate) return;
    if (!cuisines.includes(candidate)) {
      setCuisines((prev) => [...prev, candidate]);
    }
    setCuisineInput("");
  };

  const handleCuisineKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      handleAddCuisine();
    }
  };

  const handleRemoveCuisine = (value: string) => {
    setCuisines((prev) => prev.filter((c) => c !== value));
  };

  const handleCuisineSuggestionClick = (value: string) => {
    if (!cuisines.includes(value)) {
      setCuisines((prev) => [...prev, value]);
    }
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setLocationError(null);

    setHasSearched(true);

    if (!location.trim()) {
      setLocationError("Location is required.");
      return;
    }

    const rating = Number(ratingMin);
    if (Number.isNaN(rating) || rating < 0) {
      setError("Please provide a valid minimum rating.");
      return;
    }

    const payload: UserPreferenceRequest = {
      location: location.trim(),
      cuisines,
      price_range: parsedPriceRange,
      rating_min: rating,
      mood
    };

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/recommendations`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(
          text || `Request failed with status ${response.status} ${response.statusText}`
        );
      }

      const data: RecommendationResponse[] = await response.json();
      setResults(data);
    } catch (err) {
      console.error(err);
      setError(
        "Unable to fetch recommendations. Please check backend connection or try again."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="page-container">
      <header className="page-header" style={{ alignItems: "center", textAlign: "center", marginBottom: "3rem" }}>
        <div style={{ marginBottom: "1.5rem" }}>
          <img
            src="/assets/zomato_logo.png"
            alt="Zomato"
            style={{ height: "60px", width: "auto" }}
          />
        </div>
        <h1 className="page-title">Find the right place.</h1>
        <p className="page-subtitle">
          Discover the best food & drinks in your city.
        </p>
      </header>

      <section className="card">
        <h2 className="section-title">Your preferences</h2>
        <form onSubmit={handleSubmit} className="form-grid">
          <div className="form-field full-width">
            <label className="form-label" htmlFor="location">
              Location
            </label>
            <select
              id="location"
              className="form-select"
              value={location}
              onChange={(e) => {
                setLocation(e.target.value);
                if (locationError) {
                  setLocationError(null);
                }
              }}
            >
              <option value="">Select a location</option>
              {(availableLocations.length > 0 ? availableLocations : DEFAULT_LOCATION_SUGGESTIONS).map((loc) => (
                <option key={loc} value={loc}>
                  {loc}
                </option>
              ))}
            </select>
            {locationError && <div className="error-text">{locationError}</div>}
          </div>

          <div className="form-field full-width">
            <label className="form-label" htmlFor="cuisines">
              Cuisines (multi-select)
            </label>
            <select
              id="cuisines-select"
              className="form-select"
              value=""
              onChange={(e) => {
                if (e.target.value && !cuisines.includes(e.target.value)) {
                  setCuisines((prev) => [...prev, e.target.value]);
                }
              }}
            >
              <option value="">Add a cuisine...</option>
              {(availableCuisines.length > 0 ? availableCuisines : DEFAULT_CUISINE_SUGGESTIONS).map((cuisine) => (
                <option key={cuisine} value={cuisine}>
                  {cuisine}
                </option>
              ))}
            </select>
            <div style={{ marginTop: "0.5rem", display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
              {cuisines.map((cuisine) => (
                <button
                  key={cuisine}
                  type="button"
                  className="pill"
                  style={{ background: "#e23744", color: "white", border: "none", cursor: "pointer" }}
                  onClick={() => handleRemoveCuisine(cuisine)}
                >
                  {cuisine} <span style={{ marginLeft: "0.25rem" }}>×</span>
                </button>
              ))}
            </div>
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="minPrice">
              Min price (two people)
            </label>
            <input
              id="minPrice"
              className="form-input"
              type="number"
              min={0}
              placeholder="e.g. 300"
              value={minPrice}
              onChange={(e) => setMinPrice(e.target.value)}
            />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="maxPrice">
              Max price (two people)
            </label>
            <input
              id="maxPrice"
              className="form-input"
              type="number"
              min={0}
              placeholder="e.g. 1500"
              value={maxPrice}
              onChange={(e) => setMaxPrice(e.target.value)}
            />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="ratingMin">
              Minimum rating
            </label>
            <input
              id="ratingMin"
              className="form-input"
              type="number"
              min={0}
              max={5}
              step={0.1}
              value={ratingMin}
              onChange={(e) => setRatingMin(e.target.value)}
            />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="mood">
              Mood
            </label>
            <select
              id="mood"
              className="form-select"
              value={mood}
              onChange={(e) => setMood(e.target.value as Mood)}
            >
              {MOOD_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="full-width">
            <button type="submit" className="button-primary" disabled={loading}>
              {loading ? "Discovering..." : "Get Recommendations"}
            </button>
            {error && <div className="error-text" style={{ color: "white" }}>{error}</div>}
          </div>
        </form>
      </section>

      <section aria-label="Recommendation results">
        <div className="results-header">
          <h2 className="section-title" style={{ color: "white", marginBottom: 0 }}>Discover Top Places</h2>
          <span className="results-count">
            {loading
              ? "Updating..."
              : results.length > 0
                ? `${results.length} places match your vibe`
                : null}
          </span>
        </div>

        {!hasSearched && !loading && (
          <div className="empty-state" style={{ color: "rgba(255,255,255,0.8)", textAlign: "center", padding: "3rem" }}>
            Start your search to see personalized restaurant picks.
          </div>
        )}

        {hasSearched && !loading && results.length === 0 && (
          <div className="empty-state" style={{ color: "rgba(255,255,255,0.8)", textAlign: "center", padding: "3rem" }}>
            😔 No restaurants found matching your preferences.
          </div>
        )}

        <div className="results-grid">
          {results.map((item) => {
            const { restaurant } = item;
            const cuisineList = Array.isArray(restaurant.cuisines)
              ? restaurant.cuisines
              : typeof restaurant.cuisines === "string"
                ? restaurant.cuisines.split(",").map(c => c.trim())
                : [];

            const primaryCuisine = cuisineList[0] || "Dineout";

            return (
              <article
                key={String(restaurant.restaurant_id)}
                className="restaurant-card"
                onClick={() => setSelectedResult(item)}
              >
                <div className="restaurant-image-container">
                  <img
                    src={getPlaceholderImage(restaurant.cuisines)}
                    alt={restaurant.name || "Restaurant"}
                    className="restaurant-image"
                  />
                </div>
                <div className="restaurant-card-content">
                  <div className="restaurant-name">
                    {restaurant.name ?? "Unnamed restaurant"}
                  </div>

                  {renderBadges(item.matched_factors || {})}

                  <div className="restaurant-location">{restaurant.location}</div>

                  <div className="restaurant-rating-row">
                    <span className="pill pill-primary">{primaryCuisine}</span>
                    {typeof restaurant.rating === "number" && (
                      <span className="pill pill-rating">⭐ {restaurant.rating.toFixed(1)}</span>
                    )}
                  </div>

                  <p className="restaurant-explanation">{item.explanation}</p>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      {/* Detailed Result Modal */}
      {selectedResult && (
        <div className="modal-overlay" onClick={() => setSelectedResult(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <img
              src={getPlaceholderImage(selectedResult.restaurant.cuisines)}
              alt={selectedResult.restaurant.name || "Restaurant"}
              className="modal-image"
            />
            <div className="modal-body">
              <h2 className="modal-title">{selectedResult.restaurant.name || "Unnamed"}</h2>
              <div className="restaurant-location" style={{ fontSize: "1rem", marginBottom: "0.5rem" }}>
                📍 {selectedResult.restaurant.location || "City Centre"}
              </div>

              {renderBadges(selectedResult.matched_factors || {})}

              <div className="modal-meta">
                {typeof selectedResult.restaurant.rating === "number" && (
                  <span className="pill pill-rating" style={{ fontSize: "1rem", padding: "0.5rem 1rem" }}>
                    ⭐ {selectedResult.restaurant.rating.toFixed(1)}
                  </span>
                )}
                <span className="pill pill-primary" style={{ fontSize: "1rem", padding: "0.5rem 1rem" }}>
                  {Array.isArray(selectedResult.restaurant.cuisines)
                    ? selectedResult.restaurant.cuisines[0]
                    : "Dining"
                  }
                </span>
                {typeof selectedResult.restaurant.approx_cost === "number" && (
                  <span className="pill" style={{ fontSize: "1rem", padding: "0.5rem 1rem" }}>
                    ₹{Math.round(selectedResult.restaurant.approx_cost)} for two
                  </span>
                )}
              </div>

              <div style={{ marginBottom: "1.5rem" }}>
                <h3 style={{ fontSize: "0.9rem", color: "#666", textTransform: "uppercase", letterSpacing: "1px", marginBottom: "0.5rem" }}>Cuisines</h3>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                  {(Array.isArray(selectedResult.restaurant.cuisines)
                    ? selectedResult.restaurant.cuisines
                    : [selectedResult.restaurant.cuisines]).map((c: any) => (
                      <span key={String(c)} className="pill">{c}</span>
                    ))}
                </div>
              </div>

              <div className="modal-description">
                <p style={{ fontWeight: 600, color: "#e23744", marginBottom: "0.5rem" }}>Why you&apos;ll love this:</p>
                {selectedResult.explanation}
              </div>
            </div>
            <div className="modal-footer">
              <button className="button-close" onClick={() => setSelectedResult(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
