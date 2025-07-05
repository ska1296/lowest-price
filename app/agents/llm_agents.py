"""
LLM-based agents for site discovery, query enhancement, and data extraction.
"""

import json
import re
from typing import List, Dict, Optional

from langchain_core.pydantic_v1 import BaseModel as V1BaseModel, Field
from langchain_google_vertexai import ChatVertexAI

from app.config import settings
from app.models import ProductResult


class ProductInfoTool(V1BaseModel):
    """A tool to extract structured product information from HTML text."""
    product_name: str = Field(description="The full name of the product.")
    price: float = Field(description="The price of the product as a float.")
    currency: str = Field(description="The currency symbol or code (e.g., £, GBP).")
    availability: str = Field(description="Availability status, e.g., 'in-stock', 'out-of-stock'.")


# Initialize LLM instances
_llm = ChatVertexAI(
    project=settings.GCP_PROJECT,
    model_name="gemini-1.5-flash-001",
    temperature=0
)
_tool_llm = _llm.with_structured_output(ProductInfoTool, method="tool_calling")


async def discover_sites(country: str) -> List[Dict]:
    """
    Agent: Dynamically discover sites using the LLM.

    Args:
        country: Country code to discover sites for

    Returns:
        List of site dictionaries with 'domain' and 'base_url' keys
    """
    prompt = f"""You are an e-commerce expert. Identify the top 3 most popular e-commerce websites for buying new consumer electronics in the country with code '{country}'.
Also, for this demo, include 'books.toscrape.com'.
Return ONLY a JSON list of objects, each with a 'domain' and 'base_url' key. Example: [{{"domain": "amazon.com", "base_url": "https://www.amazon.com"}}]"""

    response = await _llm.ainvoke(prompt)
    try:
        match = re.search(r'\[.*\]', response.content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return []
    except (json.JSONDecodeError, TypeError):
        return []


async def enhance_query(query: str, country: str) -> str:
    """
    Agent: Enhance user query for better search results.

    Args:
        query: Original user query
        country: Target country code

    Returns:
        Enhanced query string
    """
    prompt = f"""You are a search optimization expert. Transform the user's query into an optimized search term for e-commerce sites.
Original query: "{query}"
Target country: {country}
Return ONLY the enhanced query string, no explanation."""

    response = await _llm.ainvoke(prompt)
    return response.content.strip().strip('"\'')


async def extract_from_html(html: str, site_name: str) -> Optional[ProductResult]:
    """
    Agent: Tier 2 Extraction using true function calling.

    Args:
        html: Raw HTML content to extract from
        site_name: Name of the site being scraped

    Returns:
        ProductResult if extraction successful, None otherwise
    """
    prompt = f"From this HTML of {site_name}, find the most relevant product and extract its details using the provided tool. HTML: \n\n{html[:8000]}"

    try:
        response: ProductInfoTool = await _tool_llm.ainvoke(prompt)
        return ProductResult(
            product_name=response.product_name,
            price=response.price,
            currency=response.currency,
            availability=response.availability,
            site_name=site_name,
            link="",  # Will be filled by calling agent
            confidence_score=0.7
        )
    except Exception as e:
        print(f"Tier 2 LLM extraction failed for {site_name}: {e}")
        return None
