"""
Main workflow orchestration using LangGraph - fully dynamic, config-free approach.
"""

import asyncio
from typing import Dict

import httpx
from langgraph.graph import StateGraph, END

from app.models import GraphState
# Caching removed - always use fresh LLM discovery
from app.agents.llm_agents import discover_sites, enhance_query, extract_from_html
from app.agents.product_url_discovery import find_product_urls


def create_workflow() -> StateGraph:
    """Create and compile the workflow graph - fully dynamic, config-free approach."""
    workflow = StateGraph(GraphState)

    # Add nodes - removed Tier 1 scraping, go directly to LLM extraction
    workflow.add_node("site_selection", site_selection_agent)
    workflow.add_node("query_enhancement", query_enhancement_agent)
    workflow.add_node("url_discovery", url_discovery_agent)
    workflow.add_node("llm_extraction", llm_extraction_agent)  # Renamed from "healing"
    workflow.add_node("consolidation", consolidation_agent)

    # Define the streamlined flow: Site Selection → Query Enhancement → URL Discovery → LLM Extraction → Consolidation
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
    """AGENT: LLM-based extraction for all discovered product URLs."""
    print("---AGENT: LLM Extraction (All Sites)---")

    if not state["product_urls"]:
        print("❌ No URLs to extract from")
        return state

    print(f"🤖 Starting LLM extraction from {len(state['product_urls'])} URLs...")
    extraction_tasks = []

    async with httpx.AsyncClient(headers={'User-Agent': 'Mozilla/5.0'}) as client:
        # Fetch HTML for all discovered URLs
        for url_info in state["product_urls"]:
            extraction_tasks.append(_extract_from_url(url_info, client))

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
    print(f"   • Total URLs processed: {len(state['product_urls'])}")
    print(f"   • Successful extractions: {len(valid_results)}")
    print(f"   • Failed extractions: {len(results) - len(valid_results)}")
    if captcha_sites:
        print(f"   • CAPTCHA-protected sites filtered: {', '.join(captcha_sites)}")

    return state


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


async def _extract_from_url(url_info: Dict, client: httpx.AsyncClient):
    """Helper to fetch HTML and extract product data using LLM."""
    try:
        domain = url_info["domain"]
        url = url_info["url"]

        print(f"🌐 Fetching from {domain}...")
        response = await client.get(url, follow_redirects=True, timeout=15)
        response.raise_for_status()

        print(f"📄 Received {len(response.text)} characters from {domain}")

        # Use LLM to extract product information
        result = await extract_from_html(response.text, domain)
        if result:
            result.link = url  # Set the actual product URL
            print(f"🤖 LLM extraction completed for {domain}")
            return result
        else:
            print(f"❌ LLM extraction failed for {domain}: No product data found")
            return None

    except Exception as e:
        print(f"❌ Failed to fetch/extract from {domain}: {e}")
        return None


async def consolidation_agent(state: GraphState) -> GraphState:
    """AGENT: Consolidate and deduplicate results."""
    print("---AGENT: Consolidation---")
    all_results = state["final_results"]  # Results are already in final_results from LLM extraction

    print(f"📦 Processing {len(all_results)} extracted products...")

    if not all_results:
        print("❌ No products to consolidate")
        return state

    # Log all products before deduplication
    print(f"🔍 Products before deduplication:")
    for i, product in enumerate(all_results, 1):
        print(f"   {i}. {product.site_name}: {product.product_name} - {product.currency}{product.price}")

    # Simple name-based deduplication
    unique_results = {p.product_name.lower(): p for p in all_results}.values()

    duplicates_removed = len(all_results) - len(unique_results)
    if duplicates_removed > 0:
        print(f"🔄 Removed {duplicates_removed} duplicate products")

    # Final deterministic sort by price
    sorted_results = sorted(list(unique_results), key=lambda p: p.price)
    state["final_results"] = sorted_results

    print(f"✅ Final Results ({len(sorted_results)} products, sorted by price):")
    for i, product in enumerate(sorted_results, 1):
        print(f"   {i}. {product.currency}{product.price} - {product.product_name} ({product.site_name})")

    return state
