"""
Health check API router.
"""

from typing import Dict, Any
from fastapi import APIRouter

from app import __version__
from app.services.price_comparison_service import get_health_status


router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint.

    Returns:
        Dictionary with health status and version information
    """
    return await get_health_status()


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
