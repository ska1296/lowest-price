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

    # GCP Configuration - only need service account credentials
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    # SerpApi Configuration
    SERPAPI_API_KEY: Optional[str] = os.environ.get("SERPAPI_API_KEY")

    # Database Configuration
    DB_FILE: str = "price_comparison.db"
    
    # Cache Configuration
    CACHE_DURATION_HOURS: int = 24
    
    # HTTP Configuration
    HTTP_CLIENT_TIMEOUT: int = 15
    
    # API Configuration
    API_TITLE: str = "Ultimate Price Comparison API"
    API_VERSION: str = "3.0.0"

    def validate_required_vars(self):
        """Validate that all required environment variables are set."""
        missing = []
        if not self.GOOGLE_APPLICATION_CREDENTIALS:
            missing.append("GOOGLE_APPLICATION_CREDENTIALS")
        if not self.SERPAPI_API_KEY:
            missing.append("SERPAPI_API_KEY")

        if missing:
            raise ValueError(f"Required environment variables not set: {', '.join(missing)}")


# Global settings instance
settings = Settings()

# Validate required environment variables on import (only warn, don't fail)
import warnings

if not settings.GOOGLE_APPLICATION_CREDENTIALS:
    warnings.warn("GOOGLE_APPLICATION_CREDENTIALS environment variable not set. Set it before running the application.")
if not settings.SERPAPI_API_KEY:
    warnings.warn("SERPAPI_API_KEY environment variable not set. Set it before running the application.")
