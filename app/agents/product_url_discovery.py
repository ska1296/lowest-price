"""
NEW AGENT: Uses a search engine API (SerpApi) to find direct product URLs.
"""

import asyncio
from typing import List, Dict, Optional
from serpapi import GoogleSearch

from app.config import settings


async def find_product_urls(query: str, sites: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    For each site, search Google for the product and get the top URL.

    Args:
        query: The enhanced product query.
        sites: List of target site dictionaries from the SiteSelectionAgent.

    Returns:
        A list of dictionaries, each containing the site domain and the discovered product URL.
    """
    loop = asyncio.get_event_loop()
    tasks = []
    for site in sites:
        # Construct a site-specific search query for Google
        search_query = f'{query} site:{site["domain"]}'
        tasks.append(loop.run_in_executor(None, _search_for_site, search_query, site))
    
    results = await asyncio.gather(*tasks)
    # Filter out any searches that failed
    return [res for res in results if res]


def _search_for_site(query: str, site_info: Dict[str, str]) -> Optional[Dict[str, str]]:
    """Synchronous wrapper for SerpApi search."""
    try:
        params = {
            "q": query,
            "api_key": settings.SERPAPI_API_KEY,
            "engine": "google",
            "google_domain": "google.com",  # Can be customized per country
        }
        search = GoogleSearch(params)
        results = search.get_dict()
        
        # Get the link from the first organic result
        if "organic_results" in results and results["organic_results"]:
            top_link = results["organic_results"][0].get("link")
            if top_link:
                return {"domain": site_info["domain"], "url": top_link}
    except Exception as e:
        print(f"SerpApi search failed for {site_info['domain']}: {e}")
    return None
