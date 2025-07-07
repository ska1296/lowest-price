"""
Price comparison service - main business logic orchestrator.
"""

import asyncio
from typing import Dict, Any

from app import __version__
from app.models import ProductSearchRequest, SearchResponse, GraphState
from app.core.workflow import create_workflow


# Global workflow instance
_workflow = None
_initialized = False


async def initialize():
    """Initialize the service and its dependencies."""
    global _workflow, _initialized
    if not _initialized:
        _workflow = create_workflow()
        _initialized = True


def is_ready() -> bool:
    """Check if the service is ready to handle requests."""
    return _initialized and _workflow is not None


async def search_products(request: ProductSearchRequest) -> SearchResponse:
    """
    Search for products across multiple e-commerce sites.

    Args:
        request: Product search request with country, query, and max_results

    Returns:
        SearchResponse with results sorted by price

    Raises:
        RuntimeError: If service is not initialized
        Exception: For processing errors
    """
    if not is_ready():
        raise RuntimeError("Service not initialized. Call initialize() first.")

    start_time = asyncio.get_event_loop().time()

    # Create initial state for the workflow
    initial_state = GraphState(
        request=request,
        start_time=start_time,
        selected_sites=[],
        enhanced_query="",
        product_urls=[],           # Discovered product URLs from SerpAPI
        final_results=[],          # All results go directly here from LLM extraction
        errors=[],
        tier_stats={"tier2_success": 0, "tier1_fails": 0}  # Only track LLM extraction stats
    )

    # Execute the workflow
    final_state = await _workflow.ainvoke(initial_state, {"recursion_limit": 10})

    # Calculate metrics
    search_time_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
    results = final_state.get("final_results", [])  # Return all results, no max_results limit

    # Build response
    return SearchResponse(
        success=True,
        total_results=len(results),
        search_time_ms=search_time_ms,
        results=results,
        errors=final_state.get("errors", []),
        metadata={
            "enhanced_query": final_state.get("enhanced_query"),
            "sites_checked": len(final_state.get("selected_sites", [])),
            "tier_stats": final_state.get("tier_stats")
        }
    )


async def get_health_status() -> Dict[str, Any]:
    """
    Get service health status.

    Returns:
        Dictionary with health information
    """
    return {
        "status": "healthy" if is_ready() else "not_ready",
        "version": __version__,
        "initialized": _initialized,
        "workflow_ready": _workflow is not None
    }
