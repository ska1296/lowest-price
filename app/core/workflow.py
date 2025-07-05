"""
Main workflow orchestration using LangGraph, now with URL Discovery agent.
"""

import asyncio
from typing import Dict

import httpx
from langgraph.graph import StateGraph, END

from app.models import GraphState
from app.core.cache import get_country_sites, cache_country_sites
from app.agents.site_config import get_site_config
from app.agents.llm_agents import discover_sites, enhance_query, extract_from_html
from app.agents.product_url_discovery import find_product_urls  # NEW AGENT
from app.scrapers.tier1_scraper import scrape_product_page  # NEW SCRAPER


def create_workflow() -> StateGraph:
    """Create and compile the workflow graph."""
    workflow = StateGraph(GraphState)

    # Add nodes
    workflow.add_node("site_selection", site_selection_agent)
    workflow.add_node("query_enhancement", query_enhancement_agent)
    workflow.add_node("url_discovery", url_discovery_agent)  # NEW NODE
    workflow.add_node("scraping", scraping_agent)
    workflow.add_node("healing", healing_agent)
    workflow.add_node("consolidation", consolidation_agent)

    # Define the new flow
    workflow.set_entry_point("site_selection")
    workflow.add_edge("site_selection", "query_enhancement")
    workflow.add_edge("query_enhancement", "url_discovery")  # REROUTE
    workflow.add_edge("url_discovery", "scraping")  # REROUTE
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


async def url_discovery_agent(state: GraphState) -> GraphState:
    """NEW AGENT NODE: Finds direct product URLs for each site."""
    print("---AGENT: Product URL Discovery (via SerpApi)---")
    state["product_urls"] = await find_product_urls(state["enhanced_query"], state["selected_sites"])
    print(f"Discovered {len(state['product_urls'])} product URLs.")
    return state

async def scraping_agent(state: GraphState) -> GraphState:
    """MODIFIED AGENT: Scrapes direct product URLs instead of search pages."""
    print("---AGENT: Tier 1 Scraping (Product Pages)---")
    urls_to_scrape = state["product_urls"]

    async with httpx.AsyncClient(headers={'User-Agent': 'Mozilla/5.0'}) as client:
        tasks = [_scrape_url_task(site_info, client) for site_info in urls_to_scrape]
        results = await asyncio.gather(*tasks)

    for status, result in results:
        if status == "success":
            state["successful_scrapes"].append(result)
            state["tier_stats"]["tier1_success"] += 1
        else:
            state["failed_scrapes"].append(result)
            state["tier_stats"]["tier1_fails"] += 1

    return state

async def _scrape_url_task(site_info: Dict, client: httpx.AsyncClient):
    """Helper to manage Tier 1 scraping for a single product URL."""
    domain = site_info["domain"]
    url = site_info["url"]
    config = get_site_config(domain)

    if not config:
        # If no Tier 1 config, fail immediately to Tier 2 healing
        print(f"No Tier 1 config for {domain}. Failing to Tier 2.")
        return "failure", {"reason": "no_config", "site_info": site_info}

    try:
        product = await scrape_product_page(url, config, client)
        print(f"Tier 1 SUCCESS for {domain}.")
        return "success", product
    except Exception as e:
        print(f"Tier 1 FAILED for {domain}: {e}. Failing to Tier 2.")
        # On failure, we need to fetch the HTML for the healing agent
        try:
            response = await client.get(url, follow_redirects=True)
            return "failure", {"reason": "scrape_failed", "site_info": site_info, "html": response.text, "error": str(e)}
        except Exception as fetch_e:
            return "failure", {"reason": "fetch_failed", "site_info": site_info, "error": str(fetch_e)}


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
        # We need to fetch the HTML if it wasn't already fetched during the scrape failure
        if "html" not in failure:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(failure["site_info"]["url"])
                    failure["html"] = response.text
            except Exception:
                continue  # Skip if we can't even fetch the page

        site_name = failure["site_info"]["domain"]
        healing_tasks.append(extract_from_html(failure["html"], site_name))

    results = await asyncio.gather(*healing_tasks)
    for result in results:
        if result:
            failure_info = next(
                (f for f in state["failed_scrapes"] if f["site_info"]["domain"] == result.site_name),
                None
            )
            if failure_info:
                result.link = failure_info['site_info']['url']
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
