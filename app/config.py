"""
Configuration settings for the price comparison application.
"""

import os
from typing import Optional


class Settings:
    """Application settings and configuration."""
    
    # GCP Configuration
    GCP_PROJECT: Optional[str] = os.environ.get("GCLOUD_PROJECT")
    
    # Database Configuration
    DB_FILE: str = "price_comparison.db"
    
    # Cache Configuration
    CACHE_DURATION_HOURS: int = 24
    
    # HTTP Configuration
    HTTP_CLIENT_TIMEOUT: int = 15
    
    # API Configuration
    API_TITLE: str = "Ultimate Price Comparison API"
    API_VERSION: str = "2.0.0"
    
    def __post_init__(self):
        if not self.GCP_PROJECT:
            raise ValueError("GCLOUD_PROJECT environment variable not set.")


# Global settings instance
settings = Settings()

# Validate GCP project on import
if not settings.GCP_PROJECT:
    raise ValueError("GCLOUD_PROJECT environment variable not set.")
