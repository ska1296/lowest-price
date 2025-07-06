"""
LLM-based agents for site discovery, query enhancement, and data extraction.
"""

import json
import re
from typing import List, Dict, Optional

from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
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


# Initialize LLM instances - prefer Google AI Studio over Vertex AI
def _get_llm():
    """Get the appropriate LLM instance based on available credentials."""
    if settings.GOOGLE_AI_API_KEY:
        print("🤖 Using Google AI Studio (Gemini 2.5 Flash)")
        return ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=settings.GOOGLE_AI_API_KEY,
            temperature=0
        )
    elif settings.GOOGLE_APPLICATION_CREDENTIALS:
        print("🤖 Using Vertex AI (Gemini 2.5 Flash)")
        return ChatVertexAI(
            model_name="gemini-2.5-flash",
            temperature=0
        )
    else:
        raise ValueError("No Google AI credentials available. Set GOOGLE_AI_API_KEY or GOOGLE_APPLICATION_CREDENTIALS.")

_llm = _get_llm()

# Configure structured output based on LLM type
def _get_tool_llm():
    """Get LLM configured for structured output."""
    if settings.GOOGLE_AI_API_KEY:
        # Google AI Studio doesn't support method parameter
        return _llm.with_structured_output(ProductInfoTool)
    else:
        # Vertex AI supports method parameter
        return _llm.with_structured_output(ProductInfoTool, method="tool_calling")

_tool_llm = _get_tool_llm()


async def discover_sites(country: str) -> List[Dict]:
    """
    Agent: Dynamically discover sites using the LLM.

    Args:
        country: Country code to discover sites for

    Returns:
        List of site dictionaries with 'domain' and 'base_url' keys
    """
    prompt = f"""You are an e-commerce expert. Identify the top 8-10 most popular e-commerce websites for buying new consumer electronics in the country with code '{country}'.

Include major retailers, electronics stores, department stores, and mobile carrier stores.
For {country}, include both international sites (like Amazon) and major local retailers.

Return ONLY a JSON list of objects, each with a 'domain' and 'base_url' key.
Example: [{{"domain": "amazon.com", "base_url": "https://www.amazon.com"}}, {{"domain": "bestbuy.com", "base_url": "https://www.bestbuy.com"}}]"""

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

        # More lenient relevance check for search query
        if search_query:
            search_words = search_query.lower().split()
            product_name_lower = response.product_name.lower()

            # Look for brand names and key product identifiers
            significant_words = [w for w in search_words if len(w) > 2 and w not in ['the', 'and', 'for', 'with', 'buy', 'get']]

            # Be more lenient - if any significant word matches OR if it's a reasonable product name, keep it
            has_match = any(word in product_name_lower for word in significant_words)
            is_reasonable_product = len(response.product_name) > 5 and not any(skip in product_name_lower for skip in ['error', 'not found', 'page'])

            if significant_words and not has_match and not is_reasonable_product:
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
