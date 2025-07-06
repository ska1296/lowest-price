"""
Main workflow orchestration using LangGraph - fully dynamic, config-free approach.
"""

import asyncio
from typing import Dict

import httpx
from langgraph.graph import StateGraph, END

from app.models import GraphState
from app.config import settings
# Fully dynamic approach - no caching, no site configs, no tier1 scraping
from app.agents.llm_agents import discover_sites, enhance_query, extract_from_html
from app.agents.product_url_discovery import find_product_urls


def create_workflow() -> StateGraph:
    """Create and compile the workflow graph - fully dynamic, config-free approach."""
    workflow = StateGraph(GraphState)

    # Add nodes - fully dynamic LLM-based approach (no site configs)
    workflow.add_node("site_selection", site_selection_agent)
    workflow.add_node("query_enhancement", query_enhancement_agent)
    workflow.add_node("url_discovery", url_discovery_agent)
    workflow.add_node("llm_extraction", llm_extraction_agent)  # Direct LLM extraction for all sites
    workflow.add_node("consolidation", consolidation_agent)

    # Define the streamlined flow - skip Tier 1 scraping entirely
    workflow.set_entry_point("site_selection")
    workflow.add_edge("site_selection", "query_enhancement")
    workflow.add_edge("query_enhancement", "url_discovery")
    workflow.add_edge("url_discovery", "llm_extraction")  # Direct to LLM extraction
    workflow.add_edge("llm_extraction", "consolidation")
    workflow.add_edge("consolidation", END)

    return workflow.compile()

async def site_selection_agent(state: GraphState) -> GraphState:
    """
    AGENT: This agent is the single source of truth for which sites to check.
    It uses dynamic LLM discovery (no caching for fresh results).
    """
    print("---AGENT: Site Selection---")
    country = state["request"].country.value

    print(f"🔍 Discovering sites for {country} with LLM (no cache)...")
    discovered_sites = await discover_sites(country)
    print(f"🔍 LLM discovered {len(discovered_sites)} sites:")
    for i, site in enumerate(discovered_sites, 1):
        print(f"   {i}. {site['domain']} - {site['base_url']}")
    state["selected_sites"] = discovered_sites

    return state


async def query_enhancement_agent(state: GraphState) -> GraphState:
    """AGENT: Enhance the user query for better search results."""
    print("---AGENT: Query Enhancement---")
    original_query = state["request"].query
    country = state["request"].country.value

    print(f"🔤 Original query: '{original_query}'")
    print(f"🌍 Target country: {country}")

    enhanced_query = await enhance_query(original_query, country)
    state["enhanced_query"] = enhanced_query

    print(f"✨ Enhanced query: '{enhanced_query}'")
    if enhanced_query != original_query:
        print(f"📝 Query was optimized for better search results")
    else:
        print(f"📝 Query was already optimal")

    return state


async def url_discovery_agent(state: GraphState) -> GraphState:
    """AGENT: Finds direct product URLs for each site using SerpAPI."""
    print("---AGENT: Product URL Discovery (via SerpApi)---")
    query = state["enhanced_query"]
    sites = state["selected_sites"]

    print(f"🔍 Searching for '{query}' across {len(sites)} sites...")

    discovered_urls = await find_product_urls(query, sites)
    state["product_urls"] = discovered_urls

    print(f"📍 URL Discovery Results:")
    print(f"   • Total sites searched: {len(sites)}")
    print(f"   • URLs found: {len(discovered_urls)}")

    if discovered_urls:
        print(f"🎯 Discovered product URLs:")
        for i, url_info in enumerate(discovered_urls, 1):
            print(f"   {i}. {url_info['domain']} → {url_info['url']}")
    else:
        print(f"❌ No product URLs found for any site")

    return state

async def llm_extraction_agent(state: GraphState) -> GraphState:
    """AGENT: Direct LLM extraction for discovered product URLs (rate-limited for Gemini free tier)."""
    print("---AGENT: LLM Extraction (Rate Limited)---")

    if not state["product_urls"]:
        print("❌ No URLs to extract from")
        return state

    # Adaptive rate limiting to ensure minimum results
    max_extractions = settings.MAX_SITES_TO_EXTRACT
    min_required = settings.MIN_REQUIRED_RESULTS

    # If we have fewer URLs than minimum required, process all available
    if len(state["product_urls"]) <= min_required:
        urls_to_process = state["product_urls"]
        print(f"📊 Processing all {len(urls_to_process)} URLs (below minimum threshold)")
    else:
        # Use rate limiting but ensure we have enough for minimum results
        urls_to_process = state["product_urls"][:max_extractions]
        print(f"⚠️ Rate limiting: Processing {len(urls_to_process)}/{len(state['product_urls'])} URLs to stay within Gemini limits")

    print(f"🤖 Starting LLM extraction from {len(urls_to_process)} URLs...")
    extraction_tasks = []
    additional_urls = []  # Initialize here to avoid scope issues

    async with httpx.AsyncClient(headers={'User-Agent': 'Mozilla/5.0'}) as client:
        # Fetch HTML for selected URLs
        search_query = state.get("enhanced_query", state["request"].query)
        for url_info in urls_to_process:
            extraction_tasks.append(_extract_from_url(url_info, client, search_query))

        # Execute tasks while client is still open
        results = await asyncio.gather(*extraction_tasks)

    # Process results and filter out CAPTCHA-protected sites
    valid_results = []
    captcha_sites = []

    for result in results:
        if result:
            # Check if result indicates CAPTCHA protection
            if _is_captcha_protected(result):
                captcha_sites.append(result.site_name)
                print(f"🚫 Filtered out {result.site_name}: CAPTCHA protection detected")
                state["tier_stats"]["tier1_fails"] += 1
            else:
                valid_results.append(result)
                state["final_results"].append(result)
                state["tier_stats"]["tier2_success"] += 1
                print(f"✅ Successfully extracted from {result.site_name}: {result.product_name} - {result.currency}{result.price}")
        else:
            state["tier_stats"]["tier1_fails"] += 1

    print(f"📊 Extraction Summary:")
    print(f"   • Total URLs available: {len(state['product_urls'])}")
    print(f"   • URLs processed (rate limited): {len(urls_to_process)}")
    print(f"   • Successful extractions: {len(valid_results)}")
    print(f"   • Failed extractions: {len(results) - len(valid_results)}")
    if captcha_sites:
        print(f"   • CAPTCHA-protected sites filtered: {', '.join(captcha_sites)}")

        # If we don't have enough results and there are more URLs available, try more
        remaining_urls = state["product_urls"][len(urls_to_process):]
        if len(valid_results) < settings.MIN_REQUIRED_RESULTS and remaining_urls:
            additional_needed = settings.MIN_REQUIRED_RESULTS - len(valid_results)
            additional_urls = remaining_urls[:additional_needed]

            print(f"📈 Need {additional_needed} more results. Processing {len(additional_urls)} additional URLs...")

            # Process additional URLs
            additional_tasks = []
            search_query = state.get("enhanced_query", state["request"].query)
            for url_info in additional_urls:
                additional_tasks.append(_extract_from_url(url_info, client, search_query))

            additional_results = await asyncio.gather(*additional_tasks)

            # Add successful additional results
            for result in additional_results:
                if result and result.get("product_name") != "unknown":
                    if not any(site in result.get("site_name", "") for site in captcha_sites):
                        valid_results.append(result)
                        print(f"✅ Additional extraction: {result['product_name']} from {result['site_name']}")

            print(f"📊 After additional processing: {len(valid_results)} total results")

    # Update tier stats to reflect rate limiting
    total_processed = len(urls_to_process) + len(additional_urls)
    state["tier_stats"] = {
        "tier2_success": len(valid_results),
        "tier1_fails": total_processed - len(valid_results),
        "rate_limited": max(0, len(state["product_urls"]) - total_processed)
    }

    return state


async def _extract_from_url(url_info: Dict, client: httpx.AsyncClient, search_query: str = ""):
    """Helper to fetch HTML and extract product data using LLM."""
    try:
        domain = url_info["domain"]
        url = url_info["url"]

        print(f"🌐 Fetching from {domain}...")
        response = await client.get(url, follow_redirects=True, timeout=30)  # Increased timeout
        response.raise_for_status()

        print(f"📄 Received {len(response.text)} characters from {domain}")

        # Use LLM to extract product information with search query context
        result = await extract_from_html(response.text, domain, search_query)
        if result:
            result.link = url  # Set the actual product URL
            print(f"🤖 LLM extraction completed for {domain}: {result.product_name}")
            return result
        else:
            print(f"❌ LLM extraction failed for {domain}: No matching product found")
            return None

    except Exception as e:
        print(f"❌ Failed to fetch/extract from {domain}: {e}")
        return None


def _is_captcha_protected(result) -> bool:
    """Check if the extraction result indicates CAPTCHA protection."""
    if not result:
        return False

    captcha_indicators = [
        "captcha",
        "verification",
        "robot",
        "automated",
        "suspicious activity",
        "verify you are human",
        "security check",
        "please complete",
        "prove you're not a robot"
    ]

    text_to_check = f"{result.product_name} {result.availability}".lower()
    return any(indicator in text_to_check for indicator in captcha_indicators)


# Helper function removed - now using proper tiered approach


async def consolidation_agent(state: GraphState) -> GraphState:
    """AGENT: Consolidate and deduplicate results from LLM extraction."""
    print("---AGENT: Consolidation---")

    # Results are already in final_results from LLM extraction
    all_results = state["final_results"]

    print(f"📦 Processing {len(all_results)} extracted products...")

    if not all_results:
        print("❌ No products to consolidate")
        return state

    # Log all products before deduplication
    print(f"🔍 Products before deduplication:")
    for i, product in enumerate(all_results, 1):
        print(f"   {i}. {product.site_name}: {product.product_name} - {product.currency}{product.price}")

    # More intelligent deduplication - keep results from different sites even if product name is similar
    unique_results = []
    seen_combinations = set()

    for product in all_results:
        # Create a key that includes both product name and site to avoid over-deduplication
        key = f"{product.product_name.lower().strip()}_{product.site_name}"
        if key not in seen_combinations:
            seen_combinations.add(key)
            unique_results.append(product)

    duplicates_removed = len(all_results) - len(unique_results)
    if duplicates_removed > 0:
        print(f"🔄 Removed {duplicates_removed} exact duplicate products")

    # Final deterministic sort by price
    sorted_results = sorted(unique_results, key=lambda p: p.price)
    state["final_results"] = sorted_results

    print(f"✅ Final Results ({len(sorted_results)} products, sorted by price):")
    for i, product in enumerate(sorted_results, 1):
        print(f"   {i}. {product.currency}{product.price} - {product.product_name} ({product.site_name})")

    return state
