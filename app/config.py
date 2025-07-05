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
    
    # GCP Configuration
    GCP_PROJECT: Optional[str] = os.environ.get("GCLOUD_PROJECT")
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

    def __post_init__(self):
        if not self.GCP_PROJECT:
            raise ValueError("GCLOUD_PROJECT environment variable not set.")
        if not self.GOOGLE_APPLICATION_CREDENTIALS:
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable not set.")
        if not self.SERPAPI_API_KEY:
            raise ValueError("SERPAPI_API_KEY environment variable not set.")


# Global settings instance
settings = Settings()

# Validate required environment variables on import
if not settings.GCP_PROJECT:
    raise ValueError("GCLOUD_PROJECT environment variable not set.")
if not settings.GOOGLE_APPLICATION_CREDENTIALS:
    raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable not set.")
if not settings.SERPAPI_API_KEY:
    raise ValueError("SERPAPI_API_KEY environment variable not set.")
