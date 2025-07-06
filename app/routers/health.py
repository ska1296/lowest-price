"""
Health check API router.
"""

import time
from typing import Dict, Any
from fastapi import APIRouter

from app import __version__
from app.services.price_comparison_service import get_health_status
from app.utils.rate_limiter import gemini_rate_limiter
from app.config import settings


router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint.

    Returns:
        Dictionary with health status and version information
    """
    return await get_health_status()


@router.get("/rate-limit-status")
async def rate_limit_status() -> Dict[str, Any]:
    """
    Check current rate limit status for Gemini API.

    Returns:
        Dictionary with rate limiting information
    """
    now = time.time()

    # Count requests in the last minute
    recent_requests = [req for req in gemini_rate_limiter.requests if now - req <= 60]

    return {
        "max_requests_per_minute": settings.GEMINI_RATE_LIMIT_PER_MINUTE,
        "requests_in_last_minute": len(recent_requests),
        "remaining_requests": max(0, settings.GEMINI_RATE_LIMIT_PER_MINUTE - len(recent_requests)),
        "rate_limited": len(recent_requests) >= settings.GEMINI_RATE_LIMIT_PER_MINUTE,
        "max_sites_per_request": settings.MAX_SITES_TO_EXTRACT,
        "static_cache_enabled": settings.ENABLE_STATIC_SITE_CACHE,
        "optimization_status": "Optimized for Gemini free tier (10 req/min)"
    }


@router.get("/")
async def root() -> Dict[str, Any]:
    """
    Root endpoint with API information.

    Returns:
        Dictionary with API metadata and available endpoints
    """
    return {
        "title": "Ultimate Price Comparison API",
        "version": __version__,
        "description": "A robust, backend-only tool for reliable product price comparison",
        "endpoints": {
            "search": "/search",
            "health": "/health",
            "docs": "/docs",
            "redoc": "/redoc"
        },
        "features": [
            "Multi-country support",
            "Intelligent site discovery",
            "Self-healing scraping with LLM fallback",
            "Price-based result ranking",
            "Caching for performance"
        ]
    }
