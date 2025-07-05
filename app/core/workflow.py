"""
Main workflow orchestration using LangGraph.
"""

import asyncio
from typing import Dict
from urllib.parse import quote

import httpx
from langgraph.graph import StateGraph, END

from app.config import settings
from app.models import GraphState
from app.core.cache import get_country_sites, cache_country_sites
from app.agents.site_config import get_site_config
from app.agents.llm_agents import discover_sites, enhance_query, extract_from_html
from app.scrapers.tier1_scraper import scrape_site


def create_workflow() -> StateGraph:
    """Create and compile the workflow graph."""
    workflow = StateGraph(GraphState)

    # Add nodes
    workflow.add_node("site_selection", site_selection_agent)
    workflow.add_node("query_enhancement", query_enhancement_agent)
    workflow.add_node("scraping", scraping_agent)
    workflow.add_node("healing", healing_agent)
    workflow.add_node("consolidation", consolidation_agent)

    # Define flow
    workflow.set_entry_point("site_selection")
    workflow.add_edge("site_selection", "query_enhancement")
    workflow.add_edge("query_enhancement", "scraping")
    workflow.add_conditional_edges(
        "scraping",
        should_heal,
        {"continue_to_heal": "healing", "skip_to_consolidate": "consolidation"}
    )
    workflow.add_edge("healing", "consolidation")
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

async def scraping_agent(state: GraphState) -> GraphState:
    """
    AGENT: This agent attempts a Tier 1 scrape for each site discovered
    by the SiteSelectionAgent. It uses the static SiteConfigManager to find
    the correct selectors. If a site has no config or fails, it's passed to Tier 2.
    """
    print("---AGENT: Tier 1 Scraping---")
    query = state["enhanced_query"]
    sites = state["selected_sites"]

    async with httpx.AsyncClient(headers={'User-Agent': 'Mozilla/5.0'}) as client:
        tasks = [_scrape_site_task(site, query, client) for site in sites]
        results = await asyncio.gather(*tasks)

    for status, result in results:
        if status == "success":
            state["successful_scrapes"].extend(result)
            state["tier_stats"]["tier1_success"] += 1
        else:
            state["failed_scrapes"].append(result)
            state["tier_stats"]["tier1_fails"] += 1

    return state

async def _scrape_site_task(site: Dict, query: str, client: httpx.AsyncClient):
    """Helper to manage Tier 1 scraping for a single site."""
    site_domain = site["domain"]
    config = get_site_config(site_domain)

    if not config:
        print(f"No Tier 1 config for {site_domain}. Failing to Tier 2.")
        # We must still fetch the HTML for the healing agent
        try:
            # A generic search URL fallback
            search_url = f"{site['base_url']}/search?q={quote(query)}"
            response = await client.get(search_url, follow_redirects=True)
            return "failure", {"reason": "no_config", "site": site, "html": response.text}
        except Exception as fetch_e:
            return "failure", {"reason": "fetch_failed_no_config", "site": site, "error": str(fetch_e)}

    try:
        products = await scrape_site(config, query, client)
        print(f"Tier 1 SUCCESS for {site_domain}.")
        return "success", products
    except Exception as e:
        print(f"Tier 1 FAILED for {site_domain}: {e}. Failing to Tier 2.")
        try:
            search_url = config['search_url_template'].format(query=quote(query))
            response = await client.get(search_url, follow_redirects=True)
            return "failure", {"reason": "scrape_failed", "site": site, "html": response.text, "error": str(e)}
        except Exception as fetch_e:
            return "failure", {"reason": "fetch_failed", "site": site, "error": str(fetch_e)}


def should_heal(state: GraphState) -> str:
    """Conditional edge router."""
    if state["failed_scrapes"]:
        return "continue_to_heal"
    return "skip_to_consolidate"

async def healing_agent(state: GraphState) -> GraphState:
    """AGENT: Tier 2 healing using LLM extraction."""
    print("---AGENT: Tier 2 Healing---")
    healing_tasks = []

    for failure in state["failed_scrapes"]:
        if failure.get("html"):
            site_name = failure["site"]["domain"]
            healing_tasks.append(extract_from_html(failure["html"], site_name))

    results = await asyncio.gather(*healing_tasks)
    for result in results:
        if result:
            failure_info = next(
                (f for f in state["failed_scrapes"] if f["site"]["domain"] == result.site_name),
                None
            )
            if failure_info:
                result.link = failure_info['site']['base_url']
            state["healed_results"].append(result)
            state["tier_stats"]["tier2_success"] += 1

    return state


async def consolidation_agent(state: GraphState) -> GraphState:
    """AGENT: Consolidate and deduplicate results."""
    print("---AGENT: Consolidation---")
    all_results = state["successful_scrapes"] + state["healed_results"]

    # Simple name-based deduplication
    unique_results = {p.product_name.lower(): p for p in all_results}.values()

    # Final deterministic sort by price
    state["final_results"] = sorted(list(unique_results), key=lambda p: p.price)

    return state
