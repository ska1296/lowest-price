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
from app.utils.rate_limiter import gemini_rate_limiter, get_static_sites


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
    Agent: Discover sites using static cache (to save LLM calls) or LLM fallback.

    Args:
        country: Country code to discover sites for

    Returns:
        List of site dictionaries with 'domain' and 'base_url' keys
    """
    # Use static cache first to save LLM calls (Gemini free tier: 10 req/min)
    if settings.ENABLE_STATIC_SITE_CACHE:
        static_sites = get_static_sites(country)
        if static_sites:
            print(f"🏪 Using static site cache for {country} ({len(static_sites)} sites)")
            return static_sites

    # Fallback to LLM discovery if no static cache
    print(f"🤖 Using LLM site discovery for {country} (consuming rate limit)")
    await gemini_rate_limiter.acquire()

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
    Agent: Enhance user query for better search results (with rate limiting).

    Args:
        query: Original user query
        country: Target country code

    Returns:
        Enhanced query string
    """
    # Simple enhancement rules to avoid LLM call for common cases
    query_lower = query.lower()

    # If query is already well-formed, skip LLM enhancement
    if any(brand in query_lower for brand in ['iphone', 'samsung', 'sony', 'apple', 'google']):
        if any(spec in query_lower for spec in ['gb', 'pro', 'max', 'plus', 'mini']):
            print(f"📝 Query '{query}' is already well-formed, skipping LLM enhancement")
            return query

    # Use LLM for complex queries
    print(f"🤖 Using LLM query enhancement (consuming rate limit)")
    await gemini_rate_limiter.acquire()

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

    # Enhanced anti-hallucination prompt
    prompt = f"""You are extracting product information from a webpage on '{site_name}'. You MUST ONLY use information that is explicitly present in the provided HTML content below.

**CRITICAL ANTI-HALLUCINATION RULES:**
1. **ONLY extract information that is literally present in the HTML content below**
2. **DO NOT use your training data or general knowledge about products or prices**
3. **If you cannot find clear price information in the HTML, DO NOT call the tool**
4. **The product must match the search query "{search_query}" AND be present in the HTML**
5. **Look for `[MAIN PRODUCT TITLE]` and `[PRICE HINT]` markers in the content**

**VALIDATION RULES:**
- Product name must be relevant to the search query "{search_query}"
- Price must be reasonable (not $0.00 or extremely high)
- Ignore any text about "related products", "recommendations", "also bought"

**CRITICAL PRICE EXTRACTION RULES:**
- Extract the CURRENT SELLING PRICE (the price customers pay now)
- Look for prices in this priority order:
  1. `[PRICE HINT]` markers (if available)
  2. Currency symbols followed by numbers: $999.99, £899, €1099, ₹79999
  3. Numbers with currency words: 999.99 USD, 899 GBP, 1099 EUR
  4. Standalone price numbers near product titles
- PRIORITIZE these price types (in order):
  1. "Starting at $X" or "From $X" (base/entry price)
  2. First price mentioned without qualifiers
  3. Prices near the main product title
- AVOID these price types:
  - Monthly payments: "$23.61/mo", "per month", "/month"
  - Trade-in offers: "as low as", "with trade-in", "after discount"
  - Promotional: "starts at $0", "from $0"
  - Original/crossed-out prices: "was $1099", "MSRP", "list price"
  - Higher storage/variant prices unless specifically requested

**EXAMPLES:**

✅ **CORRECT - Product matches search:**
Search: "iPhone 16 Pro"
Content: `[MAIN PRODUCT TITLE]: Apple iPhone 16 Pro 128GB Black Titanium\\n[PRICE HINT]: $999.99`
Extract: iPhone 16 Pro (matches search)

❌ **WRONG - Product doesn't match search:**
Search: "iPhone 16 Pro"
Content: `[MAIN PRODUCT TITLE]: Apple iPhone 16 Pro 128GB\\n[HEADER H2]: Customers also bought\\n[PRICE HINT]: Sony Headphones $349.99`
DO NOT extract Sony Headphones (doesn't match iPhone search)

✅ **CORRECT - Prioritize "starting at" price:**
Search: "Samsung Galaxy S24"
Content: `Starting at $1199.99\\n256GB model: $1299.99\\n512GB model: $1399.99`
Extract: Price = 1199.99 (use "Starting at" price, not higher variants)

✅ **CORRECT - Price extraction from complex pricing:**
Search: "iPhone 16 Pro 128GB"
Content: `[MAIN PRODUCT TITLE]: Apple iPhone 16 Pro\\nStarts at $0.00/mo\\n$23.61/mo for 36 mos\\nFull retail price $999.99`
Extract: Price = 999.99 (use "Full retail price", ignore promotional "$0.00/mo")

❌ **WRONG - Extracting higher variant price:**
Search: "Samsung Galaxy S24"
Content: `Starting at $1199.99\\n256GB model: $1299.99\\n512GB model: $1399.99`
DO NOT extract: Price = 1299.99 (this is a higher variant, use "Starting at" instead)

**HTML CONTENT TO ANALYZE:**
---
{cleaned_html[:8000]}
---

**FINAL INSTRUCTION:** Extract the main product information ONLY if:
1. You can clearly see the product name in the HTML content above
2. You can clearly see the price in the HTML content above
3. The product matches "{search_query}"

If any of these conditions are not met, DO NOT call the tool. Do not guess or use external knowledge."""

    try:
        # Rate limit LLM extraction calls
        await gemini_rate_limiter.acquire()
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
