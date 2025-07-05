"""
Main workflow orchestration using LangGraph - fully dynamic, config-free approach.
"""

import asyncio
from typing import Dict

import httpx
from langgraph.graph import StateGraph, END

from app.models import GraphState
from app.core.cache import get_country_sites, cache_country_sites
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
    It uses the dynamic LLM discovery and caching approach.
    """
    print("---AGENT: Site Selection---")
    country = state["request"].country.value
    cached_sites = await get_country_sites(country)

    if cached_sites:
        print(f"Cache HIT for {country}.")
        state["selected_sites"] = cached_sites
    else:
        print(f"Cache MISS for {country}. Discovering sites with LLM.")
        discovered_sites = await discover_sites(country)
        state["selected_sites"] = discovered_sites
        await cache_country_sites(country, discovered_sites)

    return state


async def query_enhancement_agent(state: GraphState) -> GraphState:
    """AGENT: Enhance the user query for better search results."""
    print("---AGENT: Query Enhancement---")
    state["enhanced_query"] = await enhance_query(
        state["request"].query, state["request"].country.value
    )
    print(f"Enhanced query: {state['enhanced_query']}")
    return state


async def url_discovery_agent(state: GraphState) -> GraphState:
    """AGENT: Finds direct product URLs for each site using SerpAPI."""
    print("---AGENT: Product URL Discovery (via SerpApi)---")
    state["product_urls"] = await find_product_urls(state["enhanced_query"], state["selected_sites"])
    print(f"Discovered {len(state['product_urls'])} product URLs.")
    return state

async def llm_extraction_agent(state: GraphState) -> GraphState:
    """AGENT: LLM-based extraction for all discovered product URLs."""
    print("---AGENT: LLM Extraction (All Sites)---")
    extraction_tasks = []

    async with httpx.AsyncClient(headers={'User-Agent': 'Mozilla/5.0'}) as client:
        # Fetch HTML for all discovered URLs
        for url_info in state["product_urls"]:
            extraction_tasks.append(_extract_from_url(url_info, client))

    results = await asyncio.gather(*extraction_tasks)

    # Process results
    for result in results:
        if result:
            state["final_results"].append(result)
            state["tier_stats"]["tier2_success"] += 1
        else:
            state["tier_stats"]["tier1_fails"] += 1  # Count as failed extraction

    print(f"Successfully extracted {len([r for r in results if r])} products from {len(state['product_urls'])} URLs.")
    return state


async def _extract_from_url(url_info: Dict, client: httpx.AsyncClient):
    """Helper to fetch HTML and extract product data using LLM."""
    try:
        domain = url_info["domain"]
        url = url_info["url"]

        print(f"Fetching and extracting from {domain}...")
        response = await client.get(url, follow_redirects=True, timeout=15)
        response.raise_for_status()

        # Use LLM to extract product information
        result = await extract_from_html(response.text, domain)
        if result:
            result.link = url  # Set the actual product URL
            print(f"LLM extraction SUCCESS for {domain}")
            return result
        else:
            print(f"LLM extraction FAILED for {domain}")
            return None

    except Exception as e:
        print(f"Failed to fetch/extract from {url_info.get('domain', 'unknown')}: {e}")
        return None


async def consolidation_agent(state: GraphState) -> GraphState:
    """AGENT: Consolidate and deduplicate results."""
    print("---AGENT: Consolidation---")
    all_results = state["final_results"]  # Results are already in final_results from LLM extraction

    # Simple name-based deduplication
    unique_results = {p.product_name.lower(): p for p in all_results}.values()

    # Final deterministic sort by price
    state["final_results"] = sorted(list(unique_results), key=lambda p: p.price)

    print(f"Final results: {len(state['final_results'])} unique products after deduplication and sorting.")
    return state
