"""
LLM-based agents for site discovery, query enhancement, and data extraction.
"""

import json
import re
from typing import List, Dict, Optional

from pydantic import BaseModel, Field
from langchain_google_vertexai import ChatVertexAI

from app.config import settings
from app.models import ProductResult
from app.utils.html_cleaner import preprocess_html_for_llm


class ProductInfoTool(BaseModel):
    """A tool to extract structured product information from HTML text."""
    product_name: str = Field(description="The full name of the product.")
    price: float = Field(description="The price of the product as a float.")
    currency: str = Field(description="The currency symbol or code (e.g., £, GBP).")
    availability: str = Field(description="Availability status, e.g., 'in-stock', 'out-of-stock'.")


# Initialize LLM instances
_llm = ChatVertexAI(
    model_name="gemini-2.5-flash",
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
    prompt = f"""You are an e-commerce expert. Identify the top 5 most popular e-commerce websites for buying new consumer electronics in the country with code '{country}'.
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


async def extract_from_html(raw_html: str, site_name: str, search_query: str = "") -> Optional[ProductResult]:
    """
    Agent: Tier 2 Extraction using preprocessed HTML and query-aware prompting.

    Args:
        raw_html: Raw HTML content to extract from
        site_name: Name of the site being scraped
        search_query: The original search query to help validate extraction

    Returns:
        ProductResult if extraction successful, None otherwise
    """
    # Preprocess the HTML first!
    cleaned_html = preprocess_html_for_llm(raw_html)

    if not cleaned_html.strip():
        print(f"HTML for {site_name} was empty after cleaning. Skipping LLM call.")
        return None

    # Query-aware prompt that helps LLM focus on the right product
    prompt = f"""You are extracting product information from a page on '{site_name}' that was found by searching for: "{search_query}"

**CRITICAL INSTRUCTIONS:**
1. **Find the MAIN product that matches the search query "{search_query}"**
2. **Look for `[MAIN PRODUCT TITLE]` first - this is usually the correct product**
3. **Ignore recommendations, related items, or "customers also bought" sections**
4. **The product name should be related to "{search_query}" - if it's completely different, DO NOT extract it**
5. **Use `[PRICE HINT]` for the price, but make sure it's for the main product, not accessories**

**VALIDATION RULES:**
- Product name must be relevant to the search query "{search_query}"
- Price must be reasonable (not $0.00 or extremely high)
- Ignore any text about "related products", "recommendations", "also bought"

**EXAMPLES:**

✅ **CORRECT - Product matches search:**
Search: "iPhone 16 Pro"
Content: `[MAIN PRODUCT TITLE]: Apple iPhone 16 Pro 128GB Black Titanium\\n[PRICE HINT]: $999.99`
Extract: iPhone 16 Pro (matches search)

❌ **WRONG - Product doesn't match search:**
Search: "iPhone 16 Pro"
Content: `[MAIN PRODUCT TITLE]: Apple iPhone 16 Pro 128GB\\n[HEADER H2]: Customers also bought\\n[PRICE HINT]: Sony Headphones $349.99`
DO NOT extract Sony Headphones (doesn't match iPhone search)

**Page Content:**
---
{cleaned_html[:6000]}
---

Extract the main product that matches the search query "{search_query}". If no matching product is found, do not call the tool."""

    try:
        response: ProductInfoTool = await _tool_llm.ainvoke(prompt)

        # Enhanced validation
        if not response.product_name or response.price <= 0:
            return None

        # Check if product name is relevant to search query
        if search_query:
            search_words = search_query.lower().split()
            product_words = response.product_name.lower().split()

            # At least one significant word should match
            significant_words = [w for w in search_words if len(w) > 3 and w not in ['the', 'and', 'for', 'with']]
            if significant_words and not any(word in response.product_name.lower() for word in significant_words):
                print(f"❌ Product '{response.product_name}' doesn't match search '{search_query}' - skipping")
                return None

        # Filter out common non-product titles
        skip_phrases = ["about us", "contact", "search results", "customers also bought", "page not found", "error", "404", "recommendations", "related products"]
        if any(phrase in response.product_name.lower() for phrase in skip_phrases):
            return None

        return ProductResult(
            product_name=response.product_name,
            price=response.price,
            currency=response.currency,
            availability=response.availability,
            site_name=site_name,
            link="",  # Will be filled by calling agent
            confidence_score=0.9  # Higher confidence due to query validation
        )
    except Exception as e:
        print(f"Tier 2 LLM extraction failed for {site_name}: {e}")
        return None
