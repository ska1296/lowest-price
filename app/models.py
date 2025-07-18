"""
Pydantic models and data structures for the price comparison application.
"""

from typing import TypedDict, List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class CountryCode(str, Enum):
    """Supported country codes."""
    US = "US"
    IN = "IN"
    GB = "GB"
    CA = "CA"
    AU = "AU"
    DE = "DE"


class ProductSearchRequest(BaseModel):
    """Request model for product search."""
    country: CountryCode
    query: str = Field(..., min_length=3, max_length=200)


class ProductResult(BaseModel):
    """Model representing a single product result."""
    link: str
    price: float
    currency: str
    product_name: str
    site_name: str
    availability: str = "unknown"
    rating: Optional[float] = None
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)


class SearchResponse(BaseModel):
    """Response model for product search."""
    success: bool
    total_results: int
    search_time_ms: int
    results: List[ProductResult]
    errors: List[str] = []
    metadata: Dict[str, Any] = {}


class GraphState(TypedDict):
    """State object for the LangGraph workflow - fully dynamic LLM-based approach."""
    request: ProductSearchRequest
    start_time: float
    selected_sites: List[Dict[str, str]]
    enhanced_query: str
    product_urls: List[Dict[str, str]]  # Stores discovered product URLs from SerpAPI
    final_results: List[ProductResult]  # All results go directly here from LLM extraction
    errors: List[str]
    tier_stats: Dict[str, int]  # Track extraction success/failure stats
