"""
Tier 1 scraper - now operates on a direct product page URL.
"""

import re
from typing import Dict
import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.models import ProductResult


async def scrape_product_page(
    page_url: str,
    site_config: Dict,
    client: httpx.AsyncClient
) -> ProductResult:
    """
    Scrapes a single product page using pre-configured selectors.

    Args:
        page_url: The direct URL to the product page.
        site_config: Configuration with selectors and currency.
        client: HTTP client.

    Returns:
        A single ProductResult object.

    Raises:
        ValueError: If scraping fails.
    """
    response = await client.get(page_url, follow_redirects=True, timeout=settings.HTTP_CLIENT_TIMEOUT)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'lxml')
    selectors = site_config['selectors']

    # The container is now the whole page, or a specific main block
    container = soup.select_one(selectors['container']) or soup

    title_elem = container.select_one(selectors['title'])
    price_elem = container.select_one(selectors['price'])

    if not (title_elem and price_elem):
        raise ValueError("Essential selectors (title, price) not found on product page.")

    price_text = price_elem.get_text(strip=True)
    price_match = re.search(r'([\d,]+\.?\d*)', price_text.replace(',', ''))
    if not price_match:
        raise ValueError("Could not parse price from text.")

    return ProductResult(
        product_name=title_elem.get_text(strip=True),
        price=float(price_match.group(1)),
        currency=site_config.get("currency", "USD"),  # Use currency from config
        link=page_url,
        site_name=site_config.get('name'),
        confidence_score=0.9
    )
