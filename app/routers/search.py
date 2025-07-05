"""
Search API router - handles product search endpoints.
"""

from fastapi import APIRouter, HTTPException

from app.models import ProductSearchRequest, SearchResponse
from app.services.price_comparison_service import search_products as search_service


router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search_products(request: ProductSearchRequest):
    """
    Search for products across multiple e-commerce sites.

    This endpoint orchestrates the entire price comparison workflow:
    1. Site selection and caching
    2. Query enhancement
    3. Multi-tier scraping (BeautifulSoup + LLM fallback)
    4. Result consolidation and deduplication
    5. Price-based sorting

    Args:
        request: Product search request with country, query, and max_results

    Returns:
        SearchResponse with results sorted by price ascending

    Raises:
        HTTPException: For service errors or invalid requests
    """
    try:
        return await search_service(request)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
