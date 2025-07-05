# ==============================================================================
# Part 0: Project Setup
# ==============================================================================
# Description: This single file combines all modules for a complete, runnable application.
# To run:
# 1. pip install -r requirements.txt (see below)
# 2. Set GCLOUD_PROJECT environment variable: export GCLOUD_PROJECT="your-gcp-project-id"
# 3. Run with uvicorn: uvicorn main:app --reload

# requirements.txt
"""
fastapi==0.111.0
uvicorn[standard]==0.29.0
langgraph==0.0.66
langchain==0.2.1
langchain-google-vertexai==1.0.4
pydantic==2.7.1
beautifulsoup4==4.12.3
httpx==0.27.0
lxml==5.2.2
"""

import os
import json
import sqlite3
import httpx
import asyncio
import re
from datetime import datetime, timedelta
from typing import TypedDict, List, Optional, Dict, Any
from enum import Enum
from contextlib import asynccontextmanager
from urllib.parse import quote, urljoin

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from bs4 import BeautifulSoup
from langgraph.graph import StateGraph, END
from langchain_core.pydantic_v1 import BaseModel as V1BaseModel
from langchain_google_vertexai import ChatVertexAI

# --- Configuration ---
GCP_PROJECT = os.environ.get("GCLOUD_PROJECT")
if not GCP_PROJECT:
    raise ValueError("GCLOUD_PROJECT environment variable not set.")

DB_FILE = "price_comparison.db"
CACHE_DURATION_HOURS = 24
HTTP_CLIENT_TIMEOUT = 15


# ==============================================================================
# Part 1: Models
# ==============================================================================

class CountryCode(str, Enum):
    US = "US"
    IN = "IN"
    GB = "GB"
    CA = "CA"
    AU = "AU"
    DE = "DE"


class ProductSearchRequest(BaseModel):
    country: CountryCode
    query: str = Field(..., min_length=3, max_length=200)
    max_results: int = Field(default=5, ge=1, le=20)


class ProductResult(BaseModel):
    link: str
    price: float
    currency: str
    product_name: str
    site_name: str
    availability: str = "unknown"
    rating: Optional[float] = None
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)


class SearchResponse(BaseModel):
    success: bool
    total_results: int
    search_time_ms: int
    results: List[ProductResult]
    errors: List[str] = []
    metadata: Dict[str, Any] = {}


class GraphState(TypedDict):
    request: ProductSearchRequest
    start_time: float
    selected_sites: List[Dict[str, str]]
    enhanced_query: str
    successful_scrapes: List[ProductResult]
    failed_scrapes: List[Dict[str, Any]]
    healed_results: List[ProductResult]
    final_results: List[ProductResult]
    errors: List[str]
    tier_stats: Dict[str, int]


# ==============================================================================
# Part 2: Caching and Scraper Configuration
# ==============================================================================

class CacheManager:
    """A unified cache for sites, as per the ultimate plan."""

    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                           CREATE TABLE IF NOT EXISTS country_sites
                           (
                               country
                               TEXT
                               PRIMARY
                               KEY,
                               sites
                               TEXT,
                               last_updated
                               TIMESTAMP
                               DEFAULT
                               CURRENT_TIMESTAMP
                           )
                           """)
            conn.commit()

    async def get_country_sites(self, country: str) -> Optional[List[Dict]]:
        loop = asyncio.get_event_loop()

        def db_read():
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT sites, last_updated FROM country_sites WHERE country = ?", (country,))
                row = cursor.fetchone()
                if row:
                    sites_json, last_updated_str = row
                    last_updated = datetime.fromisoformat(last_updated_str)
                    if datetime.utcnow() - last_updated < timedelta(hours=CACHE_DURATION_HOURS):
                        return json.loads(sites_json)
            return None

        return await loop.run_in_executor(None, db_read)

    async def cache_country_sites(self, country: str, sites: List[Dict]):
        loop = asyncio.get_event_loop()

        def db_write():
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "REPLACE INTO country_sites (country, sites, last_updated) VALUES (?, ?, ?)",
                    (country, json.dumps(sites), datetime.utcnow().isoformat())
                )
                conn.commit()

        await loop.run_in_executor(None, db_write)


class SiteConfigManager:
    """
    Manages static configurations for Tier 1 scrapers.
    This class does NOT know which sites belong to which country.
    It only provides the 'how-to' for scraping a known site.
    """

    def __init__(self):
        self.configs = {
            "books.toscrape.com": {
                "name": "Books To Scrape",
                "search_url_template": "http://books.toscrape.com/catalogue/search.html?q={query}",
                "base_url": "http://books.toscrape.com",
                "selectors": {
                    "container": "article.product_pod",
                    "title": "h3 a",
                    "price": "p.price_color",
                    "link": "h3 a",
                }
            }
            # Add more pre-written Tier 1 scraper configs here for other sites.
        }

    def get_config(self, site_domain: str) -> Optional[Dict]:
        return self.configs.get(site_domain)


# ==============================================================================
# Part 3: LLM Agents and Tiered Scrapers
# ==============================================================================

class ProductInfoTool(V1BaseModel):
    """A tool to extract structured product information from HTML text."""
    product_name: str = Field(description="The full name of the product.")
    price: float = Field(description="The price of the product as a float.")
    currency: str = Field(description="The currency symbol or code (e.g., £, GBP).")
    availability: str = Field(description="Availability status, e.g., 'in-stock', 'out-of-stock'.")


class LLMAgents:
    """Collection of LLM agents, using true structured output."""

    def __init__(self):
        self.llm = ChatVertexAI(project=GCP_PROJECT, model_name="gemini-1.5-flash-001", temperature=0)
        self.tool_llm = self.llm.with_structured_output(ProductInfoTool, method="tool_calling")

    async def discover_sites(self, country: str) -> List[Dict]:
        """Agent: Dynamically discover sites using the LLM."""
        prompt = f"""You are an e-commerce expert. Identify the top 3 most popular e-commerce websites for buying new consumer electronics in the country with code '{country}'.
Also, for this demo, include 'books.toscrape.com'.
Return ONLY a JSON list of objects, each with a 'domain' and 'base_url' key. Example: [{"domain": "amazon.com", "base_url": "https://www.amazon.com"}]"""
        response = await self.llm.ainvoke(prompt)
        try:
            match = re.search(r'\[.*\]', response.content, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return []
        except (json.JSONDecodeError, TypeError):
            return []

    async def enhance_query(self, query: str, country: str) -> str:
        prompt = f"""You are a search optimization expert. Transform the user's query into an optimized search term for e-commerce sites.
Original query: "{query}"
Target country: {country}
Return ONLY the enhanced query string, no explanation."""
        response = await self.llm.ainvoke(prompt)
        return response.content.strip().strip('"\'')

    async def extract_from_html(self, html: str, site_name: str) -> Optional[ProductResult]:
        """Agent: Tier 2 Extraction using true function calling."""
        prompt = f"From this HTML of {site_name}, find the most relevant product and extract its details using the provided tool. HTML: \n\n{html[:8000]}"
        try:
            response: ProductInfoTool = await self.tool_llm.ainvoke(prompt)
            return ProductResult(
                product_name=response.product_name,
                price=response.price,
                currency=response.currency,
                availability=response.availability,
                site_name=site_name,
                link="",
                confidence_score=0.7
            )
        except Exception as e:
            print(f"Tier 2 LLM extraction failed for {site_name}: {e}")
            return None


class Tier1Scraper:
    async def scrape(self, site_config: Dict, query: str, client: httpx.AsyncClient) -> List[ProductResult]:
        search_url = site_config['search_url_template'].format(query=quote(query))
        response = await client.get(search_url, follow_redirects=True, timeout=HTTP_CLIENT_TIMEOUT)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'lxml')
        selectors = site_config['selectors']
        containers = soup.select(selectors['container'])

        results = []
        for container in containers[:5]:  # Limit results per site
            try:
                title_elem = container.select_one(selectors['title'])
                price_elem = container.select_one(selectors['price'])
                link_elem = container.select_one(selectors['link'])

                if not (title_elem and price_elem and link_elem): continue

                price_text = price_elem.get_text(strip=True)
                price_match = re.search(r'([\d,]+\.?\d*)', price_text.replace(',', ''))
                if not price_match: continue

                product = ProductResult(
                    product_name=title_elem.get('title', title_elem.get_text(strip=True)),
                    price=float(price_match.group(1)),
                    currency="GBP",  # Hardcoded for demo
                    link=urljoin(site_config['base_url'], link_elem.get('href', '')),
                    site_name=site_config.get('name'),
                    confidence_score=0.9
                )
                results.append(product)
            except Exception:
                continue

        if not results: raise ValueError("No products found via Tier 1 selectors.")
        return results


# ==============================================================================
# Part 4: Graph Workflow
# ==============================================================================

class PriceComparisonWorkflow:
    def __init__(self):
        self.cache_manager = CacheManager()
        self.config_manager = SiteConfigManager()
        self.tier1_scraper = Tier1Scraper()
        self.llm_agents = LLMAgents()
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the graph with a clear, conditional flow."""
        workflow = StateGraph(GraphState)
        workflow.add_node("site_selection", self.site_selection_agent)
        workflow.add_node("query_enhancement", self.query_enhancement_agent)
        workflow.add_node("scraping", self.scraping_agent)
        workflow.add_node("healing", self.healing_agent)
        workflow.add_node("consolidation", self.consolidation_agent)

        workflow.set_entry_point("site_selection")
        workflow.add_edge("site_selection", "query_enhancement")
        workflow.add_edge("query_enhancement", "scraping")
        workflow.add_conditional_edges("scraping", self.should_heal,
                                       {"continue_to_heal": "healing", "skip_to_consolidate": "consolidation"})
        workflow.add_edge("healing", "consolidation")
        workflow.add_edge("consolidation", END)
        return workflow.compile()

    async def site_selection_agent(self, state: GraphState) -> GraphState:
        """
        AGENT: This agent is the single source of truth for which sites to check.
        It uses the dynamic LLM discovery and caching approach.
        """
        print("---AGENT: Site Selection---")
        country = state["request"].country.value
        cached_sites = await self.cache_manager.get_country_sites(country)
        if cached_sites:
            print(f"Cache HIT for {country}.")
            state["selected_sites"] = cached_sites
        else:
            print(f"Cache MISS for {country}. Discovering sites with LLM.")
            discovered_sites = await self.llm_agents.discover_sites(country)
            state["selected_sites"] = discovered_sites
            await self.cache_manager.cache_country_sites(country, discovered_sites)
        return state

    async def query_enhancement_agent(self, state: GraphState) -> GraphState:
        print("---AGENT: Query Enhancement---")
        state["enhanced_query"] = await self.llm_agents.enhance_query(
            state["request"].query, state["request"].country.value
        )
        print(f"Enhanced query: {state['enhanced_query']}")
        return state

    async def scraping_agent(self, state: GraphState) -> GraphState:
        """
        AGENT: This agent attempts a Tier 1 scrape for each site discovered
        by the SiteSelectionAgent. It uses the static SiteConfigManager to find
        the correct selectors. If a site has no config or fails, it's passed to Tier 2.
        """
        print("---AGENT: Tier 1 Scraping---")
        query = state["enhanced_query"]
        sites = state["selected_sites"]

        async with httpx.AsyncClient(headers={'User-Agent': 'Mozilla/5.0'}) as client:
            tasks = [self._scrape_site_task(site, query, client) for site in sites]
            results = await asyncio.gather(*tasks)

        for status, result in results:
            if status == "success":
                state["successful_scrapes"].extend(result)
                state["tier_stats"]["tier1_success"] += 1
            else:
                state["failed_scrapes"].append(result)
                state["tier_stats"]["tier1_fails"] += 1
        return state

    async def _scrape_site_task(self, site: Dict, query: str, client: httpx.AsyncClient):
        """Helper to manage Tier 1 scraping for a single site."""
        site_domain = site["domain"]
        config = self.config_manager.get_config(site_domain)
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
            products = await self.tier1_scraper.scrape(config, query, client)
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

    def should_heal(self, state: GraphState) -> str:
        """Conditional edge router."""
        if state["failed_scrapes"]:
            return "continue_to_heal"
        return "skip_to_consolidate"

    async def healing_agent(self, state: GraphState) -> GraphState:
        print("---AGENT: Tier 2 Healing---")
        healing_tasks = []
        for failure in state["failed_scrapes"]:
            if failure.get("html"):
                site_name = failure["site"]["domain"]
                healing_tasks.append(self.llm_agents.extract_from_html(failure["html"], site_name))

        results = await asyncio.gather(*healing_tasks)
        for result in results:
            if result:
                failure_info = next((f for f in state["failed_scrapes"] if f["site"]["domain"] == result.site_name),
                                    None)
                if failure_info: result.link = failure_info['site']['base_url']
                state["healed_results"].append(result)
                state["tier_stats"]["tier2_success"] += 1
        return state

    async def consolidation_agent(self, state: GraphState) -> GraphState:
        print("---AGENT: Consolidation---")
        all_results = state["successful_scrapes"] + state["healed_results"]
        # Simple name-based deduplication
        unique_results = {p.product_name.lower(): p for p in all_results}.values()
        # Final deterministic sort
        state["final_results"] = sorted(list(unique_results), key=lambda p: p.price)
        return state


# ==============================================================================
# Part 5: FastAPI Application
# ==============================================================================

workflow_instance = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global workflow_instance
    workflow_instance = PriceComparisonWorkflow()
    print("Workflow initialized.")
    yield
    print("Application shutting down.")


app = FastAPI(title="Ultimate Price Comparison API", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.post("/search", response_model=SearchResponse)
async def search_products(request: ProductSearchRequest):
    if not workflow_instance: raise HTTPException(status_code=503, detail="Workflow not ready.")

    start_time = asyncio.get_event_loop().time()
    initial_state = GraphState(
        request=request, start_time=start_time, selected_sites=[], enhanced_query="",
        successful_scrapes=[], failed_scrapes=[], healed_results=[], final_results=[], errors=[],
        tier_stats={"tier1_success": 0, "tier2_success": 0, "tier1_fails": 0}
    )
    try:
        final_state = await workflow_instance.graph.ainvoke(initial_state, {"recursion_limit": 10})
        search_time_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
        results = final_state.get("final_results", [])[:request.max_results]

        return SearchResponse(
            success=True, total_results=len(results), search_time_ms=search_time_ms,
            results=results, errors=final_state.get("errors", []),
            metadata={
                "enhanced_query": final_state.get("enhanced_query"),
                "sites_checked": len(final_state.get("selected_sites", [])),
                "tier_stats": final_state.get("tier_stats")
            }
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check(): return {"status": "healthy"}