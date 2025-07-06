"""
Configuration settings for the price comparison application.
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings and configuration."""

    # Google AI Studio Configuration (preferred over Vertex AI)
    GOOGLE_AI_API_KEY: Optional[str] = os.environ.get("GOOGLE_AI_API_KEY")

    # GCP Configuration - fallback to Vertex AI if Google AI Studio not available
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    # SerpApi Configuration
    SERPAPI_API_KEY: Optional[str] = os.environ.get("SERPAPI_API_KEY")

    # Rate Limiting Configuration for Gemini Free Tier (10 req/min)
    GEMINI_RATE_LIMIT_PER_MINUTE: int = 10
    MAX_SITES_TO_EXTRACT: int = 5  # Increased to get minimum 3 results
    ENABLE_STATIC_SITE_CACHE: bool = True  # Cache common sites to reduce LLM calls
    MIN_REQUIRED_RESULTS: int = 3  # Minimum results required per request

    # Cache Configuration (disabled)
    # DB_FILE: str = "price_comparison.db"  # Caching removed
    # CACHE_DURATION_HOURS: int = 24  # Caching removed
    
    # HTTP Configuration
    HTTP_CLIENT_TIMEOUT: int = 15
    
    # API Configuration
    API_TITLE: str = "Ultimate Price Comparison API"
    API_VERSION: str = "3.0.0"

    def validate_required_vars(self):
        """Validate that all required environment variables are set."""
        missing = []

        # Require either Google AI Studio API key OR Vertex AI credentials
        if not self.GOOGLE_AI_API_KEY and not self.GOOGLE_APPLICATION_CREDENTIALS:
            missing.append("GOOGLE_AI_API_KEY or GOOGLE_APPLICATION_CREDENTIALS")

        if not self.SERPAPI_API_KEY:
            missing.append("SERPAPI_API_KEY")

        if missing:
            raise ValueError(f"Required environment variables not set: {', '.join(missing)}")


# Global settings instance
settings = Settings()

# Validate required environment variables on import (only warn, don't fail)
import warnings

if not settings.GOOGLE_AI_API_KEY and not settings.GOOGLE_APPLICATION_CREDENTIALS:
    warnings.warn("Neither GOOGLE_AI_API_KEY nor GOOGLE_APPLICATION_CREDENTIALS environment variable set. Set one before running the application.")
if not settings.SERPAPI_API_KEY:
    warnings.warn("SERPAPI_API_KEY environment variable not set. Set it before running the application.")
