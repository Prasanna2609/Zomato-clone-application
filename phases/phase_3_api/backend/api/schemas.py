from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MoodEnum(str, Enum):
    DATE_NIGHT = "date_night"
    WORK_CAFE = "work_cafe"
    FAMILY_DINING = "family_dining"
    CASUAL_HANGOUT = "casual_hangout"
    COMFORT_FOOD = "comfort_food"


class PriceRangeRequest(BaseModel):
    min_price: Optional[float] = Field(default=None, ge=0)
    max_price: Optional[float] = Field(default=None, ge=0)


class UserPreferenceRequest(BaseModel):
    location: str
    cuisines: List[str] = Field(default_factory=list)
    price_range: Optional[PriceRangeRequest] = None
    rating_min: float = Field(..., ge=0.0)
    mood: MoodEnum


class RestaurantInfo(BaseModel):
    restaurant_id: Any
    name: Optional[str] = None
    location: Optional[str] = None
    cuisines: Optional[Any] = None
    rating: Optional[float] = None
    approx_cost: Optional[float] = None


class RecommendationResponse(BaseModel):
    restaurant: RestaurantInfo
    score: float
    matched_factors: Dict[str, Any]
    explanation: str


class OptionsResponse(BaseModel):
    locations: List[str]
    cuisines: List[str]

