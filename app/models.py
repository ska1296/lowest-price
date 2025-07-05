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
    max_results: int = Field(default=5, ge=1, le=20)


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
    """State object for the LangGraph workflow."""
    request: ProductSearchRequest
    start_time: float
    selected_sites: List[Dict[str, str]]
    enhanced_query: str
    product_urls: List[Dict[str, str]]  # NEW: Stores discovered product URLs
    successful_scrapes: List[ProductResult]
    failed_scrapes: List[Dict[str, Any]]
    healed_results: List[ProductResult]
    final_results: List[ProductResult]
    errors: List[str]
    tier_stats: Dict[str, int]
