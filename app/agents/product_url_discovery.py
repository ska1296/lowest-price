"""
NEW AGENT: Uses a search engine API (SerpApi) to find direct product URLs.
"""

import asyncio
import json
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
    """Synchronous wrapper for SerpApi search with detailed logging."""
    domain = site_info["domain"]
    try:
        print(f"🔍 Searching Google for '{query}' on {domain}...")
        params = {
            "q": query,
            "api_key": settings.SERPAPI_API_KEY,
            "engine": "google",
            "google_domain": "google.com",  # Can be customized per country
        }

        print(f"📋 SerpAPI Request Parameters:")
        print(f"   • Query: {params['q']}")
        print(f"   • Engine: {params['engine']}")
        print(f"   • Google Domain: {params['google_domain']}")
        print(f"   • API Key: {params['api_key'][:10]}...{params['api_key'][-4:]}")

        search = GoogleSearch(params)
        results = search.get_dict()

        # Log the full SerpAPI response for debugging
        print(f"📊 SerpAPI Response for {domain}:")
        print(f"   • Response keys: {list(results.keys())}")

        # Log search information if available
        if "search_information" in results:
            search_info = results["search_information"]
            print(f"   • Search Information:")
            print(f"     - Query displayed: {search_info.get('query_displayed', 'N/A')}")
            print(f"     - Total results: {search_info.get('total_results', 'N/A')}")
            print(f"     - Time taken: {search_info.get('time_taken_displayed', 'N/A')}")

        # Log organic results details
        if "organic_results" in results:
            organic_count = len(results["organic_results"])
            print(f"   • Organic results found: {organic_count}")

            if organic_count > 0:
                for i, result in enumerate(results["organic_results"][:3]):  # Show first 3
                    print(f"     {i+1}. Title: {result.get('title', 'N/A')[:60]}...")
                    print(f"        Link: {result.get('link', 'N/A')}")
                    print(f"        Snippet: {result.get('snippet', 'N/A')[:80]}...")

                top_link = results["organic_results"][0].get("link")
                if top_link:
                    print(f"✅ Found URL for {domain}: {top_link}")
                    return {"domain": domain, "url": top_link}
                else:
                    print(f"❌ No URL found in first organic result for {domain}")
            else:
                print(f"❌ Organic results array is empty for {domain}")
        else:
            print(f"❌ No 'organic_results' key in response for {domain}")

        # Log any error messages from SerpAPI
        if "error" in results:
            print(f"🚨 SerpAPI Error for {domain}: {results['error']}")

        # Log any other interesting keys
        other_keys = [k for k in results.keys() if k not in ['organic_results', 'search_information', 'error']]
        if other_keys:
            print(f"   • Other response keys: {other_keys}")

        # Log the raw response for debugging (truncated)
        raw_response = json.dumps(results, indent=2)
        if len(raw_response) > 1000:
            print(f"   • Raw response (truncated): {raw_response[:500]}...{raw_response[-500:]}")
        else:
            print(f"   • Raw response: {raw_response}")

    except Exception as e:
        print(f"❌ SerpApi search failed for {domain}: {e}")
        print(f"   • Exception type: {type(e).__name__}")
        import traceback
        print(f"   • Traceback: {traceback.format_exc()}")

    return None
